# AI
from openAI.conversation import OpenAIModule

# Serial/Display
from transmission.serialModule import SerialModule
from display.show import DisplayModule

# Voice Trigger & Recording 
from toshiba.toshiba import ToshibaVoiceTrigger, VTAPI_ParameterID
from pvrecorder import PvRecorder 

# Audio
from audio.player import play_audio, sync_audio_and_gif
from audio.recorder import record_audio

# Variables
from etc.define import *

# others
import argparse, time, wave, sys, signal, threading
import numpy as np
from datetime import datetime

should_exit = threading.Event()

def signal_handler(signum, frame):
    print(f"Received signal {signum}. Initiating graceful shutdown...")
    should_exit.set()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def clean(recorder, serial_module, display):
    print("Cleaning up...")
    if recorder:
        recorder.stop()
        recorder.delete()
    if display:
        display.send_white_frames()
    if serial_module:
        serial_module.close()

def main():
    serial_module = SerialModule(BautRate)
    display = None
    recorder = None
    
    def ensure_serial_connection():
        if not serial_module.isPortOpen:
            print("Serial connection closed. Attempting to reopen...")
            for attempt in range(3):  # Try to reopen 3 times
                if serial_module.open(USBPort):
                    print("Successfully reopened serial connection.")
                    return True
                print(f"Attempt {attempt + 1} failed. Retrying in 1 second...")
                time.sleep(1)
            print("Failed to reopen serial connection after 3 attempts. Exiting.")
            clean(recorder, serial_module, display)
            sys.exit(1)
        return True

    try:
        print(f"Attempting to open serial port {USBPort} at {BautRate} baud...")
        if not serial_module.open(USBPort):  
            print(f"Failed to open serial port {USBPort}. Please check the connection and port settings.")
            sys.exit(1)
        print("Serial port opened successfully.")

        parser = argparse.ArgumentParser()
        display = DisplayModule(serial_module)
        ai_client = OpenAIModule()

        parser.add_argument('--vtdic', help='Path to Toshiba Voice Trigger dictionary file', default=ToshibaVoiceDictionary)
        parser.add_argument('--threshold', help='Threshold for keyword detection', type=int, default=600)
        args = parser.parse_args()

        print(f"Initializing Toshiba Voice Trigger with dictionary: {args.vtdic}")
        vt = ToshibaVoiceTrigger(args.vtdic)
        print(f"Initialized with frame_size: {vt.frame_size}, num_keywords: {vt.num_keywords}")

        vt.set_parameter(VTAPI_ParameterID.VTAPI_ParameterID_aThreshold, -1, args.threshold)
        print(f"Set threshold to {args.threshold}")

        recorder = PvRecorder(device_index=-1, frame_length=vt.frame_size)

        ensure_serial_connection()
        display.play_trigger_with_logo(TriggerAudio, SeamanLogo)

        while not should_exit.is_set():
            print("Listening for wake word...")
            recorder.start()
            wake_word_detected = False

            while not wake_word_detected and not should_exit.is_set():
                try:
                    audio_frame = recorder.read()
                    audio_data = np.array(audio_frame, dtype=np.int16)
                    detections = vt.process(audio_data)
                    if any(detections):
                        print(f"Wake word detected at {datetime.now()}")
                        wake_word_detected = True
                        detected_keyword = detections.index(max(detections))
                        print(f"Detected keyword: {detected_keyword}")
                        play_audio(ResponseAudio)
                        time.sleep(0.5)
                except OSError as e:
                    print(f"Stream error: {e}. Reopening stream.")
                    recorder.stop()
                    recorder = PvRecorder(device_index=-1, frame_length=vt.frame_size)
                    recorder.start()

            if should_exit.is_set():
                break

            ensure_serial_connection()
            ai_client.reset_conversation()
            
            conversation_active = True
            silence_count = 0
            max_silence = 2

            while conversation_active and not should_exit.is_set():
                ensure_serial_connection()
                display.start_listening_display(SatoruHappy)

                frames = record_audio(vt.frame_size)

                ensure_serial_connection()
                display.stop_listening_display()

                if len(frames) < int(RATE / vt.frame_size * RECORD_SECONDS):
                    print("Recording was incomplete. Skipping processing.")
                    conversation_active = False
                    continue

                time.sleep(0.1)

                with wave.open(AIOutputAudio, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(frames))

                response_file, conversation_ended = ai_client.process_audio(AIOutputAudio,AIOutputAudio)

                if response_file:
                    ensure_serial_connection()
                    sync_audio_and_gif(display, response_file, SpeakingGif)
                    if conversation_ended:
                        print("AI has determined the conversation has ended.")
                        conversation_active = False
                    elif not ai_client.get_last_user_message().strip():
                        silence_count += 1
                        if silence_count >= max_silence:
                            print("Maximum silence reached. Ending conversation.")
                            conversation_active = False
                else:
                    print("No response generated. Resuming wake word detection.")
                    conversation_active = False

            ensure_serial_connection()
            display.fade_in_logo(SeamanLogo)   
            print("Conversation ended. Returning to wake word detection.")
        
            should_exit.wait(timeout=1)
            time.sleep(1)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print("Graceful shutdown initiated.")
        clean(recorder, serial_module, display)

if __name__ == '__main__':
    main()
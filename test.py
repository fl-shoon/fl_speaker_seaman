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
from openai import OpenAIError

# Global variables to hold resources that need cleanup
global_recorder = None
global_serial_module = None
global_display = None
shutdown_event = threading.Event()

def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def print_log(message):
    print(f"{current_time()} - {message}", flush=True)

def clean():
    print_log("Starting cleanup process...")
    global global_recorder, global_serial_module, global_display
    
    if global_recorder:
        print_log("Stopping and deleting recorder...")
        try:
            global_recorder.stop()
            global_recorder.delete()
            print_log("Recorder stopped and deleted successfully.")
        except Exception as e:
            print_log(f"Error while stopping recorder: {e}")
    
    if global_display:
        print_log("Sending white frames...")
        try:
            global_display.send_white_frames()
            print_log("White frames sent successfully.")
        except Exception as e:
            print_log(f"Error while sending white frames: {e}")
    
    if global_serial_module:
        print_log("Closing serial connection...")
        try:
            global_serial_module.close()
            print_log("Serial connection closed successfully.")
        except Exception as e:
            print_log(f"Error while closing serial connection: {e}")
    
    print_log("Cleanup process completed.")

def shutdown_handler(signum, frame):
    print_log(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_event.set()
    clean()
    sys.exit(0)

# Register the shutdown handler for both SIGINT and SIGTERM
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

def ensure_serial_connection():
    if not global_serial_module.isPortOpen:
        print_log("Serial connection closed. Attempting to reopen...")
        for attempt in range(3):  # Try to reopen 3 times
            if global_serial_module.open(USBPort):
                print_log("Successfully reopened serial connection.")
                return True
            print_log(f"Attempt {attempt + 1} failed. Retrying in 1 second...")
            time.sleep(1)
        print_log("Failed to reopen serial connection after 3 attempts. Exiting.")
        return False
    return True

def main():
    global global_recorder, global_serial_module, global_display
    
    try:
        print_log("Initializing SerialModule...")
        global_serial_module = SerialModule(BautRate)
        print_log("Initializing DisplayModule...")
        global_display = DisplayModule(global_serial_module)

        print_log(f"Attempting to open serial port {USBPort} at {BautRate} baud...")
        if not global_serial_module.open(USBPort):  
            print_log(f"Failed to open serial port {USBPort}. Please check the connection and port settings.")
            return

        print_log("Serial port opened successfully.")

        parser = argparse.ArgumentParser()
        print_log("Initializing OpenAIModule...")
        ai_client = OpenAIModule()

        parser.add_argument('--vtdic', help='Path to Toshiba Voice Trigger dictionary file', default=ToshibaVoiceDictionary)
        parser.add_argument('--threshold', help='Threshold for keyword detection', type=int, default=600)
        args = parser.parse_args()

        print_log(f"Initializing Toshiba Voice Trigger with dictionary: {args.vtdic}")
        vt = ToshibaVoiceTrigger(args.vtdic)
        print_log(f"Initialized with frame_size: {vt.frame_size}, num_keywords: {vt.num_keywords}")

        vt.set_parameter(VTAPI_ParameterID.VTAPI_ParameterID_aThreshold, -1, args.threshold)
        print_log(f"Set threshold to {args.threshold}")

        print_log("Initializing PvRecorder...")
        global_recorder = PvRecorder(frame_length=vt.frame_size)

        if not ensure_serial_connection():
            print_log("Failed to ensure serial connection. Exiting.")
            return

        print_log("Playing trigger with logo...")
        global_display.play_trigger_with_logo(TriggerAudio, SeamanLogo)

        while not shutdown_event.is_set():
            print_log("Listening for wake word...")
            global_recorder.start()
            wake_word_detected = False

            while not wake_word_detected and not shutdown_event.is_set():
                try:
                    audio_frame = global_recorder.read()
                    audio_data = np.array(audio_frame, dtype=np.int16)
                    detections = vt.process(audio_data)
                    if any(detections):
                        print_log(f"Wake word detected at {datetime.now()}")
                        wake_word_detected = True
                        detected_keyword = detections.index(max(detections))
                        print_log(f"Detected keyword: {detected_keyword}")
                        play_audio(ResponseAudio)
                        time.sleep(0.5)
                except OSError as e:
                    print_log(f"Stream error: {e}. Reopening stream.")
                    global_recorder.stop()
                    global_recorder = PvRecorder(device_index=-1, frame_length=vt.frame_size)
                    global_recorder.start()

            if shutdown_event.is_set():
                print_log("Shutdown event received. Breaking main loop.")
                break

            if not ensure_serial_connection():
                print_log("Failed to ensure serial connection. Exiting main loop.")
                break

            ai_client.reset_conversation()
            
            conversation_active = True
            silence_count = 0
            max_silence = 2

            while conversation_active and not shutdown_event.is_set():
                if not ensure_serial_connection():
                    print_log("Failed to ensure serial connection. Ending conversation.")
                    break
                
                print_log("Starting listening display...")
                global_display.start_listening_display(SatoruHappy)

                print_log("Recording audio...")
                frames = record_audio(vt.frame_size)

                if not ensure_serial_connection():
                    print_log("Failed to ensure serial connection. Skipping audio processing.")
                    break

                print_log("Stopping listening display...")
                global_display.stop_listening_display()

                if len(frames) < int(RATE / vt.frame_size * RECORD_SECONDS):
                    print_log("Recording was incomplete. Skipping processing.")
                    conversation_active = False
                    continue

                time.sleep(0.1)

                print_log("Saving recorded audio...")
                with wave.open(AIOutputAudio, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(frames))

                try:
                    print_log("Processing audio with AI...")
                    response_file, conversation_ended = ai_client.process_audio(AIOutputAudio,AIOutputAudio)

                    if response_file:
                        if not ensure_serial_connection():
                            print_log("Failed to ensure serial connection. Skipping response playback.")
                            break
                        print_log("Syncing audio and gif...")
                        sync_audio_and_gif(global_display, response_file, SpeakingGif)
                        if conversation_ended:
                            print_log("AI has determined the conversation has ended.")
                            conversation_active = False
                        elif not ai_client.get_last_user_message().strip():
                            silence_count += 1
                            if silence_count >= max_silence:
                                print_log("Maximum silence reached. Ending conversation.")
                                conversation_active = False
                    else:
                        print_log("No response generated. Resuming wake word detection.")
                        conversation_active = False
                except OpenAIError as e:
                    print_log(f"OpenAI Error: {e}")
                    error_message = ai_client.handle_openai_error(e)
                    ai_client.fallback_text_to_speech(error_message, AIOutputAudio)
                    sync_audio_and_gif(global_display, AIOutputAudio, SpeakingGif)
                    conversation_active = False

            if not ensure_serial_connection():
                print_log("Failed to ensure serial connection. Exiting main loop.")
                break

            print_log("Fading in logo...")
            global_display.fade_in_logo(SeamanLogo)   
            print_log("Conversation ended. Returning to wake word detection.")
        
            time.sleep(0.1)

    except Exception as e:
        print_log(f"An unexpected error occurred: {e}")
        import traceback
        print_log(traceback.format_exc())

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print_log("KeyboardInterrupt received in main. Initiating shutdown...")
    finally:
        print_log("Program execution completed.")
        clean()
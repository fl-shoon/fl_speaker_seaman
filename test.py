# SetUp OS & Libraries
from setup import RaspberryPiSetup

# Serial/Display
from display.show import DisplayModule

# AI
from openAI.conversation import OpenAIModule

# Voice Trigger & Recording 
from toshiba.toshiba import ToshibaVoiceTrigger, VTAPI_ParameterID
from pvrecorder import PvRecorder 

# Variables
from etc.define import *

# others
import argparse, numpy as np, threading, time, wave
from datetime import datetime

def main():
    parser = argparse.ArgumentParser()
    display = DisplayModule()
    aiClient = OpenAIModule()
    parser.add_argument('--vtdic', help='Path to Toshiba Voice Trigger dictionary file', default=ToshibaVoiceDictionary)
    parser.add_argument('--threshold', help='Threshold for keyword detection', type=int, default=600)
    args = parser.parse_args()

    print(f"Initializing Toshiba Voice Trigger with dictionary: {args.vtdic}")
    vt = ToshibaVoiceTrigger(args.vtdic)
    print(f"Initialized with frame_size: {vt.frame_size}, num_keywords: {vt.num_keywords}")

    vt.set_parameter(VTAPI_ParameterID.VTAPI_ParameterID_aThreshold, -1, args.threshold)
    print(f"Set threshold to {args.threshold}")

    # Initialize PvRecorder with the same frame size as Toshiba Voice Trigger
    recorder = PvRecorder(device_index=-1, frame_length=vt.frame_size)

    display.play_trigger_with_logo(TriggerAudio, SeamanLogo)

    try:
        while True:
            print("Listening for wake word...")
            recorder.start()
            wake_word_detected = False

            while not wake_word_detected:
                try:
                    audio_frame = recorder.read()
                    audio_data = np.array(audio_frame, dtype=np.int16)
                    detections = vt.process(audio_data)
                    if any(detections):
                        print(f"Wake word detected at {datetime.now()}")
                        wake_word_detected = True
                        detected_keyword = detections.index(max(detections))
                        print(f"Detected keyword: {detected_keyword}")
                except OSError as e:
                    print(f"Stream error: {e}. Reopening stream.")
                    recorder.stop()

            # Reset conversation history for new conversation
            global conversation_history
            conversation_history = []
            
            # Start conversation loop
            conversation_active = True
            silence_count = 0
            max_silence = 2

            while conversation_active:
                stop_display = threading.Event()
                display_thread = threading.Thread(target=display.display_image, args=(SatoruHappy, stop_display))
                display_thread.start()

                play_audio_client = pyaudio.PyAudio()
                stream = play_audio_client.open(format=FORMAT,
                                channels=CHANNELS,
                                rate=RATE,
                                input=True,
                                frames_per_buffer=CHUNK)

                print("* recording")
                frames = []

                for _ in range(0, int(RATE / vt.frame_size * RECORD_SECONDS)):
                    try:
                        data = stream.read(vt.frame_size)
                        frames.append(data)
                    except OSError as e:
                        print(f"Stream error during recording: {e}. Reopening stream.")
                        stream.stop_stream()
                        stream.close()
                        break

                print("* done recording")

                stream.stop_stream()
                stream.close()
                play_audio_client.terminate()

                stop_display.set()
                display_thread.join()
                display.send_white_frames()

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

                response_file, conversation_ended = aiClient.process_audio(AIOutputAudio)

                if response_file:
                    display.sync_audio_and_gif(response_file, SpeakingGif)
                    if conversation_ended:
                        print("AI has determined the conversation has ended.")
                        conversation_active = False
                    elif not conversation_history[-2]["content"].strip():  # Check if user's last message was empty
                        silence_count += 1
                        if silence_count >= max_silence:
                            print("Maximum silence reached. Ending conversation.")
                            conversation_active = False
                else:
                    print("No response generated. Resuming wake word detection.")
                    conversation_active = False

            display.fade_in_logo(SeamanLogo)   
            print("Conversation ended. Returning to wake word detection.")

    except KeyboardInterrupt:
        print("Stopping...")
        display.send_white_frames()
    finally:
        recorder.delete()
        display.close()

if __name__ == '__main__':
    main()
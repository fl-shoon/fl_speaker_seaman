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
import argparse, time, wave, pyaudio, queue
import numpy as np
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

    recorder = PvRecorder(device_index=-1, frame_length=vt.frame_size)

    display.play_trigger_with_logo(TriggerAudio, SeamanLogo)
    display.start_display_thread()

    time.sleep(1)

    # Initialize conversation history
    conversation_history = []

    try:
        while True:
            print("Listening for wake word...")
            recorder.start()
            wake_word_detected = False

            wake_word_start_time = time.time()
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
                    if time.time() - wake_word_start_time > 60:  # 1 minute timeout
                        print("Wake word detection timeout. Restarting loop.")
                        break
                except OSError as e:
                    print(f"Stream error: {e}. Reopening stream.")
                    recorder.stop()
                    time.sleep(1)
                    recorder.start()

            if not wake_word_detected:
                continue

            conversation_active = True
            silence_count = 0
            max_silence = 2
            conversation_start_time = time.time()

            while conversation_active:
                try:
                    display.queue_image(SatoruHappy)

                    play_audio_client = pyaudio.PyAudio()
                    stream = play_audio_client.open(format=FORMAT,
                                        channels=CHANNELS,
                                        rate=RATE,
                                        input=True,
                                        frames_per_buffer=CHUNK)

                    print("* recording")
                    frames = []
                    recording_start_time = time.time()

                    while time.time() - recording_start_time < RECORD_SECONDS:
                        try:
                            data = stream.read(CHUNK)
                            frames.append(data)
                        except OSError as e:
                            print(f"Stream error during recording: {e}. Reopening stream.")
                            stream.stop_stream()
                            stream.close()
                            play_audio_client.terminate()
                            play_audio_client = pyaudio.PyAudio()
                            stream = play_audio_client.open(format=FORMAT,
                                                channels=CHANNELS,
                                                rate=RATE,
                                                input=True,
                                                frames_per_buffer=CHUNK)

                    print("* done recording")

                    print("Stopping audio stream...")
                    stream.stop_stream()
                    stream.close()
                    play_audio_client.terminate()
                    print("Audio stream stopped and closed.")

                    print("Clearing display queue...")
                    while not display.display_queue.empty():
                        try:
                            display.display_queue.get_nowait()
                        except queue.Empty:
                            break

                    print("Sending white frames...")
                    white_frame_start_time = time.time()
                    white_frame_timeout = 15  
                    try:
                        white_frame_success = display.serial.send_white_frames(timeout=white_frame_timeout)
                        if white_frame_success:
                            print("White frames sent successfully.")
                        else:
                            print("Failed to send white frames.")
                        if time.time() - white_frame_start_time > white_frame_timeout:
                            print("White frame sending timed out.")
                            raise TimeoutError("White frame sending timed out")
                    except Exception as e:
                        print(f"Error sending white frames: {str(e)}")
                        print("Attempting to continue despite white frame error...")

                    print("Saving recorded audio...")
                    try:
                        start_time = time.time()
                        with wave.open(AIOutputAudio, 'wb') as wf:
                            wf.setnchannels(CHANNELS)
                            wf.setsampwidth(2)  # 16-bit
                            wf.setframerate(RATE)
                            wf.writeframes(b''.join(frames))
                        end_time = time.time()
                        print(f"Audio saved to {AIOutputAudio}. Time taken: {end_time - start_time:.2f} seconds")
                    except Exception as e:
                        print(f"Error saving audio file: {str(e)}")
                        conversation_active = False
                        continue

                    print("Processing audio with AI...")
                    try:
                        start_time = time.time()
                        ai_timeout = 60  # 60 seconds timeout for AI processing
                        response_file, conversation_ended = aiClient.process_audio(AIOutputAudio)
                        end_time = time.time()
                        if end_time - start_time > ai_timeout:
                            print(f"AI processing timed out after {ai_timeout} seconds")
                            conversation_active = False
                            continue
                        print(f"AI processing complete. Time taken: {end_time - start_time:.2f} seconds")
                        print(f"Response file: {response_file}, Conversation ended: {conversation_ended}")
                        
                        # Update conversation history
                        conversation_history.append({"role": "user", "content": "Audio input"})

                    except Exception as e:
                        print(f"Error during AI processing: {str(e)}")
                        conversation_active = False
                        continue

                    if response_file:
                        display.sync_audio_and_gif(response_file, SpeakingGif)
                        if conversation_ended:
                            print("AI has determined the conversation has ended.")
                            conversation_active = False
                        elif len(conversation_history) >= 2 and not conversation_history[-2]["content"].strip():
                            silence_count += 1
                            if silence_count >= max_silence:
                                print("Maximum silence reached. Ending conversation.")
                                conversation_active = False
                    else:
                        print("No response generated. Resuming wake word detection.")
                        conversation_active = False

                    if time.time() - conversation_start_time > 300:  # 5 minutes timeout
                        print("Conversation timeout reached. Ending conversation.")
                        conversation_active = False

                except Exception as e:
                    print(f"Error in conversation loop: {str(e)}")
                    conversation_active = False

            # Reset conversation history at the end of each conversation
            conversation_history = []
            display.queue_image(SeamanLogo, fade_in=True, steps=7)
            print("Conversation ended. Returning to wake word detection.")

    except KeyboardInterrupt:
        print("Stopping...")
    except Exception as e:
        print(f"Unexpected error in main loop: {str(e)}")
    finally:
        display.stop_display_thread(timeout=5)
        try:
            display.serial.send_white_frames()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
        recorder.delete()
        display.serial.close()

if __name__ == '__main__':
    main()
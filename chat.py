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
import argparse, time, wave, sys, signal, threading, atexit
import numpy as np, termios, select, tty, sys, threading
from datetime import datetime
from openai import OpenAIError

should_exit = threading.Event()

# Global variables to hold resources that need cleanup
global_recorder = None
global_serial_module = None
global_display = None

def signal_handler(signum, frame):
    print(f"Received signal {signum}. Initiating graceful shutdown...")
    should_exit.set()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def is_terminal():
    return sys.stdin.isatty()

def is_data_available():
    if is_terminal():
        return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])
    else:
        return False  # Non-blocking check not possible in non-terminal environment

def get_key():
    if is_terminal():
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            if is_data_available():
                return sys.stdin.read(1)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    return None

def input_thread_function(should_exit):
    while not should_exit.is_set():
        try:
            if is_terminal():
                key = get_key()
                if key == 'q':
                    print("Quit command received. Initiating shutdown...")
                    should_exit.set()
                    break
            else:
                user_input = input("Press 'q' and Enter to quit: ")
                if user_input.lower() == 'q':
                    print("Quit command received. Initiating shutdown...")
                    should_exit.set()
                    break
        except EOFError:
            print("EOF encountered while reading input. Exiting input thread.")
            break
        except Exception as e:
            print(f"Error in input thread: {e}")
            break
        time.sleep(0.1)

def clean():
    print("Starting cleanup process...")
    global global_recorder, global_serial_module, global_display
    
    if global_recorder:
        print("Stopping and deleting recorder...")
        try:
            global_recorder.stop()
            global_recorder.delete()
            print("Recorder stopped and deleted successfully.")
        except Exception as e:
            print(f"Error while stopping recorder: {e}")
    
    if global_display:
        print("Sending white frames...")
        try:
            global_display.send_white_frames()
            print("White frames sent successfully.")
        except Exception as e:
            print(f"Error while sending white frames: {e}")
    
    if global_serial_module:
        print("Closing serial connection...")
        try:
            global_serial_module.close()
            print("Serial connection closed successfully.")
        except Exception as e:
            print(f"Error while closing serial connection: {e}")
    
    print("Cleanup process completed.")

# Register the cleanup function to be called on exit
atexit.register(clean)

def main():
    global global_recorder, global_serial_module, global_display
    
    input_thread = threading.Thread(target=input_thread_function, args=(should_exit,))
    input_thread.daemon = True
    input_thread.start()

    def ensure_serial_connection():
        if not global_serial_module.isPortOpen:
            print("Serial connection closed. Attempting to reopen...")
            for attempt in range(3):  # Try to reopen 3 times
                if global_serial_module.open(USBPort):
                    print("Successfully reopened serial connection.")
                    return True
                print(f"Attempt {attempt + 1} failed. Retrying in 1 second...")
                time.sleep(1)
            print("Failed to reopen serial connection after 3 attempts. Exiting.")
            return False
        return True

    try:
        print("Initializing SerialModule...")
        global_serial_module = SerialModule(BautRate)
        print("Initializing DisplayModule...")
        global_display = DisplayModule(global_serial_module)

        print(f"Attempting to open serial port {USBPort} at {BautRate} baud...")
        if not global_serial_module.open(USBPort):  
            print(f"Failed to open serial port {USBPort}. Please check the connection and port settings.")
            return

        print("Serial port opened successfully.")

        parser = argparse.ArgumentParser()
        print("Initializing OpenAIModule...")
        ai_client = OpenAIModule()

        parser.add_argument('--vtdic', help='Path to Toshiba Voice Trigger dictionary file', default=ToshibaVoiceDictionary)
        parser.add_argument('--threshold', help='Threshold for keyword detection', type=int, default=600)
        args = parser.parse_args()

        print(f"Initializing Toshiba Voice Trigger with dictionary: {args.vtdic}")
        vt = ToshibaVoiceTrigger(args.vtdic)
        print(f"Initialized with frame_size: {vt.frame_size}, num_keywords: {vt.num_keywords}")

        vt.set_parameter(VTAPI_ParameterID.VTAPI_ParameterID_aThreshold, -1, args.threshold)
        print(f"Set threshold to {args.threshold}")

        print("Initializing PvRecorder...")
        global_recorder = PvRecorder(frame_length=vt.frame_size)

        if not ensure_serial_connection():
            print("Failed to ensure serial connection. Exiting.")
            return

        print("Playing trigger with logo...")
        global_display.play_trigger_with_logo(TriggerAudio, SeamanLogo)

        while not should_exit.is_set():
            print("Listening for wake word...")
            global_recorder.start()
            wake_word_detected = False

            while not wake_word_detected and not should_exit.is_set():
                try:
                    audio_frame = global_recorder.read()
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
                    global_recorder.stop()
                    global_recorder = PvRecorder(device_index=-1, frame_length=vt.frame_size)
                    global_recorder.start()

            if should_exit.is_set():
                print("Exit signal received. Breaking main loop.")
                break

            if not ensure_serial_connection():
                print("Failed to ensure serial connection. Exiting main loop.")
                break

            ai_client.reset_conversation()
            
            conversation_active = True
            silence_count = 0
            max_silence = 2

            while conversation_active and not should_exit.is_set():
                if not ensure_serial_connection():
                    print("Failed to ensure serial connection. Ending conversation.")
                    break
                
                print("Starting listening display...")
                global_display.start_listening_display(SatoruHappy)

                print("Recording audio...")
                audio_data = record_audio()

                if audio_data is None:
                    print("No speech detected. Resuming wake word detection.")
                    conversation_active = False
                    continue

                if not ensure_serial_connection():
                    print("Failed to ensure serial connection. Skipping audio processing.")
                    break

                print("Stopping listening display...")
                global_display.stop_listening_display()

                print("Saving recorded audio...")
                with wave.open(AIOutputAudio, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(audio_data))

                try:
                    print("Processing audio with AI...")
                    response_file, conversation_ended = ai_client.process_audio(AIOutputAudio,AIOutputAudio)

                    if response_file:
                        if not ensure_serial_connection():
                            print("Failed to ensure serial connection. Skipping response playback.")
                            break
                        print("Syncing audio and gif...")
                        sync_audio_and_gif(global_display, response_file, SpeakingGif)
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
                except OpenAIError as e:
                    print(f"OpenAI Error: {e}")
                    error_message = ai_client.handle_openai_error(e)
                    ai_client.fallback_text_to_speech(error_message, AIOutputAudio)
                    sync_audio_and_gif(global_display, AIOutputAudio, SpeakingGif)
                    conversation_active = False

            if not ensure_serial_connection():
                print("Failed to ensure serial connection. Exiting main loop.")
                break

            print("Fading in logo...")
            global_display.fade_in_logo(SeamanLogo)   
            print("Conversation ended. Returning to wake word detection.")
        
            should_exit.wait(timeout=0.1)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        input_thread.join(timeout=1)
        atexit._run_exitfuncs()
    finally:
        input_thread.join(timeout=1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("KeyboardInterrupt received. Initiating shutdown...")
    finally:
        print("Program execution completed.")
        atexit._run_exitfuncs()
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
import argparse, time, wave, sys, signal
import numpy as np, logging
from datetime import datetime
from openai import OpenAIError
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GracefulKiller:
    kill_now = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True
        logger.info("Received termination signal. Initiating graceful shutdown...")

@contextmanager
def timeout(time):
    def raise_timeout(signum, frame):
        raise TimeoutError

    signal.signal(signal.SIGALRM, raise_timeout)
    signal.alarm(time)

    try:
        yield
    except TimeoutError:
        logger.warning(f"Operation timed out after {time} seconds")
    finally:
        signal.signal(signal.SIGALRM, signal.SIG_IGN)

def clean(recorder, serial_module, display):
    logger.info("Cleaning up...")
    if recorder:
        logger.info("Stopping and deleting recorder...")
        recorder.stop()
        recorder.delete()
    if display:
        logger.info("Sending white frames...")
        display.send_white_frames()
    if serial_module:
        logger.info("Closing serial connection...")
        serial_module.close()
    logger.info("Cleanup completed.")

def ensure_serial_connection(serial_module):
    if not serial_module.isPortOpen:
        logger.info("Serial connection closed. Attempting to reopen...")
        for attempt in range(2):  
            if serial_module.open(USBPort):
                logger.info("Successfully reopened serial connection.")
                return True
            logger.info(f"Attempt {attempt + 1} failed. Retrying in 1 second...")
            time.sleep(1)
        logger.error("Failed to reopen serial connection after 3 attempts. Exiting.")
        return False
    return True

def main():
    killer = GracefulKiller()
    serial_module = None
    display = None
    recorder = None
    
    try:
        logger.info(f"Attempting to open serial port {USBPort} at {BautRate} baud...")
        serial_module = SerialModule(BautRate)
        if not serial_module.open(USBPort):  
            logger.error(f"Failed to open serial port {USBPort}. Please check the connection and port settings.")
            sys.exit(1)
        logger.info("Serial port opened successfully.")

        parser = argparse.ArgumentParser()
        display = DisplayModule(serial_module)
        ai_client = OpenAIModule()

        parser.add_argument('--vtdic', help='Path to Toshiba Voice Trigger dictionary file', default=ToshibaVoiceDictionary)
        parser.add_argument('--threshold', help='Threshold for keyword detection', type=int, default=600)
        args = parser.parse_args()

        logger.info(f"Initializing Toshiba Voice Trigger with dictionary: {args.vtdic}")
        vt = ToshibaVoiceTrigger(args.vtdic)
        logger.info(f"Initialized with frame_size: {vt.frame_size}, num_keywords: {vt.num_keywords}")

        vt.set_parameter(VTAPI_ParameterID.VTAPI_ParameterID_aThreshold, -1, args.threshold)
        logger.info(f"Set threshold to {args.threshold}")

        recorder = PvRecorder(frame_length=vt.frame_size)

        ensure_serial_connection(serial_module)
        display.play_trigger_with_logo(TriggerAudio, SeamanLogo)

        while not killer.kill_now:
            logger.info("Listening for wake word...")
            recorder.start()
            wake_word_detected = False

            while not wake_word_detected and not killer.kill_now:
                try:
                    audio_frame = recorder.read()
                    audio_data = np.array(audio_frame, dtype=np.int16)
                    detections = vt.process(audio_data)
                    if any(detections):
                        logger.info(f"Wake word detected at {datetime.now()}")
                        wake_word_detected = True
                        detected_keyword = detections.index(max(detections))
                        logger.info(f"Detected keyword: {detected_keyword}")
                        play_audio(ResponseAudio)
                        time.sleep(0.5)
                except OSError as e:
                    logger.error(f"Stream error: {e}. Reopening stream.")
                    recorder.stop()
                    recorder = PvRecorder(device_index=-1, frame_length=vt.frame_size)
                    recorder.start()

            if killer.kill_now:
                break

            if not ensure_serial_connection(serial_module):
                break

            ai_client.reset_conversation()
            
            conversation_active = True
            silence_count = 0
            max_silence = 2

            while conversation_active and not killer.kill_now:
                if not ensure_serial_connection(serial_module):
                    break

                display.start_listening_display(SatoruHappy)

                frames = record_audio(vt.frame_size)

                if not ensure_serial_connection(serial_module):
                    break

                display.stop_listening_display()

                if len(frames) < int(RATE / vt.frame_size * RECORD_SECONDS):
                    logger.info("Recording was incomplete. Skipping processing.")
                    conversation_active = False
                    continue

                time.sleep(0.1)

                with wave.open(AIOutputAudio, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(frames))

                try:
                    response_file, conversation_ended = ai_client.process_audio(AIOutputAudio,AIOutputAudio)

                    if response_file:
                        if not ensure_serial_connection(serial_module):
                            break
                        sync_audio_and_gif(display, response_file, SpeakingGif)
                        if conversation_ended:
                            logger.info("AI has determined the conversation has ended.")
                            conversation_active = False
                        elif not ai_client.get_last_user_message().strip():
                            silence_count += 1
                            if silence_count >= max_silence:
                                logger.info("Maximum silence reached. Ending conversation.")
                                conversation_active = False
                    else:
                        logger.info("No response generated. Resuming wake word detection.")
                        conversation_active = False
                except OpenAIError as e:
                    error_message = ai_client.handle_openai_error(e)
                    ai_client.fallback_text_to_speech(error_message, AIOutputAudio)
                    sync_audio_and_gif(display, AIOutputAudio, SpeakingGif)
                    conversation_active = False

            if not ensure_serial_connection(serial_module):
                break

            display.fade_in_logo(SeamanLogo)   
            logger.info("Conversation ended. Returning to wake word detection.")
        
            time.sleep(1)

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        error_message = "申し訳ありませんが、システムエラーが発生しました。システムを再起動します。"
        ai_client.text_to_speech(error_message, AIOutputAudio)
        sync_audio_and_gif(display, ErrorAudio, SpeakingGif)
    finally:
        logger.info("Entering cleanup phase...")
        try:
            with timeout(5):  
                clean(recorder, serial_module, display)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        logger.info("Exiting program.")

if __name__ == '__main__':
    main()
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
import numpy as np, logging
from datetime import datetime
from openai import OpenAIError

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

should_exit = threading.Event()

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    should_exit.set()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def clean(recorder, serial_module, display):
    logger.info("Starting cleanup process...")
    if recorder:
        logger.info("Stopping and deleting recorder...")
        try:
            recorder.stop()
            recorder.delete()
            logger.info("Recorder stopped and deleted successfully.")
        except Exception as e:
            logger.error(f"Error while stopping recorder: {e}")
    
    if display:
        logger.info("Sending white frames...")
        try:
            display.send_white_frames()
            logger.info("White frames sent successfully.")
        except Exception as e:
            logger.error(f"Error while sending white frames: {e}")
    
    if serial_module:
        logger.info("Closing serial connection...")
        try:
            serial_module.close()
            logger.info("Serial connection closed successfully.")
        except Exception as e:
            logger.error(f"Error while closing serial connection: {e}")
    
    logger.info("Cleanup process completed.")

def main():
    serial_module = None
    display = None
    recorder = None
    
    def ensure_serial_connection():
        if not serial_module.isPortOpen:
            logger.info("Serial connection closed. Attempting to reopen...")
            for attempt in range(3):  # Try to reopen 3 times
                if serial_module.open(USBPort):
                    logger.info("Successfully reopened serial connection.")
                    return True
                logger.info(f"Attempt {attempt + 1} failed. Retrying in 1 second...")
                time.sleep(1)
            logger.error("Failed to reopen serial connection after 3 attempts. Exiting.")
            return False
        return True

    try:
        logger.info("Initializing SerialModule...")
        serial_module = SerialModule(BautRate)
        logger.info("Initializing DisplayModule...")
        display = DisplayModule(serial_module)

        logger.info(f"Attempting to open serial port {USBPort} at {BautRate} baud...")
        if not serial_module.open(USBPort):  
            logger.error(f"Failed to open serial port {USBPort}. Please check the connection and port settings.")
            sys.exit(1)
        logger.info("Serial port opened successfully.")

        parser = argparse.ArgumentParser()
        logger.info("Initializing OpenAIModule...")
        ai_client = OpenAIModule()

        parser.add_argument('--vtdic', help='Path to Toshiba Voice Trigger dictionary file', default=ToshibaVoiceDictionary)
        parser.add_argument('--threshold', help='Threshold for keyword detection', type=int, default=600)
        args = parser.parse_args()

        logger.info(f"Initializing Toshiba Voice Trigger with dictionary: {args.vtdic}")
        vt = ToshibaVoiceTrigger(args.vtdic)
        logger.info(f"Initialized with frame_size: {vt.frame_size}, num_keywords: {vt.num_keywords}")

        vt.set_parameter(VTAPI_ParameterID.VTAPI_ParameterID_aThreshold, -1, args.threshold)
        logger.info(f"Set threshold to {args.threshold}")

        logger.info("Initializing PvRecorder...")
        recorder = PvRecorder(frame_length=vt.frame_size)

        if not ensure_serial_connection():
            raise Exception("Failed to ensure serial connection.")
        
        logger.info("Playing trigger with logo...")
        display.play_trigger_with_logo(TriggerAudio, SeamanLogo)

        while not should_exit.is_set():
            logger.info("Listening for wake word...")
            recorder.start()
            wake_word_detected = False

            while not wake_word_detected and not should_exit.is_set():
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

            if should_exit.is_set():
                logger.info("Exit signal received. Breaking main loop.")
                break

            if not ensure_serial_connection():
                logger.error("Failed to ensure serial connection. Exiting main loop.")
                break

            ai_client.reset_conversation()
            
            conversation_active = True
            silence_count = 0
            max_silence = 2

            while conversation_active and not should_exit.is_set():
                if not ensure_serial_connection():
                    logger.error("Failed to ensure serial connection. Ending conversation.")
                    break
                
                logger.info("Starting listening display...")
                display.start_listening_display(SatoruHappy)

                logger.info("Recording audio...")
                frames = record_audio(vt.frame_size)

                if not ensure_serial_connection():
                    logger.error("Failed to ensure serial connection. Skipping audio processing.")
                    break

                logger.info("Stopping listening display...")
                display.stop_listening_display()

                if len(frames) < int(RATE / vt.frame_size * RECORD_SECONDS):
                    logger.info("Recording was incomplete. Skipping processing.")
                    conversation_active = False
                    continue

                time.sleep(0.1)

                logger.info("Saving recorded audio...")
                with wave.open(AIOutputAudio, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(frames))

                
                try:
                    logger.info("Processing audio with AI...")
                    response_file, conversation_ended = ai_client.process_audio(AIOutputAudio,AIOutputAudio)

                    if response_file:
                        if not ensure_serial_connection():
                            logger.error("Failed to ensure serial connection. Skipping response playback.")
                            break
                        logger.info("Syncing audio and gif...")
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
                    logger.error(f"OpenAI Error: {e}")
                    error_message = ai_client.handle_openai_error(e)
                    ai_client.fallback_text_to_speech(error_message, AIOutputAudio)
                    sync_audio_and_gif(display, AIOutputAudio, SpeakingGif)
                    conversation_active = False

            if not ensure_serial_connection():
                logger.error("Failed to ensure serial connection. Exiting main loop.")
                break

            logger.info("Fading in logo...")
            display.fade_in_logo(SeamanLogo)   
            logger.info("Conversation ended. Returning to wake word detection.")
        
            should_exit.wait(timeout=0.1)

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        logger.info("Entering cleanup phase...")
        try:
            clean(recorder, serial_module, display)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
        logger.info("Exiting program")

if __name__ == '__main__':
    main()
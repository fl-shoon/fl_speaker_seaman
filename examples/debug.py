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
import argparse, time, wave, sys, signal, logging, numpy as np
from datetime import datetime
from openai import OpenAIError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables to hold resources that need cleanup
global_recorder = None
global_serial_module = None
global_display = None
exit_flag = False

def signal_handler(signum, frame):
    global exit_flag
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    exit_flag = True
    clean()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def clean():
    logger.info("Starting cleanup process...")
    global global_recorder, global_serial_module, global_display

    if global_recorder:
        logger.info("Stopping and deleting recorder...")
        try:
            global_recorder.stop()
            global_recorder.delete()
            logger.info("Recorder stopped and deleted successfully.")
        except Exception as e:
            logger.error(f"Error while stopping recorder: {e}")

    if global_display and global_serial_module and global_serial_module.isPortOpen:
        logger.info("Turning display white...")
        try:
            global_display.send_white_frames()
            logger.info("Display turned to white successfully.")
        except Exception as e:
            logger.error(f"Error while turning display white: {e}")

    if global_serial_module:
        logger.info("Closing serial connection...")
        try:
            global_serial_module.close()
            logger.info("Serial connection closed successfully.")
        except Exception as e:
            logger.error(f"Error while closing serial connection: {e}")

    logger.info("Cleanup process completed.")

def main():
    global global_recorder, global_serial_module, global_display, exit_flag

    def ensure_serial_connection():
        if not global_serial_module.isPortOpen:
            logger.info("Serial connection closed. Attempting to reopen...")
            for attempt in range(3):  # Try to reopen 3 times
                if global_serial_module.open(USBPort):
                    logger.info("Successfully reopened serial connection.")
                    return True
                logger.info(f"Attempt {attempt + 1} failed. Retrying in 1 second...")
                time.sleep(1)
            logger.error("Failed to reopen serial connection after 3 attempts. Exiting.")
            return False
        return True

    try:
        logger.info("Initializing SerialModule...")
        global_serial_module = SerialModule(BautRate)
        logger.info("Initializing DisplayModule...")
        global_display = DisplayModule(global_serial_module)

        logger.info(f"Attempting to open serial port {USBPort} at {BautRate} baud...")
        if not global_serial_module.open(USBPort):  
            logger.error(f"Failed to open serial port {USBPort}. Please check the connection and port settings.")
            return

        logger.info("Serial port opened successfully.")

        parser = argparse.ArgumentParser()
        logger.info("Initializing OpenAIModule...")
        ai_client = OpenAIModule()

        parser.add_argument('--vtdic', help='Path to Toshiba Voice Trigger dictionary file', default=ToshibaVoiceDictionary)
        parser.add_argument('--threshold', help='Threshold for keyword detection', type=int, default=600)
        args = parser.parse_args()

        logger.info(f"Initializing Toshiba Voice Trigger with dictionary: {args.vtdic}")
        vt = ToshibaVoiceTrigger(args.vtdic)
        logger.info(f"Initialized Toshiba Voice Trigger with frame_size: {vt.frame_size}, num_keywords: {vt.num_keywords}")

        vt.set_parameter(VTAPI_ParameterID.VTAPI_ParameterID_aThreshold, -1, args.threshold)
        logger.info(f"Set threshold to {args.threshold}")

        logger.info("Initializing PvRecorder...")
        global_recorder = PvRecorder(frame_length=vt.frame_size)

        if not ensure_serial_connection():
            logger.error("Failed to ensure serial connection. Exiting.")
            return

        global_display.play_trigger_with_logo(TriggerAudio, SeamanLogo)

        while not exit_flag:
            try:
                logger.info("Listening for wake word...")
                global_recorder.start()
                wake_word_detected = False

                while not wake_word_detected and not exit_flag:
                    try:
                        audio_frame = global_recorder.read()
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
                        global_recorder.stop()
                        global_recorder = PvRecorder(device_index=-1, frame_length=vt.frame_size)
                        global_recorder.start()

                if exit_flag:
                    break

                if not ensure_serial_connection():
                    logger.error("Failed to ensure serial connection. Exiting main loop.")
                    break

                ai_client.reset_conversation()

                conversation_active = True
                silence_count = 0
                max_silence = 2

                while conversation_active and not exit_flag:
                    if not ensure_serial_connection():
                        logger.error("Failed to ensure serial connection. Ending conversation.")
                        break

                    global_display.start_listening_display(SatoruHappy)

                    logger.info("Recording audio...")
                    audio_data = record_audio()

                    if audio_data:
                        logger.info("Saving recorded audio...")
                        input_audio_file = AIOutputAudio
                        with wave.open(input_audio_file, 'wb') as wf:
                            wf.setnchannels(CHANNELS)
                            wf.setsampwidth(2)  
                            wf.setframerate(RATE)
                            wf.writeframes(audio_data)  
                    else:
                        logger.info("No speech detected. Resuming wake word detection.")
                        conversation_active = False
                        continue

                    if exit_flag:
                        break

                    if not ensure_serial_connection():
                        logger.error("Failed to ensure serial connection. Skipping audio processing.")
                        break

                    global_display.stop_listening_display()

                    try:
                        logger.info("Processing audio with AI...")
                        response_file, conversation_ended = ai_client.process_audio(input_audio_file)

                        if response_file:
                            if not ensure_serial_connection():
                                logger.error("Failed to ensure serial connection. Skipping response playback.")
                                break
                            sync_audio_and_gif(global_display, response_file, SpeakingGif)
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
                        error_audio_file = ErrorAudio
                        ai_client.fallback_text_to_speech(error_message, error_audio_file)
                        sync_audio_and_gif(global_display, error_audio_file, SpeakingGif)
                        conversation_active = False

                if exit_flag:
                    break

                if not ensure_serial_connection():
                    logger.error("Failed to ensure serial connection. Exiting main loop.")
                    break

                global_display.fade_in_logo(SeamanLogo)   
                logger.info("Conversation ended. Returning to wake word detection.")
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                if exit_flag:
                    break
                time.sleep(1)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Initiating shutdown...")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        clean()
        logger.info("Program execution completed.")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Ensuring cleanup...")
    finally:
        logging.shutdown()
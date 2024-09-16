import argparse
import logging
import signal
import wave
import time
import numpy as np
from threading import Event

from openAI.conversation import OpenAIModule
from audio.player import sync_audio_and_gif, play_audio
from audio.recorder import record_audio
from display.show import DisplayModule
from display.setting import SettingModule
from etc.define import *
from pvrecorder import PvRecorder
from toshiba.toshiba import ToshibaVoiceTrigger, VTAPI_ParameterID
from transmission.serialModule import SerialModule

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables
exit_event = Event()

class VoiceAssistant:
    def __init__(self, args):
        self.args = args
        self.serial_module = None
        self.display = None
        self.recorder = None
        self.vt = None
        self.ai_client = None
        self.setting_module = None

    def initialize(self):
        try:
            self.serial_module = SerialModule(BautRate)
            self.display = DisplayModule(self.serial_module)
            
            if not self.serial_module.open(USBPort):
                raise ConnectionError(f"Failed to open serial port {USBPort}")

            self.ai_client = OpenAIModule()
            self.vt = ToshibaVoiceTrigger(self.args.vtdic)
            self.vt.set_parameter(VTAPI_ParameterID.VTAPI_ParameterID_aThreshold, -1, self.args.threshold)
            
            self.recorder = PvRecorder(frame_length=self.vt.frame_size)
            self.setting_module = SettingModule(self.serial_module)
            
            logger.info("Voice Assistant initialized successfully")
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            self.cleanup()
            raise

    def ensure_serial_connection(self):
        if not self.serial_module.isPortOpen:
            logger.info("Serial connection closed. Attempting to reopen...")
            for attempt in range(3):
                if self.serial_module.open(USBPort):
                    logger.info("Successfully reopened serial connection.")
                    return True
                logger.info(f"Attempt {attempt + 1} failed. Retrying in 1 second...")
                time.sleep(1)
            logger.error("Failed to reopen serial connection after 3 attempts.")
            return False
        return True

    def listen_for_wake_word(self):
        self.recorder.start()
        try:
            while not exit_event.is_set():
                audio_frame = self.recorder.read()
                audio_data = np.array(audio_frame, dtype=np.int16)
                detections = self.vt.process(audio_data)
                if any(detections):
                    detected_keyword = detections.index(max(detections))
                    logger.info(f"Wake word detected: {detected_keyword}")
                    play_audio(ResponseAudio)
                    return True
                
                if self.serial_module.check_right_button():
                    logger.info("Right button pressed. Opening settings menu.")
                    self.open_settings_menu()
                    return False
                
                time.sleep(0.01)
        except Exception as e:
            logger.error(f"Error in wake word detection: {e}")
        finally:
            self.recorder.stop()
        return False

    def process_conversation(self):
        conversation_active = True
        silence_count = 0
        max_silence = 2

        while conversation_active and not exit_event.is_set():
            if not self.ensure_serial_connection():
                break

            self.display.start_listening_display(SatoruHappy)
            audio_data = record_audio()

            if not audio_data:
                silence_count += 1
                if silence_count >= max_silence:
                    logger.info("Maximum silence reached. Ending conversation.")
                    conversation_active = False
                continue

            input_audio_file = AIOutputAudio
            with wave.open(input_audio_file, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(RATE)
                wf.writeframes(audio_data)

            self.display.stop_listening_display()

            try:
                response_file, conversation_ended = self.ai_client.process_audio(input_audio_file)
                if response_file:
                    sync_audio_and_gif(self.display, response_file, SpeakingGif)
                    if conversation_ended:
                        conversation_active = False
                else:
                    logger.info("No response generated. Ending conversation.")
                    conversation_active = False
            except Exception as e:
                logger.error(f"Error processing conversation: {e}")
                error_message = self.ai_client.handle_openai_error(e)
                error_audio_file = ErrorAudio
                self.ai_client.fallback_text_to_speech(error_message, error_audio_file)
                sync_audio_and_gif(self.display, error_audio_file, SpeakingGif)
                conversation_active = False

        self.display.fade_in_logo(SeamanLogo)

    def open_settings_menu(self):
        action, new_brightness = self.setting_module.run()
        if action == 'back':
            logger.info("Returned from settings menu")
        elif action == 'exit':
            logger.info("Exited from settings menu")
        
        if new_brightness != self.serial_module.current_brightness:
            self.serial_module.set_brightness(new_brightness)
            logger.info(f"Brightness updated to {new_brightness:.2f}")

    def run(self):
        try:
            self.initialize()
            self.display.play_trigger_with_logo(TriggerAudio, SeamanLogo)

            while not exit_event.is_set():
                if self.listen_for_wake_word():
                    self.process_conversation()

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Shutting down...")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        finally:
            self.cleanup()

    def cleanup(self):
        logger.info("Starting cleanup process...")
        if self.recorder:
            self.recorder.stop()
            self.recorder.delete()
        if self.display and self.serial_module and self.serial_module.isPortOpen:
            self.display.send_white_frames()
        if self.serial_module:
            self.serial_module.close()
        logger.info("Cleanup process completed.")

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    exit_event.set()

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser()
    parser.add_argument('--vtdic', help='Path to Toshiba Voice Trigger dictionary file', default=ToshibaVoiceDictionary)
    parser.add_argument('--threshold', help='Threshold for keyword detection', type=int, default=600)
    args = parser.parse_args()

    assistant = VoiceAssistant(args)
    assistant.run()
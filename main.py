from audio.player import sync_audio_and_gif, play_audio
from audio.recorder import InteractiveRecorder
from display.show import DisplayModule
from display.setting import SettingModule
from etc.define import *
from openAI.conversation import OpenAIModule
from pvrecorder import PvRecorder
from pico.pico import PicoVoiceTrigger
from threading import Event
from toshiba.toshiba import ToshibaVoiceTrigger, VTAPI_ParameterID
from transmission.serialModule import SerialModule

import argparse
import logging
import numpy as np
import signal
import time
import wave

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

exit_event = Event()

class VoiceAssistant:
    def __init__(self, args):
        self.args = args
        self.serial_module = None
        self.display = None
        self.recorder = None
        self.vt = None
        self.porcupine = None
        self.ai_client = None
        self.audio_threshold_calibration_done = False
        self.interactive_recorder = InteractiveRecorder()

    def initialize(self):
        try:
            self.serial_module = SerialModule(BautRate)
            self.display = DisplayModule(self.serial_module)
            # self.settingMenu = Setting
            
            if not self.serial_module.open(USBPort):
                # FIXME: Send a failure notice post request to server later
                raise ConnectionError(f"Failed to open serial port {USBPort}")

            self.ai_client = OpenAIModule()
            try:
                self.vt = ToshibaVoiceTrigger(self.args.vtdic)
                self.vt.set_parameter(VTAPI_ParameterID.VTAPI_ParameterID_aThreshold, -1, self.args.threshold)
                
                self.recorder = PvRecorder(frame_length=self.vt.frame_size)
            except Exception as e:
                self.vt = None
                logger.info("Failed to initialize toshiba. Using pico instead")
                self.porcupine = PicoVoiceTrigger(self.args)
                self.recorder = PvRecorder(frame_length=self.porcupine.frame_length)
            
            logger.info("Voice Assistant initialized successfully")
        except Exception as e:
            # FIXME: Send a failure notice post request to server later
            logger.error(f"Initialization error: {e}")
            self.cleanup()
            raise

    def handle_audio_calibration(self):
        if not self.audio_threshold_calibration_done:
            logger.info("Starting calibration process...")
            self.interactive_recorder.calibrate_energy_threshold()
            logger.info("Calibration completed successfully.")
            self.audio_threshold_calibration_done = True
        return self.audio_threshold_calibration_done

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
            # FIXME: Send a failure notice post request to server later
            return False
        return True

    def listen_for_wake_word(self):
        self.recorder.start()
        try:
            while not exit_event.is_set():
                audio_frame = self.recorder.read()
                audio_data = np.array(audio_frame, dtype=np.int16)

                if self.vt: 
                    detections = self.vt.process(audio_data)
                    wake_word_triggered = any(detections)
                else: 
                    detections = self.porcupine.process(audio_frame)
                    wake_word_triggered = detections >= 0
                
                if wake_word_triggered:
                    '''
                    All in one operation to both detect 
                    if a wake word was spoken and 
                    determine which specific wake word it was
                    
                    # detected_keyword = detections.index(max(detections))
                    # logger.info(f"Wake word detected: {detected_keyword}")
                    '''
                    logger.info("Wake word detected")
                    if self.handle_audio_calibration():
                        play_audio(ResponseAudio)
                        return True
                    else:
                        logger.info("Calibration failed. Returning to wake word detection.")
        except Exception as e:
            # FIXME: Handle the error and try to process wake word again
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
            audio_data = self.interactive_recorder.record_question(silence_duration=1.5, max_duration=30)

            if not audio_data:
                silence_count += 1
                if silence_count >= max_silence:
                    logger.info("Maximum silence reached. Ending conversation.")
                    conversation_active = False
                continue
            else:
                silence_count = 0

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
                sync_audio_and_gif(self.display, ErrorAudio, SpeakingGif)
                conversation_active = False

        self.display.fade_in_logo(SeamanLogo)
        self.audio_threadshold_calibration_done = False

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
    # Handle the signals when either signal is received
    logger.info(f"Received {signum} signal. Initiating graceful shutdown...")
    exit_event.set()

if __name__ == '__main__':
    '''
    Set up a handler for a specific signal
    signal.signal(params1, params2)

    params1 : the signal number
    params2 : the function to be called when the signal is received

    SIGTERM(Signal Terminate) 
    The standard signal for requesting a program to terminate

    SIGINT (Signal Interrupt)
    Typically sent when the user presses Ctrl+C
    '''
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser()
    # Toshiba
    parser.add_argument('--vtdic', help='Path to Toshiba Voice Trigger dictionary file', default=ToshibaVoiceDictionary)
    parser.add_argument('--threshold', help='Threshold for keyword detection', type=int, default=600)
    
    # Pico
    parser.add_argument('--access_key', help='AccessKey for Porcupine', default=os.environ["PICO_ACCESS_KEY"])
    parser.add_argument('--keyword_paths', nargs='+', help="Paths to keyword model files", default=[PicoWakeWordSatoru])
    parser.add_argument('--model_path', help='Path to Porcupine model file', default=PicoLangModel)
    parser.add_argument('--sensitivities', nargs='+', help="Sensitivities for keywords", type=float, default=[0.5])

    args = parser.parse_args()

    assistant = VoiceAssistant(args)
    assistant.run()
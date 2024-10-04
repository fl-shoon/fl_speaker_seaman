from audio.player import AudioPlayer
from audio.recorder import InteractiveRecorder
from collections import deque
from display.display import DisplayModule
from display.setting import SettingMenu
from etc.define import *
from openAI.conversation import OpenAIClient
from pvrecorder import PvRecorder
from pico.pico import PicoVoiceTrigger
from threading import Event
from toshiba.toshiba import ToshibaVoiceTrigger, VTAPI_ParameterID
from transmission.serialModule import SerialModule

import argparse
import asyncio
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
        self.interactive_recorder = InteractiveRecorder()
        self.calibration_buffer = deque(maxlen=100)  
        self.energy_levels = deque(maxlen=100)
        self.initialize(self.args.aiclient)

    def initialize(self, aiclient):
        try:
            self.serial_module = SerialModule(BautRate)
            self.display = DisplayModule(self.serial_module)
            self.audioPlayer = AudioPlayer(self.display)
            self.setting_menu = SettingMenu(self.serial_module)
            
            if not self.serial_module.open(USBPort):
                # FIXME: Send a failure notice post request to server later
                raise ConnectionError(f"Failed to open serial port {USBPort}")

            self.ai_client = aiclient
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

    def update_calibration(self, audio_data):
        chunk = audio_data[:self.interactive_recorder.CHUNK_SIZE]
        filtered_audio = self.interactive_recorder.butter_lowpass_filter(chunk, cutoff=1000, fs=RATE)
        energy = np.sum(filtered_audio**2) / len(filtered_audio)
        self.energy_levels.append(energy)

    def perform_calibration(self):
        if len(self.energy_levels) > 0:
            self.interactive_recorder.silence_energy = np.mean(self.energy_levels)
            self.interactive_recorder.energy_threshold = self.interactive_recorder.silence_energy * 2
            # logger.info(f"Calibration updated. Silence energy: {self.interactive_recorder.silence_energy}, Threshold: {self.interactive_recorder.energy_threshold}")
        else:
            logger.warning("No energy data available for calibration")

    def listen_for_wake_word(self):
        self.recorder.start()
        self.calibration_buffer.clear()
        self.energy_levels.clear()
        calibration_interval = 50  #50 -> frames
        frames_since_last_calibration = 0

        try:
            while not exit_event.is_set():
                audio_frame = self.recorder.read()
                audio_data = np.array(audio_frame, dtype=np.int16)

                self.update_calibration(audio_data)
                frames_since_last_calibration += 1

                if frames_since_last_calibration >= calibration_interval:
                    self.perform_calibration()
                    frames_since_last_calibration = 0

                if self.vt: 
                    detections = self.vt.process(audio_data)
                    wake_word_triggered = any(detections)
                else: 
                    detections = self.porcupine.process(audio_frame)
                    wake_word_triggered = detections >= 0
                
                if wake_word_triggered:
                    logger.info("Wake word detected")
                    self.audioPlayer.play_audio(ResponseAudio)
                    return True
                
                else:
                    res, brightness = self.check_buttons()
                    logger.info(f"response: {res}, brightness: {brightness}")
                    # if res == 'exit':

        except Exception as e:
            logger.error(f"Error in wake word detection: {e}")
        finally:
            self.recorder.stop()
        return False

    async def process_conversation(self):
        conversation_active = True
        silence_count = 0
        max_silence = 2

        while conversation_active and not exit_event.is_set():
            if not self.ensure_serial_connection():
                break

            self.display.start_listening_display(SatoruHappy)
            audio_data = self.interactive_recorder.record_question(silence_duration=1.5, max_duration=30, audio_player=self.audioPlayer)

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
                conversation_ended = await self.ai_client.process_audio(input_audio_file)
                if conversation_ended:
                    conversation_active = False
            except Exception as e:
                logger.error(f"Error processing conversation: {e}")
                error_message = self.ai_client.handle_openai_error(e)
                error_audio_file = ErrorAudio
                self.ai_client.fallback_text_to_speech(error_message, error_audio_file)
                conversation_active = False

        self.display.fade_in_logo(SeamanLogo)
        self.audio_threadshold_calibration_done = False

    def check_buttons(self):
        inputs = self.serial_module.get_inputs()
        if inputs and 'result' in inputs:
            result = inputs['result']
            buttons = result['buttons']
            logger.info(f"result: {result}")
            logger.info(f"buttons: {buttons}")

            if buttons[1]:  # RIGHT button
                response = self.setting_menu.display_menu()
                if response:
                    return response
                time.sleep(0.2)
        return None, None

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

async def main():
    aiClient = OpenAIClient()
    await aiClient.initialize()

    parser = argparse.ArgumentParser()
    # Toshiba
    parser.add_argument('--vtdic', help='Path to Toshiba Voice Trigger dictionary file', default=ToshibaVoiceDictionary)
    parser.add_argument('--threshold', help='Threshold for keyword detection', type=int, default=600)
    
    # Pico
    parser.add_argument('--access_key', help='AccessKey for Porcupine', default=os.environ["PICO_ACCESS_KEY"])
    parser.add_argument('--keyword_paths', nargs='+', help="Paths to keyword model files", default=[PicoWakeWordSatoru])
    parser.add_argument('--model_path', help='Path to Porcupine model file', default=PicoLangModel)
    parser.add_argument('--sensitivities', nargs='+', help="Sensitivities for keywords", type=float, default=[0.5])

    # OpenAi
    parser.add_argument('--aiclient', help='Asynchronous openAi client', default=aiClient)

    args = parser.parse_args()

    assistant = VoiceAssistant(args)
    aiClient.setAudioPlayer(assistant.audioPlayer)

    try:
        assistant.audioPlayer.play_trigger_with_logo(TriggerAudio, SeamanLogo)

        while not exit_event.is_set():
            if assistant.listen_for_wake_word():
                await assistant.process_conversation()

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        await assistant.ai_client.close()
        assistant.cleanup()
        
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

    asyncio.run(main())
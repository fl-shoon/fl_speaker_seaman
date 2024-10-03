import os, logging, time, wave
import numpy as np
import asyncio
import signal
import argparse

from audio.playAudio import sync_audio_and_gif_async, play_audio
from audio.recorder import InteractiveRecorder
from display.display import DisplayModule
from etc.define import *
from openAI.chat import OpenAIModule
from pvrecorder import PvRecorder
from pico.pico import PicoVoiceTrigger
from threading import Event
from toshiba.toshiba import ToshibaVoiceTrigger, VTAPI_ParameterID
from transmission.serialModule import SerialModule

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
            
            if not self.serial_module.open(USBPort):
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
                    logger.info("Wake word detected")
                    if self.handle_audio_calibration():
                        play_audio(ResponseAudio)
                        return True
                    else:
                        logger.info("Calibration failed. Returning to wake word detection.")
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

            await self.display.start_listening_display_async(SatoruHappy)
            audio_data = await asyncio.to_thread(self.interactive_recorder.record_question, silence_duration=1.5, max_duration=30)

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

            await self.display.stop_listening_display_async()

            try:
                # Transcribe audio
                transcribed_text = await self.ai_client.transcribe_audio(input_audio_file)
                
                # Process the transcribed text and stream the response
                response_chunks = []
                async for chunk in self.ai_client.chat_async(transcribed_text):
                    response_chunks.append(chunk)
                    # Here you can perform any real-time processing if needed
                    
                full_response = ''.join(response_chunks)
                
                # Check if the conversation has ended
                conversation_ended = '[END_OF_CONVERSATION]' in full_response
                full_response = full_response.replace('[END_OF_CONVERSATION]', '').strip()
                
                # Generate speech from the full response
                response_audio_file = 'temp_response.wav'
                await self.ai_client.text_to_speech(full_response, response_audio_file)
                
                # Play the audio response and show the GIF
                await sync_audio_and_gif_async(self.display, response_audio_file, SpeakingGif)
                
                if conversation_ended:
                    conversation_active = False
                
            except Exception as e:
                logger.error(f"Error processing conversation: {e}")
                error_message = self.ai_client.handle_error(e)
                error_audio_file = ErrorAudio
                await asyncio.to_thread(self.ai_client.fallback_text_to_speech, error_message, error_audio_file)
                await sync_audio_and_gif_async(self.display, error_audio_file, SpeakingGif)
                conversation_active = False

        await self.display.display_image_async(SeamanLogo)
        self.audio_threshold_calibration_done = False

    async def run_async(self):
        try:
            self.initialize()
            await self.display.play_trigger_with_logo_async(TriggerAudio, SeamanLogo)

            while not exit_event.is_set():
                if await asyncio.to_thread(self.listen_for_wake_word):
                    await self.process_conversation()

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Shutting down...")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        finally:
            self.cleanup()

    def run(self):
        asyncio.run(self.run_async())

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
    logger.info(f"Received {signum} signal. Initiating graceful shutdown...")
    exit_event.set()

if __name__ == '__main__':
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
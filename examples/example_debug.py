import argparse
import logging
import signal
import wave
import time
import asyncio
import datetime
import numpy as np
import firebase_admin
from threading import Event
from firebase_admin import credentials, firestore

from openAI.conversation import OpenAIModule
from audio.player import sync_audio_and_gif, play_audio
from audio.recorder import record_audio
from display.show import DisplayModule
from etc.define import *
from pvrecorder import PvRecorder
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
        self.ai_client = None

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

class ScheduledVoiceAssistant(VoiceAssistant):
    def __init__(self, args):
        super().__init__(args)
        self.db = None 
        self.scheduled_time = None
    
    def initialize(self):
        super().initialize()
        self.init_fire()

    def init_fire(self):
        cred = credentials.Certificate(FIRE_CRED)
        firebase_admin.initialize_app(cred)
        self.db = firestore.client()
        self.db_ref = self.db.collection('schedulers').document('medicine_reminder_time')
        self.update_schedule()

    def update_schedule(self):
        try:
            self.schedule_data = self.db_ref.get().to_dict()
            scheduled_hour = self.schedule_data.get('hour')
            scheduled_minute = self.schedule_data.get('minute')
            now = datetime.datetime.now()
            self.scheduled_time = now.replace(hour=scheduled_hour, minute=scheduled_minute, second=0, microsecond=0)
            if self.scheduled_time <= now:
                self.scheduled_time += datetime.timedelta(days=1)
            logger.info(f"Next scheduled time set to: {self.scheduled_time}")
        except Exception as e:
            logger.error(f"Error updating schedule: {e}")
            self.scheduled_time = None

    async def check_schedule(self):
        while not exit_event.is_set():
            try:
                now = datetime.datetime.now()
                if self.scheduled_time is None:
                    logger.warning("No scheduled time set. Updating schedule...")
                    self.update_schedule()
                    await asyncio.sleep(60)
                    continue

                time_until_scheduled = (self.scheduled_time - now).total_seconds()
                
                if time_until_scheduled <= 0:
                    logger.info(f"Scheduled time reached. Current time: {now}, Scheduled time: {self.scheduled_time}")
                    self.update_schedule()  
                    return True
                else:
                    logger.info(f"Waiting for scheduled time. Current time: {now}, Scheduled time: {self.scheduled_time}, Time until scheduled: {time_until_scheduled:.2f} seconds")
                
                await asyncio.sleep(60)  
            except Exception as e:
                logger.error(f"Error in check_schedule: {e}")
                await asyncio.sleep(60)
        return False

    async def run(self):
        try:
            self.initialize()
            self.display.play_trigger_with_logo(TriggerAudio, SeamanLogo)

            while not exit_event.is_set():
                wake_word_task = asyncio.create_task(self.listen_for_wake_word_async())
                schedule_task = asyncio.create_task(self.check_schedule())

                done, pending = await asyncio.wait(
                    [wake_word_task, schedule_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()

                if wake_word_task in done and wake_word_task.result():
                    logger.info("Conversation started by wake word.")
                    self.process_conversation()  
                elif schedule_task in done and schedule_task.result():
                    logger.info("Conversation started by schedule.")
                    self.process_conversation()  
                else:
                    logger.warning("No task completed as expected. Restarting loop.")

        except Exception as e:
            logger.error(f"An unexpected error occurred in run: {e}", exc_info=True)
        finally:
            self.cleanup()

    async def listen_for_wake_word_async(self):
        return await asyncio.to_thread(self.listen_for_wake_word)

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

    # assistant = VoiceAssistant(args)
    # assistant.run()

    assistant = ScheduledVoiceAssistant(args)
    asyncio.run(assistant.run())
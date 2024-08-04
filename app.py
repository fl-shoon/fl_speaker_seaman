import argparse, wave, sys, signal
import numpy as np
import logging
from datetime import datetime

# Observer & Reactive Streaming
import asyncio
from concurrent.futures import ThreadPoolExecutor
from rx import operators as ops
from rx.subject import Subject
from rx.scheduler.eventloop import AsyncIOScheduler

# Serial/Display
from transmission.serialModule import SerialModule
from display.show import DisplayModule

# AI
from openAI.conversation import OpenAIModule

# Voice Trigger & Recording 
from toshiba.toshiba import ToshibaVoiceTrigger, VTAPI_ParameterID
from pvrecorder import PvRecorder 

# Audio
from audio.player import play_audio, sync_audio_and_gif
from audio.recorder import record_audio

# Variables
from etc.define import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

should_exit = asyncio.Event()

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    asyncio.get_event_loop().call_soon_threadsafe(should_exit.set)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

class KaiwaService:
    def __init__(self):
        self.wake_word_subject = Subject()
        self.conversation_subject = Subject()
        self.audio_subject = Subject()

        self.parser = argparse.ArgumentParser()
        self.parser.add_argument('--vtdic', help='Path to Toshiba Voice Trigger dictionary file', default=ToshibaVoiceDictionary)
        self.parser.add_argument('--threshold', help='Threshold for keyword detection', type=int, default=600)
        self.args = self.parser.parse_args()

        self.serial_module = SerialModule(BautRate)
        self.display = DisplayModule(self.serial_module)
        self.ai_client = OpenAIModule()

        self.vt = ToshibaVoiceTrigger(self.args.vtdic)
        self.vt.set_parameter(VTAPI_ParameterID.VTAPI_ParameterID_aThreshold, -1, self.args.threshold)

        self.recorder = PvRecorder(frame_length=self.vt.frame_size)
        self.loop = asyncio.get_event_loop()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.scheduler = AsyncIOScheduler(asyncio.get_event_loop())

    async def clean(self):
        logger.info("Cleaning up...")
        if self.recorder:
            await self.loop.run_in_executor(self.executor, self.recorder.stop)
            await self.loop.run_in_executor(self.executor, self.recorder.delete)
        if self.display:
            await self.loop.run_in_executor(self.executor, self.display.send_white_frames)
        if self.serial_module:
            await self.loop.run_in_executor(self.executor, self.serial_module.close)

    async def ensure_serial_connection(self):
        max_attempts = 5
        for attempt in range(max_attempts):
            if self.serial_module.isPortOpen:
                return True
            
            logger.info(f"Attempting to open serial port {USBPort} (Attempt {attempt + 1}/{max_attempts})...")
            if await self.loop.run_in_executor(self.executor, self.serial_module.open, USBPort):
                logger.info("Successfully opened serial connection.")
                return True
            
            if attempt < max_attempts - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.info(f"Failed to open serial port. Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
        
        logger.error(f"Failed to open serial port {USBPort} after {max_attempts} attempts.")
        return False

    async def listen_for_wake_word(self):
        while not should_exit.is_set():
            try:
                audio_frame = await self.loop.run_in_executor(self.executor, self.recorder.read)
                audio_data = np.array(audio_frame, dtype=np.int16)
                detections = await self.loop.run_in_executor(self.executor, self.vt.process, audio_data)
                if any(detections):
                    logger.info(f"Wake word detected at {datetime.now()}")
                    detected_keyword = detections.index(max(detections))
                    logger.info(f"Detected keyword: {detected_keyword}")
                    await self.loop.run_in_executor(self.executor, play_audio, ResponseAudio)
                    await asyncio.sleep(0.5)
                    return True
            except OSError as e:
                logger.error(f"Stream error: {e}. Reopening stream.")
                await self.loop.run_in_executor(self.executor, self.recorder.stop)
                self.recorder = PvRecorder(device_index=-1, frame_length=self.vt.frame_size)
                await self.loop.run_in_executor(self.executor, self.recorder.start)
        return False

    async def record_conversation(self):
        await self.ensure_serial_connection()
        await self.loop.run_in_executor(self.executor, self.display.start_listening_display, SatoruHappy)

        frames = await self.loop.run_in_executor(self.executor, record_audio, self.vt.frame_size)

        await self.ensure_serial_connection()
        await self.loop.run_in_executor(self.executor, self.display.stop_listening_display)

        if len(frames) < int(RATE / self.vt.frame_size * RECORD_SECONDS):
            logger.info("Recording was incomplete. Skipping processing.")
            return None

        await asyncio.sleep(0.1)

        with wave.open(AIOutputAudio, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))

        return AIOutputAudio

    async def process_audio(self, audio_file):
        response_file, conversation_ended = await self.loop.run_in_executor(
            self.executor, self.ai_client.process_audio, audio_file, AIOutputAudio)
        
        if response_file:
            await self.ensure_serial_connection()
            await self.loop.run_in_executor(
                self.executor, sync_audio_and_gif, self.display, response_file, SpeakingGif)
        
        return conversation_ended

    async def run(self):
        try:
            logger.info(f"Attempting to open serial port {USBPort} at {BautRate} baud...")
            if not await self.ensure_serial_connection():
                logger.error("Unable to establish serial connection. Exiting.")
                return
            logger.info("Serial port opened successfully.")

            await self.ensure_serial_connection()
            await self.loop.run_in_executor(self.executor, self.display.play_trigger_with_logo, TriggerAudio, SeamanLogo)

            while not should_exit.is_set():
                logger.info("Listening for wake word...")
                await self.loop.run_in_executor(self.executor, self.recorder.start)
                
                wake_word_detected = await self.listen_for_wake_word()
                if not wake_word_detected:
                    continue

                await self.ensure_serial_connection()
                await self.loop.run_in_executor(self.executor, self.ai_client.reset_conversation)
                
                conversation_active = True
                silence_count = 0
                max_silence = 2

                while conversation_active and not should_exit.is_set():
                    audio_file = await self.record_conversation()
                    if not audio_file:
                        conversation_active = False
                        continue

                    conversation_ended = await self.process_audio(audio_file)

                    if conversation_ended:
                        logger.info("AI has determined the conversation has ended.")
                        conversation_active = False
                    elif not self.ai_client.get_last_user_message().strip():
                        silence_count += 1
                        if silence_count >= max_silence:
                            logger.info("Maximum silence reached. Ending conversation.")
                            conversation_active = False
                    else:
                        silence_count = 0

                await self.ensure_serial_connection()
                await self.loop.run_in_executor(self.executor, self.display.fade_in_logo, SeamanLogo)   
                logger.info("Conversation ended. Returning to wake word detection.")
            
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
        finally:
            logger.info("Graceful shutdown initiated.")
            await self.clean()

async def main():
    kaiwa_service = KaiwaService()
    await kaiwa_service.run()

if __name__ == '__main__':
    asyncio.run(main())
import argparse, wave, numpy as np

# Observer & Reactive Streaming
import asyncio
from concurrent.futures import ThreadPoolExecutor
from rx import operators as ops
from rx.subject import Subject

# Serial/Display
from display.show import DisplayModule

# AI
from openAI.conversation import OpenAIModule

# Voice Trigger & Recording 
from toshiba.toshiba import ToshibaVoiceTrigger, VTAPI_ParameterID
from pvrecorder import PvRecorder 

# Variables
from etc.define import *

class KaiwaService:
    def __init__(self):
        self.wake_word_subject = Subject()
        self.conversation_subject = Subject()
        self.audio_subject = Subject()

        self.parser = argparse.ArgumentParser()
        self.args = self.parser.parse_args()

        self.aiClient = OpenAIModule()

        self.displayClient = DisplayModule()

        self.vt = ToshibaVoiceTrigger(self.args.vtdic)

        self.recorder = PvRecorder(device_index=-1, frame_length=self.vt.frame_size)
        self.loop = asyncio.get_event_loop()
        self.executor = ThreadPoolExecutor(max_workers=1)

    def wake_word_detected(self):
        self.wake_word_subject.on_next(True)

    def start_conversation(self, audio_data):
        self.conversation_subject.on_next(audio_data)

    def process_audio(self, audio_data):
        self.audio_subject.on_next(audio_data)

    async def listen_for_wake_word(self):
        while True:
            try:
                audio_frame = await self.loop.run_in_executor(self.executor, self.recorder.read)
                audio_data = np.array(audio_frame, dtype=np.int16)
                detections = self.vt.process(audio_data)
                if any(detections):
                    self.wake_word_detected()
                    break
            except Exception as e:
                print(f"Error in wake word detection: {e}")
                await asyncio.sleep(0.1)

    async def record_audio(self):
        frames = []
        for _ in range(0, int(RATE / self.vt.frame_size * RECORD_SECONDS)):
            try:
                data = await self.loop.run_in_executor(self.executor, self.recorder.read)
                frames.append(data)
            except Exception as e:
                print(f"Error in audio recording: {e}")
                break
        return frames

    async def run(self):
        while True:
            print("Listening for wake word...")
            await self.listen_for_wake_word()
            
            print("Wake word detected! Starting conversation...")
            frames = await self.record_audio()
            
            if len(frames) < int(RATE / self.vt.frame_size * RECORD_SECONDS):
                print("Recording was incomplete. Skipping processing.")
                continue

            with wave.open(AIOutputAudio, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(RATE)
                wf.writeframes(b''.join(frames))

            self.process_audio(AIOutputAudio)

async def main():
    kaiwa_service = KaiwaService()
    display = kaiwa_service.displayClient
    aiClient = kaiwa_service.aiClient

    def process_audio_sync(audio_file):
        # This function runs in a separate thread
        response_file, conversation_ended = aiClient.process_audio(audio_file)
        if response_file:
            display.sync_audio_and_gif(response_file, SpeakingGif)
        return conversation_ended

    # Set up wake word detection
    wake_word_subscription = kaiwa_service.wake_word_subject.subscribe(
        on_next=lambda _: print("Wake word detected!")
    )

    # Set up audio processing
    audio_subscription = kaiwa_service.audio_subject.pipe(
        ops.map(lambda audio: asyncio.run_coroutine_threadsafe(
            kaiwa_service.loop.run_in_executor(None, process_audio_sync, audio),
            kaiwa_service.loop
        )),
        ops.map(lambda future: future.result()),
    ).subscribe(
        on_next=lambda conversation_ended: print("Conversation ended." if conversation_ended else "Continuing conversation...")
    )

    await kaiwa_service.run()

if __name__ == '__main__':
    asyncio.run(main())
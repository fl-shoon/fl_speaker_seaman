import os
import re
import pygame
import json
import logging
import wave
import asyncio
import aiohttp
from typing import List, Dict, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pyaudio
import webrtcvad 
from contextlib import contextmanager
from pygame import mixer
from threading import Event

RATE = 16000
CHANNELS = 1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

exit_event = Event()

@contextmanager
def suppress_stdout_stderr():
    """A context manager that redirects stdout and stderr to devnull"""
    try:
        null = os.open(os.devnull, os.O_RDWR)
        save_stdout, save_stderr = os.dup(1), os.dup(2)
        os.dup2(null, 1)
        os.dup2(null, 2)
        yield
    finally:
        os.dup2(save_stdout, 1)
        os.dup2(save_stderr, 2)
        os.close(null)

ERROR_HANDLER_FUNC = lambda type, handle, errno, reason: logger.debug(f"ALSA Error: {reason}")
ERROR_HANDLER_FUNC_PTR = ERROR_HANDLER_FUNC

class InteractiveRecorder:
    def __init__(self, vad_aggressiveness): 
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.stream = None
        self.CHUNK_DURATION_MS = 30  
        self.CHUNK_SIZE = int(RATE * self.CHUNK_DURATION_MS / 1000)

        self.p = None
        self.init_pyaudio()

    def init_pyaudio(self):
        with suppress_stdout_stderr():
            self.p = pyaudio.PyAudio()
        try:
            asound = self.p._lib_pa.pa_get_library_by_name('libasound.so.2')
            asound.snd_lib_error_set_handler(ERROR_HANDLER_FUNC_PTR)
        except:
            logger.warning("Failed to set ALSA error handler")

    def start_stream(self):
        with suppress_stdout_stderr():
            self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=CHANNELS,
                                  rate=RATE,
                                  input=True,
                                  frames_per_buffer=self.CHUNK_SIZE)

    def stop_stream(self):
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def record_question(self, silence_threshold=0.02, silence_duration=1.5, max_duration=5):
        self.start_stream()
        logger.info("Listening... Speak your question.")

        frames = []
        silent_frames = 0
        is_speaking = False
        speech_frames = 0
        total_frames = 0
        
        consecutive_speech_frames = 2
        initial_silence_duration = 5

        max_silent_frames = int(silence_duration * RATE / self.CHUNK_SIZE) 

        while True:
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            total_frames += 1

            audio_chunk = np.frombuffer(data, dtype=np.int16)
            audio_level = np.abs(audio_chunk).mean() / 32767 

            try:
                is_speech = self.vad.is_speech(data, RATE)
            except Exception as e:
                logger.error(f"VAD error: {e}")
                is_speech = False

            if is_speech or audio_level > silence_threshold:
                speech_frames += 1
                silent_frames = 0
                if not is_speaking and speech_frames > consecutive_speech_frames:
                    logger.info("Speech detected. Recording...")
                    is_speaking = True
            else: 
                silent_frames += 1
                speech_frames = max(0, speech_frames - 1)

            if is_speaking:
                if silent_frames > max_silent_frames:
                    logger.info(f"End of speech detected. Total frames: {total_frames}")
                    break
            elif total_frames > initial_silence_duration * RATE / self.CHUNK_SIZE:  
                logger.info("No speech detected. Stopping recording.")
                return None

            if total_frames > max_duration * RATE / self.CHUNK_SIZE:
                logger.info(f"Maximum duration reached. Total frames: {total_frames}")
                break

        self.stop_stream()
        return b''.join(frames) 

    def __del__(self):
        self.stop_stream()
        if self.p:
            self.p.terminate()

class AIAssistantService:
    def __init__(self): 
        self.interactive_recorder = InteractiveRecorder(vad_aggressiveness=3)
        self.ai_client = OpenAIClient()
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
        with suppress_stdout_stderr():
            self.p = pyaudio.PyAudio()
            pygame.init()
            mixer.init()
        self.is_playing = False

    def play_audio(self, filename):
        with suppress_stdout_stderr():
            mixer.music.load(filename)
            mixer.music.play()
            mixer.music.set_volume(0.5)
        self.is_playing = True
        while mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        self.is_playing = False

    async def process_conversation(self):
        conversation_active = True
        silence_count = 0
        max_silence = 2

        while conversation_active and not exit_event.is_set():
            while self.is_playing:
                await asyncio.sleep(0.1)

            await asyncio.sleep(0.5)
            audio_data = self.interactive_recorder.record_question(silence_duration=1.5, max_duration=30)

            if not audio_data:
                silence_count += 1
                if silence_count >= max_silence:
                    logger.info("Maximum silence reached. Ending conversation.")
                    conversation_active = False
                continue
            else:
                silence_count = 0

            input_audio_file = 'assets/output.wav'
            with wave.open(input_audio_file, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(RATE)
                wf.writeframes(audio_data)

            try:
                response_file, conversation_ended = await self.ai_client.process_audio(input_audio_file)
                if response_file:
                    await asyncio.to_thread(self.play_audio, response_file)
                    if conversation_ended:
                        conversation_active = False
                else:
                    logger.info("No response generated. Ending conversation.")
                    conversation_active = False
            except Exception as e:
                logger.error(f"Error processing conversation: {e}")
                error_message = self.ai_client.handle_openai_error(e)
                error_audio_file = "assets/error_audio.wav"
                self.ai_client.fallback_text_to_speech(error_message, error_audio_file)
                await asyncio.to_thread(self.play_audio, error_audio_file)
                conversation_active = False

        logger.info("Conversation ended.")

class OpenAIClient:
    def __init__(self):
        self.api_key = os.environ["OPENAI_API_KEY"]
        self.conversation_history: List[Dict[str, str]] = []
        self.max_retries = 3
        self.retry_delay = 5
        self.session = None
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def setup(self):
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
        self.executor.shutdown()

    async def stream_api_call(self, endpoint: str, payload: Dict, files: Dict = None) -> AsyncGenerator[bytes, None]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"https://api.openai.com/v1/{endpoint}"

        if files:
            data = aiohttp.FormData()
            for key, value in payload.items():
                data.add_field(key, str(value))
            for key, (filename, file) in files.items():
                data.add_field(key, file, filename=filename)
            async with self.session.post(url, data=data, headers=headers) as response:
                async for chunk in response.content.iter_chunks():
                    yield chunk[0]
        else:
            async with self.session.post(url, json=payload, headers=headers) as response:
                async for chunk in response.content.iter_chunks():
                    yield chunk[0]

    async def chat(self, new_message: str) -> AsyncGenerator[str, None]:
        if not self.conversation_history:
            self.conversation_history = [
                {"role": "system", "content": """あなたは役立つアシスタントです。日本語で返答してください。
                        ユーザーが薬を飲んだかどうか一度だけ確認してください。確認後は、他の話題に移ってください。
                        会話が自然に終了したと判断した場合は、返答の最後に '[END_OF_CONVERSATION]' というタグを付けてください。
                        ただし、ユーザーがさらに質問や話題を提供する場合は会話を続けてください。"""}
            ]

        self.conversation_history.append({"role": "user", "content": new_message})

        payload = {
            "model": "gpt-4",
            "messages": self.conversation_history,
            "temperature": 0.75,
            "max_tokens": 500,
            "stream": True
        }

        full_response = ""
        buffer = ""
        async for chunk in self.stream_api_call("chat/completions", payload):
            buffer += chunk.decode('utf-8')
            while True:
                try:
                    split_index = buffer.index('\n\n')
                    line = buffer[:split_index].strip()
                    buffer = buffer[split_index + 2:]
                    
                    if line.startswith("data: "):
                        if line == "data: [DONE]":
                            break
                        json_str = line[6:] 
                        chunk_data = json.loads(json_str)
                        content = chunk_data['choices'][0]['delta'].get('content', '')
                        if content:
                            full_response += content
                            yield content
                except ValueError:  
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    logger.error(f"Problematic JSON string: {json_str}")
                    break

        self.conversation_history.append({"role": "assistant", "content": full_response})

        if len(self.conversation_history) > 11:
            self.conversation_history = self.conversation_history[:1] + self.conversation_history[-10:]

    async def transcribe_audio(self, audio_file_path: str) -> AsyncGenerator[str, None]:
        with open(audio_file_path, "rb") as audio_file:
            files = {"file": ("audio.wav", audio_file)}
            payload = {"model": "whisper-1", "response_format": "text", "language": "ja"}
            
            full_transcript = ""
            async for chunk in self.stream_api_call("audio/transcriptions", payload, files):
                transcript_chunk = chunk.decode('utf-8')
                full_transcript += transcript_chunk
                yield transcript_chunk

        logger.info(f"Full transcript: {full_transcript}")

    async def text_to_speech(self, text: str, output_file: str):
        payload = {"model": "tts-1-hd", "voice": "nova", "input": text, "response_format": "wav"}
        
        with open(output_file, "wb") as f:
            async for chunk in self.stream_api_call("audio/speech", payload):
                f.write(chunk)

        logger.info(f'Audio content written to file "{output_file}"')

    async def process_audio(self, input_audio_file: str) -> tuple[str, bool]:
        try:
            base, ext = os.path.splitext(input_audio_file)
            output_audio_file = f"{base}_response{ext}"

            # Transcribe audio (STT)
            full_transcript = ""
            async for transcript_chunk in self.transcribe_audio(input_audio_file):
                full_transcript += transcript_chunk

            logger.info(f"Full Transcript: {full_transcript}")

            # Generate response (Chat)
            full_response = ""
            async for response_chunk in self.chat(full_transcript):
                full_response += response_chunk

            conversation_ended = '[END_OF_CONVERSATION]' in full_response
            full_response = full_response.replace('[END_OF_CONVERSATION]', '').strip()

            logger.info(f"AI response: {full_response}")
            logger.info(f"Conversation ended: {conversation_ended}")

            # Generate speech (TTS)
            await self.text_to_speech(full_response, output_audio_file)

            return output_audio_file, conversation_ended

        except Exception as e:
            logger.error(f"Error in process_audio: {e}")
            error_message = await self.handle_openai_error(e)
            output_audio_file = "assets/error_audio.wav"
            self.fallback_text_to_speech(error_message, output_audio_file)
            return output_audio_file, True

    async def handle_openai_error(self, e: Exception) -> str:
        logger.error(f"OpenAI API error: {e}")
        return "申し訳ありませんが、エラーが発生しました。"

    def fallback_text_to_speech(self, text: str, output_file: str):
        duration = 1
        frequency = 440
        sample_rate = 44100

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = np.sin(2 * np.pi * frequency * t)
        audio = (audio * 32767).astype(np.int16)

        with wave.open(output_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())

        logger.warning(f"Fallback TTS used. Original message: {text}")
        logger.info(f"Fallback audio saved to {output_file}")

async def main():
    assistant = AIAssistantService()
    await assistant.ai_client.setup()
    
    try:
        while not exit_event.is_set():
            await assistant.process_conversation()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Shutting down...")
        exit_event.set()
    finally:
        await assistant.ai_client.close()

if __name__ == "__main__":
    asyncio.run(main())
import os
import json
import wave
import aiohttp
from typing import List, Dict, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

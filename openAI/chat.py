import os, logging, time, wave, asyncio
import numpy as np
from typing import List, Dict, AsyncGenerator
from openai import AsyncOpenAI, OpenAIError
from etc.define import ErrorAudio

logging.basicConfig(level=logging.INFO)

class OpenAIModule:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.conversation_history: List[Dict[str, str]] = []
        self.max_retries = 3
        self.retry_delay = 5

    async def transcribe_audio(self, audio_file_path: str) -> str:
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcript = await self.client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file, 
                    response_format="text",
                    language="ja"
                )
            return transcript
        except OpenAIError as e:
            logging.error(f"Error in transcribe_audio: {e}")
            raise

    async def chat_async(self, new_message: str) -> AsyncGenerator[str, None]:
        for attempt in range(self.max_retries):
            try:
                if not self.conversation_history:
                    self.conversation_history = [
                        {"role": "system", "content": """あなたは役立つアシスタントです。日本語で返答してください。
                        ユーザーが薬を飲んだかどうか一度だけ確認してください。確認後は、他の話題に移ってください。
                        会話が自然に終了したと判断した場合は、返答の最後に '[END_OF_CONVERSATION]' というタグを付けてください。
                        ただし、ユーザーがさらに質問や話題を提供する場合は会話を続けてください。"""}
                    ]

                self.conversation_history.append({"role": "user", "content": new_message})

                stream = await self.client.chat.completions.create(
                    model="gpt-4",
                    messages=self.conversation_history,
                    temperature=0.75,
                    max_tokens=500,
                    stream=True
                )

                full_response = ""
                async for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield content

                self.conversation_history.append({"role": "assistant", "content": full_response})

                if len(self.conversation_history) > 11:
                    self.conversation_history = self.conversation_history[:1] + self.conversation_history[-10:]

                return
            except OpenAIError as e:
                if e.code == 'insufficient_quota':
                    logging.error("OpenAI API quota exceeded. Please check your plan and billing details.")
                    yield "申し訳ありません。現在システムに問題が発生しています。後でもう一度お試しください。"
                    return
                elif e.code == 'rate_limit_exceeded':
                    if attempt < self.max_retries - 1:
                        logging.warning(f"Rate limit exceeded. Retrying in {self.retry_delay} seconds...")
                        await asyncio.sleep(self.retry_delay)
                    else:
                        logging.error("Max retries reached. Unable to complete the request.")
                        yield "申し訳ありません。しばらくしてからもう一度お試しください。"
                        return
                else:
                    logging.error(f"OpenAI API error: {e}")
                    yield "申し訳ありません。エラーが発生しました。"
                    return

    async def text_to_speech(self, text: str, output_file: str):
        try:
            response = await self.client.audio.speech.create(
                model="tts-1-hd",
                voice="nova",
                input=text,
                response_format="wav",
            )

            with open(output_file, "wb") as f:
                async for chunk in response.iter_bytes(chunk_size=4096):
                    f.write(chunk)
        except OpenAIError as e:
            logging.error(f"Failed to generate speech: {e}")
            self.fallback_text_to_speech(text, output_file)

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

        logging.warning(f"Fallback TTS used. Original message: {text}")
        logging.info(f"Fallback audio saved to {output_file}")

    def handle_error(self, e: Exception) -> str:
        if isinstance(e, OpenAIError):
            if getattr(e, 'code', None) == 'insufficient_quota':
                logging.error("OpenAI API quota exceeded. Please check your plan and billing details.")
                return "申し訳ありませんが、システムに一時的な問題が発生しています。後ほど再度お試しください。ただいまシステムを終了します。"
            elif getattr(e, 'code', None) == 'rate_limit_exceeded':
                logging.warning(f"Rate limit exceeded. Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
                return "少々お待ちください。システムが混み合っています。"
            else:
                logging.error(f"OpenAI API error: {e}")
                return "申し訳ありませんが、エラーが発生しました。ただいまシステムを終了します。"
        else:
            logging.error(f"Unexpected error: {str(e)}")
            return "申し訳ありませんが、予期せぬエラーが発生しました。ただいまシステムを終了します。"
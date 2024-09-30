import os, logging, time, wave, asyncio
import numpy as np
from typing import List, Dict
from openai import AsyncOpenAI, OpenAIError
from etc.define import ErrorAudio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIModule:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.conversation_history: List[Dict[str, str]] = []
        self.max_retries = 3
        self.retry_delay = 5
        self.tts_cache = {}

    async def generate_text(self, prompt: str) -> str:
        response = await self.client.completions.create(
            model="gpt-4",
            prompt=prompt,
            max_tokens=500,
            temperature=0.75,
        )
        return response.choices[0].text.strip()

    async def chat(self, new_message: str) -> str:
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

                response = await self.client.chat.completions.create(
                    model="gpt-4",
                    messages=self.conversation_history,
                    temperature=0.75,
                    max_tokens=500
                )
                ai_message = response.choices[0].message.content
                self.conversation_history.append({"role": "assistant", "content": ai_message})

                if len(self.conversation_history) > 11:
                    self.conversation_history = self.conversation_history[:1] + self.conversation_history[-10:]

                return ai_message
            except OpenAIError as e:
                if attempt < self.max_retries - 1:
                    logging.warning(f"OpenAI API error: {e}. Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    return self.handle_openai_error(e)

    async def transcribe_audio(self, audio_file_path: str) -> str:
        with open(audio_file_path, "rb") as audio_file:
            transcript = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
                language="ja"
            )
        return transcript

    async def text_to_speech(self, text: str, output_file: str):
        if text in self.tts_cache:
            with open(output_file, "wb") as f:
                f.write(self.tts_cache[text])
            return

        try:
            response = await self.client.audio.speech.create(
                model="tts-1-hd",
                voice="nova",
                input=text
            )

            audio_data = await response.read()
            with open(output_file, "wb") as f:
                f.write(audio_data)

            self.tts_cache[text] = audio_data
        except OpenAIError as e:
            logging.error(f"Failed to generate speech: {e}")
            await self.fallback_text_to_speech(text, output_file)

    async def process_audio(self, input_audio_file: str) -> tuple[str, bool]:
        try:
            base, ext = os.path.splitext(input_audio_file)
            output_audio_file = f"{base}_response{ext}"

            stt_text = await self.transcribe_audio(input_audio_file)
            logging.info(f"Transcript: {stt_text}")

            content_response = await self.chat(stt_text)
            conversation_ended = '[END_OF_CONVERSATION]' in content_response
            content_response = content_response.replace('[END_OF_CONVERSATION]', '').strip()

            logging.info(f"AI response: {content_response}")
            logging.info(f"Conversation ended: {conversation_ended}")

            await self.text_to_speech(content_response, output_audio_file)
            logging.info(f'Audio content written to file "{output_audio_file}"')

            return output_audio_file, conversation_ended

        except OpenAIError as e:
            error_message = self.handle_openai_error(e)
            output_audio_file = ErrorAudio
            await self.text_to_speech(error_message, output_audio_file)
            return output_audio_file, True

    def handle_openai_error(self, e: OpenAIError) -> str:
        if isinstance(e, OpenAIError):
            if e.code == 'insufficient_quota':
                logging.error("OpenAI API quota exceeded. Please check your plan and billing details.")
                return "申し訳ありませんが、システムに一時的な問題が発生しています。後ほど再度お試しください。ただいまシステムを終了します。"
            elif e.code == 'rate_limit_exceeded':
                logging.warning(f"Rate limit exceeded. Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
                return "少々お待ちください。システムが混み合っています。"
            else:
                logging.error(f"OpenAI API error: {e}")
                return "申し訳ありませんが、エラーが発生しました。ただいまシステムを終了します。"
        else:
            logging.error(f"Unexpected error: {e}")
            return "予期せぬエラーが発生しました。ただいまシステムを終了します。"

    async def fallback_text_to_speech(self, text: str, output_file: str):
        # Generate a simple beep sound
        duration = 1  # seconds
        frequency = 440  # Hz (A4 note)
        sample_rate = 44100  # standard sample rate

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = np.sin(2 * np.pi * frequency * t)
        audio = (audio * 32767).astype(np.int16)

        # Write the audio data to a WAV file
        with wave.open(output_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())

        logging.warning(f"Fallback TTS used. Original message: {text}")
        logging.info(f"Fallback audio saved to {output_file}")

# import os, logging, time, wave
# import numpy as np
# from typing import List, Dict
# from openai import OpenAI, OpenAIError
# from etc.define import ErrorAudio

# logging.basicConfig(level=logging.INFO)

# class OpenAIModule:
#     def __init__(self):
#         self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
#         self.conversation_history: List[Dict[str, str]] = []
#         self.max_retries = 3
#         self.retry_delay = 5 

#     def generate_text(self, prompt: str) -> str:
#         response = self.client.completions.create(
#             model="gpt-4",  
#             prompt=prompt,
#             max_tokens=500,
#             temperature=0.75,
#         )
#         return response.choices[0].text.strip()

#     def embed_content(self, text: str) -> List[float]:
#         response = self.client.embeddings.create(
#             input=text,
#             model="text-embedding-ada-002"
#         )
#         return response.data[0].embedding

#     def chat(self, new_message: str) -> str:
#         for attempt in range(self.max_retries):
#             try:
#                 if not self.conversation_history:
#                     self.conversation_history = [
#                         {"role": "system", "content": """あなたは役立つアシスタントです。日本語で返答してください。
#                         ユーザーが薬を飲んだかどうか一度だけ確認してください。確認後は、他の話題に移ってください。
#                         会話が自然に終了したと判断した場合は、返答の最後に '[END_OF_CONVERSATION]' というタグを付けてください。
#                         ただし、ユーザーがさらに質問や話題を提供する場合は会話を続けてください。"""}
#                     ]

#                 self.conversation_history.append({"role": "user", "content": new_message})

#                 response = self.client.chat.completions.create(
#                     model="gpt-4",
#                     messages=self.conversation_history,
#                     temperature=0.75,
#                     max_tokens=500
#                 )
#                 ai_message = response.choices[0].message.content
#                 self.conversation_history.append({"role": "assistant", "content": ai_message})

#                 # Limit conversation history to last 10 messages to prevent token limit issues
#                 if len(self.conversation_history) > 11:  # 11 to keep the system message
#                     self.conversation_history = self.conversation_history[:1] + self.conversation_history[-10:]

#                 return ai_message
#             except OpenAIError as e:
#                 if e.code == 'insufficient_quota':
#                     logging.error("OpenAI API quota exceeded. Please check your plan and billing details.")
#                     return "申し訳ありません。現在システムに問題が発生しています。後でもう一度お試しください。"
#                 elif e.code == 'rate_limit_exceeded':
#                     if attempt < self.max_retries - 1:
#                         logging.warning(f"Rate limit exceeded. Retrying in {self.retry_delay} seconds...")
#                         time.sleep(self.retry_delay)
#                     else:
#                         logging.error("Max retries reached. Unable to complete the request.")
#                         return "申し訳ありません。しばらくしてからもう一度お試しください。"
#                 else:
#                     logging.error(f"OpenAI API error: {e}")
#                     return "申し訳ありません。エラーが発生しました。"

#     def transcribe_audio(self, audio_file_path: str) -> str:
#         with open(audio_file_path, "rb") as audio_file:
#             transcript = self.client.audio.transcriptions.create(
#                 model="whisper-1", 
#                 file=audio_file, 
#                 response_format="text",
#                 language="ja"
#             )
#         return transcript

#     def text_to_speech(self, text: str, output_file: str):
#         try:
#             response = self.client.audio.speech.create(
#                 model="tts-1-hd",
#                 voice="nova",
#                 input=text,
#                 response_format="wav",
#             )

#             with open(output_file, "wb") as f:
#                 for chunk in response.iter_bytes(chunk_size=4096):
#                     f.write(chunk)
#         except OpenAIError as e:
#             logging.error(f"Failed to generate speech: {e}")
#             self.fallback_text_to_speech(text, output_file)

#     def reset_conversation(self):
#         self.conversation_history = [
#             {"role": "system", "content": """あなたは役立つアシスタントです。日本語で返答してください。
#             ユーザーが薬を飲んだかどうか一度だけ確認してください。確認後は、他の話題に移ってください。
#             会話が自然に終了したと判断した場合は、返答の最後に '[END_OF_CONVERSATION]' というタグを付けてください。
#             ただし、ユーザーがさらに質問や話題を提供する場合は会話を続けてください。"""}
#         ]

#     def get_last_user_message(self):
#         for message in reversed(self.conversation_history):
#             if message["role"] == "user":
#                 return message["content"]
#         return ""

#     def process_audio(self, input_audio_file: str) -> tuple[str, bool]:
#         try:
#             # Generate output filename
#             base, ext = os.path.splitext(input_audio_file)
#             output_audio_file = f"{base}_response{ext}"

#             # Speech-to-Text
#             stt_text = self.transcribe_audio(input_audio_file)
#             logging.info(f"Transcript: {stt_text}")

#             # Generate content using OpenAI
#             content_response = self.chat(stt_text)
#             conversation_ended = '[END_OF_CONVERSATION]' in content_response
#             content_response = content_response.replace('[END_OF_CONVERSATION]', '').strip()

#             logging.info(f"AI response: {content_response}")
#             logging.info(f"Conversation ended: {conversation_ended}")

#             # Text-to-Speech
#             self.text_to_speech(content_response, output_audio_file)
#             logging.info(f'Audio content written to file "{output_audio_file}"')

#             return output_audio_file, conversation_ended

#         except OpenAIError as e:
#             error_message = self.handle_openai_error(e)
#             output_audio_file = ErrorAudio
#             self.text_to_speech(error_message, output_audio_file)
#             return output_audio_file, True

#     def handle_openai_error(self, e: OpenAIError) -> str:
#         if e.code == 'insufficient_quota':
#             logging.error("OpenAI API quota exceeded. Please check your plan and billing details.")
#             return "申し訳ありませんが、システムに一時的な問題が発生しています。後ほど再度お試しください。ただいまシステムを終了します。"
#         elif e.code == 'rate_limit_exceeded':
#             logging.warning(f"Rate limit exceeded. Retrying in {self.retry_delay} seconds...")
#             time.sleep(self.retry_delay)
#             return "少々お待ちください。システムが混み合っています。"
#         else:
#             logging.error(f"OpenAI API error: {e}")
#             return "申し訳ありませんが、エラーが発生しました。ただいまシステムを終了します。"
        
#     def fallback_text_to_speech(self, text: str, output_file: str):
#         # Generate a simple beep sound
#         duration = 1  # seconds
#         frequency = 440  # Hz (A4 note)
#         sample_rate = 44100  # standard sample rate

#         t = np.linspace(0, duration, int(sample_rate * duration), False)
#         audio = np.sin(2 * np.pi * frequency * t)
#         audio = (audio * 32767).astype(np.int16)

#         # Write the audio data to a WAV file
#         with wave.open(output_file, 'wb') as wf:
#             wf.setnchannels(1)
#             wf.setsampwidth(2)
#             wf.setframerate(sample_rate)
#             wf.writeframes(audio.tobytes())

#         logging.warning(f"Fallback TTS used. Original message: {text}")
#         logging.info(f"Fallback audio saved to {output_file}")
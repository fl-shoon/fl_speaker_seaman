import os, logging, time
from typing import List, Dict
from openai import OpenAI, OpenAIError
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIModule:
    def __init__(self):
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.conversation_history: List[Dict[str, str]] = []

    def generate_text(self, prompt: str) -> str:
        response = self.client.completions.create(
            model="gpt-3.5-turbo-instruct",  
            prompt=prompt,
            max_tokens=100,
            temperature=0.75,
        )
        return response.choices[0].text.strip()

    def embed_content(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding

    def chat(self, new_message: str) -> str:
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                if not self.conversation_history:
                    self.conversation_history = [
                        {"role": "system", "content": """あなたは役立つアシスタントです。日本語で返答してください。
                        ユーザーが薬を飲んだかどうか一度だけ確認してください。確認後は、他の話題に移ってください。
                        会話が自然に終了したと判断した場合は、返答の最後に '[END_OF_CONVERSATION]' というタグを付けてください。
                        ただし、ユーザーがさらに質問や話題を提供する場合は会話を続けてください。"""}
                    ]

                self.conversation_history.append({"role": "user", "content": new_message})

                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=self.conversation_history,
                    temperature=0.75,
                    max_tokens=500
                )
                ai_message = response.choices[0].message.content
                self.conversation_history.append({"role": "assistant", "content": ai_message})

                # Limit conversation history to last 10 messages to prevent token limit issues
                if len(self.conversation_history) > 11:  # 11 to keep the system message
                    self.conversation_history = self.conversation_history[:1] + self.conversation_history[-10:]

                return ai_message
            except OpenAIError as e:
                if e.code == 'insufficient_quota':
                    logging.error("OpenAI API quota exceeded. Please check your plan and billing details.")
                    return "申し訳ありません。現在システムに問題が発生しています。後でもう一度お試しください。"
                elif e.code == 'rate_limit_exceeded':
                    if attempt < max_retries - 1:
                        logging.warning(f"Rate limit exceeded. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        logging.error("Max retries reached. Unable to complete the request.")
                        return "申し訳ありません。しばらくしてからもう一度お試しください。"
                else:
                    logging.error(f"OpenAI API error: {e}")
                    return "申し訳ありません。エラーが発生しました。"

    def transcribe_audio(self, audio_file_path: str) -> str:
        with open(audio_file_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file, 
                response_format="text",
                language="ja"
            )
        return transcript

    def text_to_speech(self, text: str, output_file: str):
        response = self.client.audio.speech.create(
            model="tts-1-hd",
            voice="nova",
            input=text,
            response_format="wav",
        )

        with open(output_file, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=4096):
                f.write(chunk)

    def reset_conversation(self):
        self.conversation_history = [
            {"role": "system", "content": """あなたは役立つアシスタントです。日本語で返答してください。
            ユーザーが薬を飲んだかどうか一度だけ確認してください。確認後は、他の話題に移ってください。
            会話が自然に終了したと判断した場合は、返答の最後に '[END_OF_CONVERSATION]' というタグを付けてください。
            ただし、ユーザーがさらに質問や話題を提供する場合は会話を続けてください。"""}
        ]

    def get_last_user_message(self):
        for message in reversed(self.conversation_history):
            if message["role"] == "user":
                return message["content"]
        return ""

    def process_audio(self, audio_file: str, output_file: str) -> tuple[str, bool]:
        # Speech-to-Text
        stt_text = self.transcribe_audio(audio_file)
        print(f"Transcript: {stt_text}")

        # Generate content using OpenAI
        content_response = self.chat(stt_text)
        conversation_ended = '[END_OF_CONVERSATION]' in content_response
        content_response = content_response.replace('[END_OF_CONVERSATION]', '').strip()

        print(f"AI response: {content_response}")
        print(f"Conversation ended: {conversation_ended}")

        # Text-to-Speech
        self.text_to_speech(content_response, output_file)
        print(f'Audio content written to file "{output_file}"')

        return output_file, conversation_ended
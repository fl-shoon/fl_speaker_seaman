import pyaudio
import wave
from openai import OpenAI
import os
import threading
import queue
import time

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Global variables
audio_queue = queue.Queue()
is_recording = True
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "temp_audio.wav"
MP3_OUTPUT_FILENAME = "temp_audio.mp3"
WAKE_WORD = "こんにちは"

def record_audio():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("* Recording continuously. Press Ctrl+C to stop.")

    while is_recording:
        frames = []
        for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK)
            frames.append(data)
        audio_queue.put(frames)

    stream.stop_stream()
    stream.close()
    p.terminate()

def save_audio(frames, filename):
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(pyaudio.PyAudio().get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

def transcribe_audio(audio_file):
    with open(audio_file, "rb") as file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=file
        )
    return transcript.text

def check_wake_word(transcript):
    return WAKE_WORD.lower() in transcript.lower()

def process_audio():
    while is_recording:
        if not audio_queue.empty():
            frames = audio_queue.get()
            save_audio(frames, WAVE_OUTPUT_FILENAME)
            transcript = transcribe_audio(WAVE_OUTPUT_FILENAME)
            # print(f"Transcript: {transcript}")
            
            if check_wake_word(transcript):
                print(f"Wake word '{WAKE_WORD}' detected!")
            
            os.remove(WAVE_OUTPUT_FILENAME)
        time.sleep(0.1)

def main():
    global is_recording

    record_thread = threading.Thread(target=record_audio)
    process_thread = threading.Thread(target=process_audio)

    record_thread.start()
    process_thread.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Stopping recording...")
        is_recording = False

    record_thread.join()
    process_thread.join()

if __name__ == "__main__":
    main()
# import pyaudio
# import wave
# from openai import OpenAI
# import os
# from pydub import AudioSegment
# import threading
# import queue
# import time

# client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# # Global variables
# audio_queue = queue.Queue()
# is_recording = True
# CHUNK = 1024
# FORMAT = pyaudio.paInt16
# CHANNELS = 1
# RATE = 16000
# RECORD_SECONDS = 5
# WAVE_OUTPUT_FILENAME = "temp_audio.wav"
# MP3_OUTPUT_FILENAME = "temp_audio.mp3"
# WAKE_WORD = "こんにちは"

# def record_audio():
#     p = pyaudio.PyAudio()
#     stream = p.open(format=FORMAT,
#                     channels=CHANNELS,
#                     rate=RATE,
#                     input=True,
#                     frames_per_buffer=CHUNK)

#     print("* Recording continuously. Press Ctrl+C to stop.")

#     while is_recording:
#         frames = []
#         for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
#             data = stream.read(CHUNK)
#             frames.append(data)
#         audio_queue.put(frames)

#     stream.stop_stream()
#     stream.close()
#     p.terminate()

# def save_audio(frames, filename):
#     wf = wave.open(filename, 'wb')
#     wf.setnchannels(CHANNELS)
#     wf.setsampwidth(pyaudio.PyAudio().get_sample_size(FORMAT))
#     wf.setframerate(RATE)
#     wf.writeframes(b''.join(frames))
#     wf.close()

# def convert_to_mp3(wav_file, mp3_file):
#     audio = AudioSegment.from_wav(wav_file)
#     audio.export(mp3_file, format="mp3")

# def transcribe_audio(audio_file):
#     with open(audio_file, "rb") as file:
#         transcript = client.audio.transcriptions.create(
#             model="whisper-1", 
#             file=file
#         )
#     return transcript.text

# def check_wake_word(transcript):
#     return WAKE_WORD.lower() in transcript.lower()

# def process_audio():
#     while is_recording:
#         if not audio_queue.empty():
#             frames = audio_queue.get()
#             save_audio(frames, WAVE_OUTPUT_FILENAME)
#             convert_to_mp3(WAVE_OUTPUT_FILENAME, MP3_OUTPUT_FILENAME)
#             transcript = transcribe_audio(MP3_OUTPUT_FILENAME)
#             # print(f"Transcript: {transcript}")
            
#             if check_wake_word(transcript):
#                 print(f"Wake word '{WAKE_WORD}' detected!")
            
#             os.remove(WAVE_OUTPUT_FILENAME)
#             os.remove(MP3_OUTPUT_FILENAME)
#         time.sleep(0.1)

# def main():
#     global is_recording

#     record_thread = threading.Thread(target=record_audio)
#     process_thread = threading.Thread(target=process_audio)

#     record_thread.start()
#     process_thread.start()

#     try:
#         while True:
#             time.sleep(0.1)
#     except KeyboardInterrupt:
#         print("Stopping recording...")
#         is_recording = False

#     record_thread.join()
#     process_thread.join()

# if __name__ == "__main__":
#     main()
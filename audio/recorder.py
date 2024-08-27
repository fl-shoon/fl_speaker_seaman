import pyaudio
import numpy as np
import logging
from etc.define import *
import webrtcvad # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InteractiveRecorder:
    def __init__(self, vad_aggressiveness=3):
        self.p = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.stream = None
        self.CHUNK_DURATION_MS = 30  # 30ms chunk duration for VAD
        self.CHUNK_SIZE = int(RATE * self.CHUNK_DURATION_MS / 1000)

    def start_stream(self):
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=CHANNELS,
                                  rate=RATE,
                                  input=True,
                                  frames_per_buffer=self.CHUNK_SIZE)

    def stop_stream(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()

    def record_question(self, silence_threshold=0.03, silence_duration=1.0):
        self.start_stream()
        print("Listening... Speak your question.")
        
        frames = []
        silent_frames = 0
        is_speaking = False
        
        while True:
            data = self.stream.read(self.CHUNK_SIZE)
            frames.append(data)
            
            # Convert audio chunk to float32 for level detection
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            audio_level = np.abs(audio_chunk).mean()
            
            # Voice activity detection
            try:
                is_speech = self.vad.is_speech(data, RATE)
            except Exception as e:
                logger.error(f"VAD error: {e}")
                is_speech = False
            
            if is_speech and not is_speaking:
                print("Speech detected. Recording...")
                is_speaking = True
                silent_frames = 0
            elif not is_speech and is_speaking:
                silent_frames += 1
                if silent_frames > silence_duration * (RATE / self.CHUNK_SIZE):
                    print("End of speech detected.")
                    break
            elif audio_level < silence_threshold * 32767:  # Convert threshold to 16-bit scale
                silent_frames += 1
                if silent_frames > silence_duration * (RATE / self.CHUNK_SIZE):
                    if is_speaking:
                        print("End of speech detected.")
                        break
                    else:
                        print("No speech detected. Please try again.")
                        return None
            else:
                silent_frames = 0
        
        self.stop_stream()
        return b''.join(frames)

def record_audio():
    recorder = InteractiveRecorder()
    return recorder.record_question()
# import pyaudio, logging
# from etc.define import *

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# def record_audio(frame_size):
#     p = pyaudio.PyAudio()

#     stream = p.open(format=FORMAT,  
#                     channels=CHANNELS,
#                     rate=RATE,
#                     input=True,
#                     frames_per_buffer=frame_size)

#     print("* recording")
#     frames = []

#     for _ in range(0, int(RATE / frame_size * RECORD_SECONDS)):
#         try:
#             data = stream.read(frame_size)
#             frames.append(data)
#         except IOError as e:
#             logger.error(f"Stream error during recording: {e}. Continuing...")

#     print("* done recording")

#     stream.stop_stream()
#     stream.close()
#     p.terminate()

#     return frames
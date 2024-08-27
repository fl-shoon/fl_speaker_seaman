import pyaudio
import numpy as np
import logging
# from etc.define import *
import webrtcvad # type: ignore

RATE = 16000
CHANNELS = 1

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class InteractiveRecorder:
    def __init__(self, vad_aggressiveness=3):
        self.p = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.stream = None
        self.CHUNK_DURATION_MS = 30  # 30ms chunk duration for VAD
        self.CHUNK_SIZE = int(RATE * self.CHUNK_DURATION_MS / 1000)
        logger.debug(f"Chunk size: {self.CHUNK_SIZE}")

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

    def record_question(self, silence_threshold=0.01, silence_duration=2.0):
        self.start_stream()
        logger.info("Listening... Speak your question.")
        
        frames = []
        silent_frames = 0
        is_speaking = False
        speech_frames = 0
        
        while True:
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
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
            
            logger.debug(f"Audio level: {audio_level}, Is speech: {is_speech}")
            
            if is_speech:
                speech_frames += 1
                silent_frames = 0
                if not is_speaking and speech_frames > 3:  # Require 3 consecutive speech frames
                    logger.info("Speech detected. Recording...")
                    is_speaking = True
            else:
                silent_frames += 1
                speech_frames = 0
            
            if is_speaking:
                if silent_frames > silence_duration * (RATE / self.CHUNK_SIZE):
                    logger.info("End of speech detected.")
                    break
            elif audio_level < silence_threshold * 32767 and len(frames) > 5 * RATE / self.CHUNK_SIZE:  # 5 seconds of silence
                logger.info("No speech detected. Please try again.")
                return None
        
        self.stop_stream()
        return b''.join(frames)

def record_audio():
    recorder = InteractiveRecorder()
    return recorder.record_question()

# Test the recorder if this script is run directly
if __name__ == "__main__":
    audio_data = record_audio()
    if audio_data:
        logger.info(f"Recorded audio length: {len(audio_data) / RATE} seconds")
    else:
        logger.info("No audio recorded")
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
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
    def __init__(self, vad_aggressiveness=1):  
        self.p = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.stream = None
        self.CHUNK_DURATION_MS = 30  
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

    def record_question(self, silence_threshold=0.005, silence_duration=2.0, max_duration=30):
        self.start_stream()
        logger.info("Listening... Speak your question.")

        frames = []
        silent_frames = 0
        is_speaking = False
        speech_frames = 0
        total_frames = 0

        while True:
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            total_frames += 1

            # Convert audio chunk to float32 for level detection
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            audio_level = np.abs(audio_chunk).mean()

            # Voice activity detection (VAD)
            try:
                is_speech = self.vad.is_speech(data, RATE)
            except Exception as e:
                logger.error(f"VAD error: {e}")
                is_speech = False

            logger.debug(f"Frame {total_frames}: Audio level: {audio_level}, Is speech: {is_speech}")

            if is_speech or audio_level > silence_threshold * 32767:
                speech_frames += 1
                silent_frames = 0
                if not is_speaking and speech_frames > 2: 
                    logger.info("Speech detected. Recording...")
                    is_speaking = True
            else:
                silent_frames += 1
                speech_frames = max(0, speech_frames - 1)  

            if is_speaking:
                if silent_frames > silence_duration * (RATE / self.CHUNK_SIZE):
                    logger.info(f"End of speech detected. Total frames: {total_frames}")
                    break
            elif total_frames > 5 * RATE / self.CHUNK_SIZE:  # 5 seconds of initial silence
                logger.info(f"No speech detected. Total frames: {total_frames}")
                return None

            # Maximum duration check
            if total_frames > max_duration * RATE / self.CHUNK_SIZE:
                logger.info(f"Maximum duration reached. Total frames: {total_frames}")
                break

        self.stop_stream()
        return b''.join(frames)

def record_audio():
    recorder = InteractiveRecorder()
    return recorder.record_question()

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
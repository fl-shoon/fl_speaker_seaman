import pyaudio
import numpy as np
import logging
import webrtcvad # type: ignore

from etc.define import *
# CHANNELS = 1
# RATE = 16000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InteractiveRecorder:
    def __init__(self, vad_aggressiveness=1):  # Reduced aggressiveness
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

    def record_question(self, silence_threshold=0.001, silence_duration=2.0, max_duration=30):
        self.start_stream()
        logger.info("Listening... Speak your question.")

        frames = []
        silent_frames = 0
        is_speaking = False
        speech_frames = 0
        total_frames = 0
        speech_start_frame = 0
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

            logger.debug(f"Frame {total_frames}: Audio level: {audio_level:.4f}, Is speech: {is_speech}")

            if is_speech or audio_level > silence_threshold:
                speech_frames += 1
                silent_frames = 0
                if not is_speaking and speech_frames > 3:  # Reduced from 5 to 3
                    logger.info("Speech detected. Recording...")
                    is_speaking = True
                    speech_start_frame = total_frames - speech_frames
            else:
                silent_frames += 1
                speech_frames = max(0, speech_frames - 1)

            if is_speaking:
                if silent_frames > max_silent_frames:
                    if total_frames - speech_start_frame > 1.0 * (RATE / self.CHUNK_SIZE):  # Reduced from 1.5 to 1.0
                        logger.info(f"End of speech detected. Total frames: {total_frames}")
                        break
                    else:
                        logger.debug("Short speech detected, continuing to listen")
                        is_speaking = False
                        silent_frames = 0
            elif total_frames > 20 * RATE / self.CHUNK_SIZE:  # Increased from 10 to 20 seconds
                logger.info("No speech detected. Stopping recording.")
                return None

            if total_frames > max_duration * RATE / self.CHUNK_SIZE:
                logger.info(f"Maximum duration reached. Total frames: {total_frames}")
                break

        self.stop_stream()
        return b''.join(frames)

def record_audio():
    recorder = InteractiveRecorder(vad_aggressiveness=1)  # Reduced aggressiveness
    return recorder.record_question(silence_threshold=0.001, silence_duration=2.0)  # Adjusted thresholds

# if __name__ == "__main__":
#     audio_data = record_audio()
#     if audio_data:
#         logger.info(f"Recorded audio length: {len(audio_data) / RATE:.2f} seconds")
#     else:
#         logger.info("No audio recorded")
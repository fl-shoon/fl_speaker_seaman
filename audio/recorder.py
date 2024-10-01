import pyaudio, os
import numpy as np
import logging
from typing import Optional

from contextlib import contextmanager

from etc.define import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    def __init__(self): 
        '''
        VAD aggressiveness
        Increasing the value => less sensitive to background noise
        But, it can lead to less speech detection performance.

        Decreasing the vlaue => more sensitive to potential speech
        '''
        self.stream = None
        self.CHUNK_DURATION_MS = 30  
        self.CHUNK_SIZE = int(RATE * self.CHUNK_DURATION_MS / 1000)

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
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()

    def is_speech(self, audio_chunk, threshold=500):
        """Detect speech based on audio energy"""
        audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
        energy = np.abs(audio_data).mean()
        return energy > threshold
    
    def record_question(self, max_duration: int = 20) -> Optional[bytes]:
        self.start_stream()
        logger.info("Listening... Speak your question.")

        frames = []
        is_speaking = False
        last_speech_time = 0
        total_duration = 0
        max_pause = 1.5
        min_recording_duration = 1.0
        initial_silence_duration = 3.0

        while total_duration < max_duration:
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            chunk_duration = len(data) / (RATE * CHANNELS * 2)
            total_duration += chunk_duration

            if self.is_speech(data):
                if not is_speaking:
                    is_speaking = True
                    logger.info("Speech detected. Recording...")
                last_speech_time = total_duration
            elif is_speaking:
                pause_duration = total_duration - last_speech_time
                if pause_duration > max_pause and total_duration > min_recording_duration:
                    logger.info(f"End of speech detected. Total duration: {total_duration:.2f}s")
                    break
            else:
                logger.debug("No speech detected.")

            if not is_speaking and total_duration > initial_silence_duration:
                logger.info("Initial silence duration exceeded. Stopping recording.")
                return None

        self.stop_stream()

        if not is_speaking or total_duration < min_recording_duration:
            logger.info("No speech detected or recording too short. Returning None.")
            return None

        logger.info(f"Recording complete. Total duration: {total_duration:.2f}s")
        self.play_stop_listening_cue()
        return b''.join(frames)

    def play_stop_listening_cue(self):
        # Generate a simple beep sound
        duration = 0.2  # seconds
        frequency = 880  # Hz (A5 note)
        sample_rate = 44100  

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = np.sin(2 * np.pi * frequency * t)
        audio = (audio * 32767).astype(np.int16)

        with suppress_stdout_stderr():
            stream = self.p.open(format=pyaudio.paInt16,
                                channels=1,
                                rate=sample_rate,
                                output=True)
            stream.write(audio.tobytes())
            stream.stop_stream()
            stream.close()

def record_audio() -> Optional[bytes]:
    recorder = InteractiveRecorder()
    return recorder.record_question()
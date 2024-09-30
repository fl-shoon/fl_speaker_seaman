import pyaudio
import numpy as np
import logging
import webrtcvad 
from collections import deque
from etc.define import *
from contextlib import contextmanager

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
    def __init__(self, vad_aggressiveness=3):
        '''
        VAD aggressiveness
        Increasing the value => less sensitive to background noise
        But, it can lead to less speech detection performance.

        Decreasing the vlaue => more sensitive to potential speech
        '''
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.stream = None
        self.CHUNK_DURATION_MS = 10
        self.CHUNK_SIZE = int(RATE * self.CHUNK_DURATION_MS / 1000)
        self.SPEECH_CHUNKS = int(0.1 * 1000 / self.CHUNK_DURATION_MS)
        self.PAUSE_WINDOW = int(1.0 * 1000 / self.CHUNK_DURATION_MS)
        self.ENERGY_WINDOW = int(2.0 * 1000 / self.CHUNK_DURATION_MS)

        with suppress_stdout_stderr():
            self.audio = pyaudio.PyAudio()

        try:
            asound = self.p._lib_pa.pa_get_library_by_name('libasound.so.2')
            asound.snd_lib_error_set_handler(ERROR_HANDLER_FUNC_PTR)
        except:
            logger.warning("Failed to set ALSA error handler")

    def start_stream(self):
        with suppress_stdout_stderr():
            self.stream = self.audio.open(format=pyaudio.paInt16,
                                      channels=CHANNELS,
                                      rate=RATE,
                                      input=True,
                                      frames_per_buffer=self.CHUNK_SIZE)

    def stop_stream(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()

    def is_speech(self, data):
        return self.vad.is_speech(data, RATE)

    def record_question(self, initial_silence_threshold=0.015, energy_threshold=0.3, max_duration=10):
        self.start_stream()

        frames = []
        speech_chunks = 0
        total_chunks = 0
        start_recording = False
        buffer_queue = deque(maxlen=self.PAUSE_WINDOW)
        energy_window = deque(maxlen=self.ENERGY_WINDOW)
        max_energy = 0
        dynamic_silence_threshold = initial_silence_threshold
        last_speech_chunk = 0

        while True:
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            buffer_queue.append(data)
            total_chunks += 1

            is_speech = self.is_speech(data)
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio_chunk).mean() / 32767
            '''
            32767 is the maximum positive value for a 16-bit signed integer
            calculates the average absolute amplitude of the audio chunk, normalized to a 0-1 range
            ''' 
            energy_window.append(volume)

            if volume > max_energy:
                max_energy = volume
                dynamic_silence_threshold = max(initial_silence_threshold, max_energy * 0.1)

            if is_speech or volume > dynamic_silence_threshold:
                speech_chunks += 1
                last_speech_chunk = total_chunks
                if speech_chunks >= self.SPEECH_CHUNKS and not start_recording:
                    start_recording = True
                    frames = list(buffer_queue) + frames
                    logger.info("Speech detected, started recording")
            else:
                speech_chunks = max(0, speech_chunks - 1) 

            if start_recording:
                avg_energy = sum(energy_window) / len(energy_window)
                recent_energy = sum(list(energy_window)[-5:]) / 5  # Use last 50ms for recent energy

                # Detect end of speech
                if recent_energy < dynamic_silence_threshold and avg_energy < energy_threshold * max_energy:
                    silence_duration = total_chunks - last_speech_chunk
                    if silence_duration >= self.PAUSE_WINDOW:
                        logger.info("End of speech detected")
                        # Trim the end to remove silence
                        frames = frames[:-(silence_duration - self.PAUSE_WINDOW // 2)]
                        break

            if total_chunks > max_duration * 1000 / self.CHUNK_DURATION_MS:
                logger.info("Maximum duration reached")
                break

        self.stop_stream()
        return b''.join(frames) if frames else None

def record_audio():
    recorder = InteractiveRecorder(vad_aggressiveness=3)
    return recorder.record_question(initial_silence_threshold=0.015, energy_threshold=0.3, max_duration=10)

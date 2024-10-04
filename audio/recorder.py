import pyaudio
import os
import numpy as np
import logging
import tempfile
import wave
from scipy.signal import butter, lfilter
from contextlib import contextmanager
from collections import deque
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

class InteractiveRecorder:
    def __init__(self):
        self.stream = None
        self.beep_file = self.generate_beep_file()
        # How long each chunk should be in time
        self.CHUNK_DURATION_MS = 30 
        # Pieces of sound data to be collected in one chunk
        self.CHUNK_SIZE = int(RATE * self.CHUNK_DURATION_MS / 1000)
        # Number of chunks to be processed in one second
        self.CHUNKS_PER_SECOND = 1000 // self.CHUNK_DURATION_MS

        self.audio_buffer = deque(maxlen=50) 
        # The loudness level above that is considered to be speech 
        self.energy_threshold = None
        # How long each chunk should be in time
        self.silence_energy = None
        # How loud it typically is when someone is speaking
        self.speech_energy = None

        with suppress_stdout_stderr():
            self.p = pyaudio.PyAudio()

    def start_stream(self):
        if self.stream is None or not self.stream.is_active():
            with suppress_stdout_stderr():
                self.stream = self.p.open(format=pyaudio.paInt16,
                                          channels=CHANNELS,
                                          rate=RATE,
                                          input=True,
                                          frames_per_buffer=self.CHUNK_SIZE)

    def stop_stream(self):
        if self.stream and self.stream.is_active():
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def butter_lowpass(self, cutoff, fs, order=5):
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        return b, a

    def butter_lowpass_filter(self, data, cutoff, fs, order=5):
        b, a = self.butter_lowpass(cutoff, fs, order=order)
        y = lfilter(b, a, data)
        return y

    def calibrate_energy_threshold(self, duration=2):
        self.start_stream()
        energy_levels = []
        for _ in range(duration * self.CHUNKS_PER_SECOND):
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            filtered_audio = self.butter_lowpass_filter(audio_chunk, cutoff=1000, fs=RATE)
            energy = np.sum(filtered_audio**2) / len(filtered_audio)
            energy_levels.append(energy)
        
        self.silence_energy = np.mean(energy_levels)
        # if the recording has ended before speech, use larger value than 2.5
        self.energy_threshold = self.silence_energy * 2.5 
        # logger.info(f"Calibration complete. Silence energy: {self.silence_energy}, Threshold: {self.energy_threshold}")
        self.stop_stream()

    def record_question(self, silence_duration, max_duration, audio_player):
        if self.energy_threshold is None:
            return None

        self.start_stream()
        logging.info("Listening... Speak your question.")

        frames = []
        silent_chunks = 0
        is_speaking = False
        total_chunks = 0

        max_silent_chunks = int(silence_duration * self.CHUNKS_PER_SECOND)

        while True:
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            total_chunks += 1

            audio_chunk = np.frombuffer(data, dtype=np.int16)
            filtered_audio = self.butter_lowpass_filter(audio_chunk, cutoff=1000, fs=RATE)
            energy = np.sum(filtered_audio**2) / len(filtered_audio)

            self.audio_buffer.append(energy)
            average_energy = np.mean(self.audio_buffer)

            is_speech = energy > self.energy_threshold

            # logging.debug(f"Chunk {total_chunks}: Energy: {energy:.2f}, Average energy: {average_energy:.2f}, Threshold: {self.energy_threshold:.2f}, Is speech: {is_speech}, Silent chunks: {silent_chunks}")

            if is_speech:
                if not is_speaking:
                    logging.info("Speech detected. Recording...")
                    is_speaking = True
                silent_chunks = 0
            else:
                silent_chunks += 1

            if is_speaking:
                if silent_chunks > max_silent_chunks:
                    logging.info(f"End of speech detected. Total chunks: {total_chunks}")
                    break
            elif total_chunks > 5 * self.CHUNKS_PER_SECOND:  
                logging.info("No speech detected. Stopping recording.")
                self.stop_stream()
                return None

            if total_chunks > max_duration * self.CHUNKS_PER_SECOND:
                logging.info(f"Maximum duration reached. Total chunks: {total_chunks}")
                break

        audio_player.play_audio(self.beep_file)
        self.stop_stream()
        return b''.join(frames)

    def generate_beep_file(self):
        duration = 0.2  # seconds
        frequency = 880  # Hz (A5 note)
        sample_rate = 44100  

        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = np.sin(2 * np.pi * frequency * t)
        audio = (audio * 32767).astype(np.int16)

        fd, temp_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)

        with wave.open(temp_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())

        return temp_path

    def __del__(self):
        self.stop_stream()
        if self.p:
            self.p.terminate()
        if hasattr(self, 'beep_file') and os.path.exists(self.beep_file):
            os.remove(self.beep_file)
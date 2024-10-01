import pyaudio
import os
import numpy as np
import logging
import webrtcvad
import tempfile
import wave
from scipy.signal import butter, lfilter
from contextlib import contextmanager
from collections import deque
# from etc.define import *
CHANNELS = 1
RATE = 16000
# from audio.player import play_audio
from player import play_audio

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
    def __init__(self, vad_aggressiveness): 
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.stream = None
        self.beep_file = self.generate_beep_file()
        self.CHUNK_DURATION_MS = 30
        self.CHUNK_SIZE = int(RATE * self.CHUNK_DURATION_MS / 1000)
        self.CHUNKS_PER_SECOND = 1000 // self.CHUNK_DURATION_MS

        self.audio_buffer = deque(maxlen=30)  # Increased buffer size
        self.energy_threshold = None
        self.silence_energy = None
        self.speech_energy = None

        with suppress_stdout_stderr():
            self.p = pyaudio.PyAudio()

        try:
            asound = self.p._lib_pa.pa_get_library_by_name('libasound.so.2')
            asound.snd_lib_error_set_handler(ERROR_HANDLER_FUNC_PTR)
        except:
            logger.warning("Failed to set ALSA error handler")

    def start_stream(self):
        if self.stream is None:
            with suppress_stdout_stderr():
                self.stream = self.p.open(format=pyaudio.paInt16,
                                          channels=CHANNELS,
                                          rate=RATE,
                                          input=True,
                                          frames_per_buffer=self.CHUNK_SIZE)
        logger.debug("Audio stream started")

    def stop_stream(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        self.p.terminate()
        logger.debug("Audio stream stopped")

    def butter_lowpass(self, cutoff, fs, order=5):
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        return b, a

    def butter_lowpass_filter(self, data, cutoff, fs, order=5):
        b, a = self.butter_lowpass(cutoff, fs, order=order)
        y = lfilter(b, a, data)
        return y

    def calibrate_energy_threshold(self, duration=5):
        logger.info("Calibrating energy threshold. Please remain silent...")
        self.start_stream()
        energy_levels = []
        for _ in range(duration * self.CHUNKS_PER_SECOND):
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            filtered_audio = self.butter_lowpass_filter(audio_chunk, cutoff=1000, fs=RATE)
            energy = np.sum(filtered_audio**2) / len(filtered_audio)
            energy_levels.append(energy)
        
        self.silence_energy = np.mean(energy_levels)
        self.energy_threshold = self.silence_energy * 1.5  # Reduced from 2 to 1.5
        logger.info(f"Silence energy: {self.silence_energy}")
        logger.info(f"Initial energy threshold set to: {self.energy_threshold}")

        logger.info("Now, please speak a few words for calibration...")
        speech_energy_levels = []
        for _ in range(3 * self.CHUNKS_PER_SECOND):  # Record for 3 seconds
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            filtered_audio = self.butter_lowpass_filter(audio_chunk, cutoff=1000, fs=RATE)
            energy = np.sum(filtered_audio**2) / len(filtered_audio)
            speech_energy_levels.append(energy)
        
        self.speech_energy = np.mean(speech_energy_levels)
        self.energy_threshold = (self.silence_energy + self.speech_energy) / 2
        logger.info(f"Speech energy: {self.speech_energy}")
        logger.info(f"Adjusted energy threshold: {self.energy_threshold}")

    def record_question(self, silence_duration, max_duration):
        if self.energy_threshold is None:
            self.calibrate_energy_threshold()
        else:
            self.start_stream()

        logger.info("Listening... Speak your question.")

        frames = []
        silent_chunks = 0
        is_speaking = False
        speech_probability = 0
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

            try:
                is_speech = self.vad.is_speech(data, RATE)
            except Exception as e:
                logger.error(f"VAD error: {e}")
                is_speech = False

            # Calculate speech probability
            if energy > self.energy_threshold:
                speech_probability = min(1.0, speech_probability + 0.1)
            else:
                speech_probability = max(0.0, speech_probability - 0.1)

            logger.debug(f"Chunk {total_chunks}: Energy: {energy:.2f}, Average energy: {average_energy:.2f}, Threshold: {self.energy_threshold:.2f}, Is speech: {is_speech}, Speech probability: {speech_probability:.2f}, Silent chunks: {silent_chunks}")

            if speech_probability > 0.5 or is_speech:
                if not is_speaking:
                    logger.info("Speech detected. Recording...")
                    is_speaking = True
                silent_chunks = 0
            else:
                silent_chunks += 1

            if is_speaking:
                if silent_chunks > max_silent_chunks:
                    logger.info(f"End of speech detected. Total chunks: {total_chunks}")
                    break
                elif average_energy < self.silence_energy * 1.2 and total_chunks > 30:  # At least 1 second of recording
                    logger.info(f"Sustained low energy detected. Ending recording. Total chunks: {total_chunks}")
                    break
            elif total_chunks > 5 * self.CHUNKS_PER_SECOND:  # 5 seconds of initial silence
                logger.info("No speech detected. Stopping recording.")
                self.stop_stream()
                return None

            if total_chunks > max_duration * self.CHUNKS_PER_SECOND:
                logger.info(f"Maximum duration reached. Total chunks: {total_chunks}")
                break

        self.stop_stream()
        play_audio(self.beep_file)
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
        if hasattr(self, 'beep_file') and os.path.exists(self.beep_file):
            os.remove(self.beep_file)
            
def record_audio():
    recorder = InteractiveRecorder(vad_aggressiveness=2)
    return recorder.record_question(silence_duration=1.5, max_duration=10)

if __name__ == "__main__":
    print("Testing speech detection. Speak into your microphone...")
    audio_data = record_audio()
    if audio_data:
        print(f"Recorded audio data of length: {len(audio_data)} bytes")
    else:
        print("No speech detected")
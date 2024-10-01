import pyaudio
import os
import numpy as np
import logging
import webrtcvad
import tempfile
import wave
from scipy.signal import butter, lfilter
from contextlib import contextmanager
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
        '''
        VAD aggressiveness
        Increasing the value => less sensitive to background noise
        But, it can lead to less speech detection performance.

        Decreasing the vlaue => more sensitive to potential speech
        '''
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.stream = None
        self.beep_file = self.generate_beep_file()
        self.CHUNK_DURATION_MS = 30  
        self.CHUNK_SIZE = int(RATE * self.CHUNK_DURATION_MS / 1000)
        self.CHUNKS_PER_SECOND = 1000 // self.CHUNK_DURATION_MS

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

    def butter_lowpass(self, cutoff, fs, order=5):
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='low', analog=False)
        return b, a

    def butter_lowpass_filter(self, data, cutoff, fs, order=5):
        b, a = self.butter_lowpass(cutoff, fs, order=order)
        y = lfilter(b, a, data)
        return y

    def record_question(self, silence_threshold, silence_duration, max_duration):
        self.start_stream()
        logger.info("Listening... Speak your question.")

        frames = []
        silent_chunks = 0
        is_speaking = False
        speech_chunks = 0
        total_chunks = 0

        consecutive_speech_chunks = 3
        initial_silence_chunks = 3 * self.CHUNKS_PER_SECOND

        max_silent_chunks = int(silence_duration * self.CHUNKS_PER_SECOND)

        while True:
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            total_chunks += 1

            audio_chunk = np.frombuffer(data, dtype=np.int16)
            
            # Apply low-pass filter
            filtered_audio = self.butter_lowpass_filter(audio_chunk, cutoff=1000, fs=RATE)
            
            audio_level = np.abs(filtered_audio).mean() / 32767

            # Update audio buffer
            self.audio_buffer.append(audio_level)
            if len(self.audio_buffer) > self.buffer_size:
                self.audio_buffer.pop(0)

            # Calculate moving average
            average_level = np.mean(self.audio_buffer)

            try:
                is_speech = self.vad.is_speech(data, RATE)
            except Exception as e:
                logger.error(f"VAD error: {e}")
                is_speech = average_level > silence_threshold  # Fallback to audio level

            logger.debug(f"Chunk {total_chunks}: Audio level: {audio_level:.4f}, Average level: {average_level:.4f}, Is speech: {is_speech}, Silent chunks: {silent_chunks}, Speech chunks: {speech_chunks}")

            if is_speech or average_level > silence_threshold:
                speech_chunks += 1
                silent_chunks = 0
                if not is_speaking and speech_chunks > consecutive_speech_chunks:
                    logger.info("Speech detected. Recording...")
                    is_speaking = True
            else: 
                silent_chunks += 1
                speech_chunks = max(0, speech_chunks - 1)

            if is_speaking:
                if silent_chunks > max_silent_chunks:
                    logger.info(f"End of speech detected. Total chunks: {total_chunks}")
                    break
            elif total_chunks > initial_silence_chunks:  
                logger.info("No speech detected. Stopping recording.")
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
    return recorder.record_question(silence_threshold=0.02, silence_duration=1.5, max_duration=10)

if __name__ == "__main__":
    print("Testing speech detection. Speak into your microphone...")
    audio_data = record_audio()
    if audio_data:
        print(f"Recorded audio data of length: {len(audio_data)} bytes")
    else:
        print("No speech detected")
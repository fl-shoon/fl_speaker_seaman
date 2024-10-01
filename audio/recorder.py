import pyaudio
import os
import numpy as np
import logging
import webrtcvad
import tempfile
import wave
from contextlib import contextmanager
from etc.define import *
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

    def record_question(self, silence_threshold, silence_duration, max_duration):
        '''
        Silence_threadshold is so low because mic's audio output levels were generally very low.
        Setting the small value enhances the detection of quieter speech.

        Increasing silence_duration allows more natural pauses in speech.
        '''
        self.start_stream()
        logger.info("Listening... Speak your question.")

        frames = []
        silent_frames = 0
        is_speaking = False
        speech_frames = 0
        total_frames = 0

        '''
        Consecutive speech to prevent false starts due to brief noises
        Here, frame value is too small due to mic's audio output quality.
        '''
        consecutive_speech_frames = 2

        '''
        Initial silence duration to decide to stop recording due to no speech
        '''
        initial_silence_duration = 3

        max_silent_frames = int(silence_duration * RATE / self.CHUNK_SIZE) # calculates how many silent chunks correspond to the silence_duration

        while True:
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            total_frames += 1

            audio_chunk = np.frombuffer(data, dtype=np.int16)
            audio_level = np.abs(audio_chunk).mean() / 32767 
            '''
            32767 is the maximum positive value for a 16-bit signed integer
            calculates the average absolute amplitude of the audio chunk, normalized to a 0-1 range
            '''  

            try:
                is_speech = self.vad.is_speech(data, RATE)
            except Exception as e:
                logger.error(f"VAD error: {e}")
                is_speech = False

            logger.debug(f"Frame {total_frames}: Audio level: {audio_level:.4f}, Is speech: {is_speech}")

            if is_speech or audio_level > silence_threshold:
                speech_frames += 1
                silent_frames = 0
                if not is_speaking and speech_frames > consecutive_speech_frames:
                    logger.info("Speech detected. Recording...")
                    is_speaking = True
            else: 
                silent_frames += 1
                speech_frames = max(0, speech_frames - 1)

            if is_speaking:
                if silent_frames > max_silent_frames:
                    logger.info(f"End of speech detected. Total frames: {total_frames}")
                    break
            elif total_frames > initial_silence_duration * RATE / self.CHUNK_SIZE:  
                logger.info("No speech detected. Stopping recording.")
                return None

            if total_frames > max_duration * RATE / self.CHUNK_SIZE:
                logger.info(f"Maximum duration reached. Total frames: {total_frames}")
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
    recorder = InteractiveRecorder(vad_aggressiveness=3)
    return recorder.record_question(silence_threshold=0.01, silence_duration=1, max_duration=10)
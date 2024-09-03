import pyaudio, os
import numpy as np
import logging
import webrtcvad # type: ignore

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
    def __init__(self, vad_aggressiveness=1):
        # self.p = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.stream = None
        self.CHUNK_DURATION_MS = 30  
        self.CHUNK_SIZE = int(RATE * self.CHUNK_DURATION_MS / 1000)
        logger.debug(f"Chunk size: {self.CHUNK_SIZE}")

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

    def record_question(self, silence_threshold=0.0005, silence_duration=1.5, max_duration=15):
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
                if not is_speaking and speech_frames > 2:
                    logger.info("Speech detected. Recording...")
                    is_speaking = True
                    speech_start_frame = total_frames - speech_frames
            else:
                silent_frames += 1
                speech_frames = max(0, speech_frames - 1)

            if is_speaking:
                if silent_frames > max_silent_frames:
                    logger.info(f"End of speech detected. Total frames: {total_frames}")
                    break
            elif total_frames > 10 * RATE / self.CHUNK_SIZE:  # 10 seconds of initial silence
                logger.info("No speech detected. Stopping recording.")
                return None

            if total_frames > max_duration * RATE / self.CHUNK_SIZE:
                logger.info(f"Maximum duration reached. Total frames: {total_frames}")
                break

        self.stop_stream()
        return b''.join(frames)  

def record_audio():
    recorder = InteractiveRecorder(vad_aggressiveness=1)
    return recorder.record_question(silence_threshold=0.0005, silence_duration=1.5, max_duration=15)

# for reference purpose
'''
Increased VAD aggressiveness: The VAD was sometimes detecting speech when the audio level was very low. I've increased the default vad_aggressiveness to 2 to make it less sensitive to background noise.
Adjusted silence threshold: I've lowered the silence_threshold to 0.002 (from 0.01) as the audio levels in your output were generally very low.
Modified speech detection logic: I've increased the number of consecutive speech frames required to trigger recording from 3 to 5. This should help prevent false starts due to brief noises.
Implemented a gradual speech frame reduction: Instead of resetting speech frames to 0 immediately, I've added a gradual reduction to allow for small gaps in speech.
'''

'''
Reduced VAD aggressiveness from 2 to 1 to make it more sensitive to potential speech.
Lowered the silence_threshold from 0.002 to 0.001 to detect quieter speech.
Increased silence_duration from 1.5 to 2.0 seconds to allow for more natural pauses in speech.
Reduced the number of consecutive speech frames required to trigger recording from 5 to 3.
Decreased the minimum speech duration from 1.5 seconds to 1.0 seconds to capture shorter utterances.
Increased the initial silence duration from 10 to 20 seconds before stopping due to no speech.
Modified the speech detection condition to if is_speech or audio_level > silence_threshold to be more lenient.
'''
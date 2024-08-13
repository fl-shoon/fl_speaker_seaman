import pyaudio
import numpy as np
import time
import logging
from etc.define import *

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def is_silent(data_chunk, threshold=100):
    """Check if the audio chunk is silent."""
    amplified_chunk = np.frombuffer(data_chunk, dtype=np.int16) * 5  # Amplify the signal
    max_amplitude = np.max(np.abs(amplified_chunk))
    logger.debug(f"Max amplitude: {max_amplitude}")
    return max_amplitude < threshold

def record_audio(frame_size, silence_threshold=100, silence_duration=1.5, max_duration=10, min_duration=0.5):
    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=frame_size)

    logger.info("* recording started")
    frames = []
    silent_time = 0
    start_time = time.time()
    has_speech = False
    last_audio_time = start_time
    speech_duration = 0

    while True:
        current_time = time.time()
        chunk = stream.read(frame_size)
        
        if not is_silent(chunk, silence_threshold):
            if not has_speech:
                logger.info("Speech detected")
            has_speech = True
            last_audio_time = current_time
            silent_time = 0
            speech_duration += current_time - last_audio_time
        elif has_speech:
            silent_time += current_time - last_audio_time
            logger.debug(f"Silent for {silent_time:.2f} seconds")

        frames.append(chunk)

        elapsed_time = current_time - start_time
        if has_speech and (silent_time >= silence_duration or speech_duration >= 5) and elapsed_time >= min_duration:
            logger.info(f"Stopping recording. Total duration: {elapsed_time:.2f} seconds")
            break
        
        if elapsed_time >= max_duration:
            logger.info(f"Reached maximum duration of {max_duration} seconds")
            break

    logger.info("* recording finished")

    stream.stop_stream()
    stream.close()
    p.terminate()

    if not has_speech or (time.time() - start_time) < min_duration:
        logger.warning("No speech detected or recording too short")
        return []

    logger.info(f"Recorded {len(frames)} frames")
    return frames
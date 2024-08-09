import pyaudio
import numpy as np
import time
import logging
from etc.define import *

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def is_silent(data_chunk, threshold=100):  # Lowered threshold even further
    """Check if the audio chunk is silent."""
    amplified_chunk = np.frombuffer(data_chunk, dtype=np.int16) * 5  # Amplify the signal
    max_amplitude = np.max(np.abs(amplified_chunk))
    logger.debug(f"Max amplitude: {max_amplitude}")
    return max_amplitude < threshold

def record_audio(frame_size, silence_threshold=100, silence_duration=1.5, max_duration=30, min_duration=0.5):
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

    while True:
        current_time = time.time()
        chunk = stream.read(frame_size)
        
        if not is_silent(chunk, silence_threshold):
            has_speech = True
            last_audio_time = current_time
            silent_time = 0
            logger.debug("Speech detected")
        elif has_speech:
            silent_time += current_time - last_audio_time
            last_audio_time = current_time
            logger.debug(f"Silent for {silent_time:.2f} seconds")

        frames.append(chunk)

        elapsed_time = current_time - start_time
        if has_speech and silent_time >= silence_duration and elapsed_time >= min_duration:
            logger.info(f"Detected end of speech. Total duration: {elapsed_time:.2f} seconds")
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
# import pyaudio, logging
# from etc.define import *

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# def record_audio(frame_size, device_name_pattern="USB PnP Sound Device"):
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
import pyaudio
import logging
import numpy as np
from etc.define import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_silent(data_chunk, threshold=500):
    """Check if the audio chunk is silent."""
    return np.max(np.abs(np.frombuffer(data_chunk, dtype=np.int16))) < threshold

def record_audio(frame_size, silence_threshold=500, silence_duration=3):
    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=frame_size)

    print("* recording")
    frames = []
    silent_chunks = 0
    silence_limit = int(silence_duration * RATE / frame_size)

    while True:
        try:
            data = stream.read(frame_size)
            frames.append(data)

            if is_silent(data, silence_threshold):
                silent_chunks += 1
                if silent_chunks >= silence_limit:
                    break
            else:
                silent_chunks = 0
        except IOError as e:
            logger.error(f"Stream error during recording: {e}. Continuing...")

    print("* done recording")

    stream.stop_stream()
    stream.close()
    p.terminate()

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
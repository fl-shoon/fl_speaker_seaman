import pyaudio
import numpy as np
import time
from etc.define import *

def is_silent(data_chunk, threshold=500):
    """Check if the audio chunk is silent."""
    return np.max(np.abs(np.frombuffer(data_chunk, dtype=np.int16))) < threshold

def record_audio(frame_size, silence_threshold=500, silence_duration=2, max_duration=30):
    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=frame_size)

    print("* recording")
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
        elif has_speech:
            silent_time += current_time - last_audio_time
            last_audio_time = current_time

        frames.append(chunk)

        if has_speech and silent_time >= silence_duration:
            print("Detected end of speech")
            break
        
        if current_time - start_time >= max_duration:
            print("Reached maximum duration")
            break

    print("* done recording")

    stream.stop_stream()
    stream.close()
    p.terminate()

    return frames if has_speech else []
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
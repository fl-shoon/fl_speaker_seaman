import pyaudio, logging
from etc.define import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_input_device_index(device_name_pattern):
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        dev_info = p.get_device_info_by_index(i)
        if device_name_pattern.lower() in dev_info['name'].lower() and dev_info['maxInputChannels'] > 0:
            return i
    return None

def record_audio(frame_size, device_name_pattern="USB PnP Sound Device"):
    p = pyaudio.PyAudio()

    device_index = get_input_device_index(device_name_pattern)

    if device_index is None:
        logger.error(f"Error: Could not find input device matching '{device_name_pattern}'")
        device_index = 3
    
    stream = p.open(format=FORMAT,  
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=frame_size)

    print("* recording")
    frames = []

    for _ in range(0, int(RATE / frame_size * RECORD_SECONDS)):
        try:
            data = stream.read(frame_size)
            frames.append(data)
        except IOError as e:
            logger.error(f"Stream error during recording: {e}. Continuing...")

    print("* done recording")

    stream.stop_stream()
    stream.close()
    p.terminate()

    return frames
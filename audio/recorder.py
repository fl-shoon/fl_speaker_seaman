import pyaudio
from etc.define import CHUNK, CHANNELS, RATE, FORMAT, RECORD_SECONDS

def record_audio(frame_size):
    p = pyaudio.PyAudio()
    
    stream = p.open(format=FORMAT,  
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=frame_size)

    print("* recording")
    frames = []

    for _ in range(0, int(RATE / frame_size * RECORD_SECONDS)):
        try:
            data = stream.read(frame_size)
            frames.append(data)
        except IOError as e:
            print(f"Stream error during recording: {e}. Continuing...")

    print("* done recording")

    stream.stop_stream()
    stream.close()
    p.terminate()

    return frames
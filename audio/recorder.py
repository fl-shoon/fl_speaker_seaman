# import pyaudio
# import numpy as np
# import logging
# import webrtcvad 
# from collections import deque
# from etc.define import *

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# class InteractiveRecorder:
#     def __init__(self, vad_aggressiveness=3):
#         self.vad = webrtcvad.Vad(vad_aggressiveness)
#         self.audio = pyaudio.PyAudio()
#         self.stream = None
#         self.CHUNK_DURATION_MS = 10
#         self.CHUNK_SIZE = int(RATE * self.CHUNK_DURATION_MS / 1000)
#         self.SPEECH_CHUNKS = int(0.1 * 1000 / self.CHUNK_DURATION_MS)
#         self.SHORT_PAUSE_CHUNKS = int(0.3 * 1000 / self.CHUNK_DURATION_MS)
#         self.LONG_PAUSE_CHUNKS = int(0.7 * 1000 / self.CHUNK_DURATION_MS)
#         self.ACTIVITY_WINDOW = int(3.0 * 1000 / self.CHUNK_DURATION_MS)

#     def start_stream(self):
#         self.stream = self.audio.open(format=pyaudio.paInt16,
#                                       channels=CHANNELS,
#                                       rate=RATE,
#                                       input=True,
#                                       frames_per_buffer=self.CHUNK_SIZE)

#     def stop_stream(self):
#         if self.stream:
#             self.stream.stop_stream()
#             self.stream.close()
#         self.audio.terminate()

#     def is_speech(self, data):
#         return self.vad.is_speech(data, RATE)

#     def record_question(self, silence_threshold=0.015, max_duration=10):
#         self.start_stream()

#         frames = []
#         silent_chunks = 0
#         speech_chunks = 0
#         total_chunks = 0
#         start_recording = False
#         buffer_queue = deque(maxlen=self.SHORT_PAUSE_CHUNKS)
#         activity_window = deque(maxlen=self.ACTIVITY_WINDOW)

#         while True:
#             data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
#             frames.append(data)
#             buffer_queue.append(data)
#             total_chunks += 1

#             is_speech = self.is_speech(data)
#             audio_chunk = np.frombuffer(data, dtype=np.int16)
#             volume = np.abs(audio_chunk).mean() / 32767

#             activity_window.append(volume > silence_threshold)

#             if is_speech or volume > silence_threshold:
#                 speech_chunks += 1
#                 silent_chunks = 0
#                 if speech_chunks >= self.SPEECH_CHUNKS and not start_recording:
#                     start_recording = True
#                     frames = list(buffer_queue) + frames
#                     logger.info("Speech detected, started recording")
#             else:
#                 silent_chunks += 1
#                 speech_chunks = max(0, speech_chunks - 1)  # Allow for small interruptions

#             if start_recording:
#                 # Adaptive silence detection
#                 if silent_chunks >= self.LONG_PAUSE_CHUNKS:
#                     logger.info("Long pause detected, stopping recording")
#                     break
#                 elif silent_chunks >= self.SHORT_PAUSE_CHUNKS:
#                     # Check recent activity to decide if we should stop
#                     recent_activity = sum(activity_window) / len(activity_window)
#                     if recent_activity < 0.3:  # Less than 30% activity in the recent window
#                         logger.info("Low recent activity detected, stopping recording")
#                         break

#             if total_chunks > max_duration * 1000 / self.CHUNK_DURATION_MS:
#                 logger.info("Maximum duration reached")
#                 break

#         self.stop_stream()
#         return b''.join(frames) if frames else None

# def record_audio():
#     recorder = InteractiveRecorder(vad_aggressiveness=3)
#     return recorder.record_question(silence_threshold=0.015, max_duration=10)

import pyaudio
import numpy as np
import logging
import webrtcvad 
from collections import deque
from etc.define import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InteractiveRecorder:
    def __init__(self, vad_aggressiveness=3):
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.CHUNK_DURATION_MS = 10
        self.CHUNK_SIZE = int(RATE * self.CHUNK_DURATION_MS / 1000)
        self.SPEECH_CHUNKS = int(0.1 * 1000 / self.CHUNK_DURATION_MS)
        self.PAUSE_WINDOW = int(1.0 * 1000 / self.CHUNK_DURATION_MS)
        self.ENERGY_WINDOW = int(2.0 * 1000 / self.CHUNK_DURATION_MS)

    def start_stream(self):
        self.stream = self.audio.open(format=pyaudio.paInt16,
                                      channels=CHANNELS,
                                      rate=RATE,
                                      input=True,
                                      frames_per_buffer=self.CHUNK_SIZE)

    def stop_stream(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()

    def is_speech(self, data):
        return self.vad.is_speech(data, RATE)

    def record_question(self, initial_silence_threshold=0.015, energy_threshold=0.3, max_duration=10):
        self.start_stream()

        frames = []
        speech_chunks = 0
        total_chunks = 0
        start_recording = False
        buffer_queue = deque(maxlen=self.PAUSE_WINDOW)
        energy_window = deque(maxlen=self.ENERGY_WINDOW)
        max_energy = 0
        dynamic_silence_threshold = initial_silence_threshold

        while True:
            data = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            frames.append(data)
            buffer_queue.append(data)
            total_chunks += 1

            is_speech = self.is_speech(data)
            audio_chunk = np.frombuffer(data, dtype=np.int16)
            volume = np.abs(audio_chunk).mean() / 32767
            energy_window.append(volume)

            if volume > max_energy:
                max_energy = volume
                dynamic_silence_threshold = max(initial_silence_threshold, max_energy * 0.1)

            if is_speech or volume > dynamic_silence_threshold:
                speech_chunks += 1
                if speech_chunks >= self.SPEECH_CHUNKS and not start_recording:
                    start_recording = True
                    frames = list(buffer_queue) + frames
                    logger.info("Speech detected, started recording")
            else:
                speech_chunks = max(0, speech_chunks - 1)  # Allow for small interruptions

            if start_recording:
                avg_energy = sum(energy_window) / len(energy_window)
                recent_energy = sum(list(energy_window)[-10:]) / 10  # Average of last 100ms

                # Detect end of speech
                if recent_energy < dynamic_silence_threshold and avg_energy < energy_threshold * max_energy:
                    pause_duration = sum(1 for v in reversed(energy_window) if v < dynamic_silence_threshold)
                    if pause_duration >= self.PAUSE_WINDOW * 0.7:  # 70% of pause window is silence
                        logger.info("End of speech detected")
                        break

            if total_chunks > max_duration * 1000 / self.CHUNK_DURATION_MS:
                logger.info("Maximum duration reached")
                break

        self.stop_stream()
        return b''.join(frames) if frames else None

def record_audio():
    recorder = InteractiveRecorder(vad_aggressiveness=3)
    return recorder.record_question(initial_silence_threshold=0.015, energy_threshold=0.3, max_duration=10)

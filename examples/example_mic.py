import speech_recognition as sr # SpeechRecognition
import pyttsx3
import pyaudio
import wave
import pygame
import io

def speak(text):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

def record_audio(duration=10, sample_rate=44100, chunk=1024, channels=1):
    audio = pyaudio.PyAudio()
    print("Listening... Speak your question.")
    stream = audio.open(format=pyaudio.paInt16,
                        channels=channels,
                        rate=sample_rate,
                        input=True,
                        frames_per_buffer=chunk)

    frames = []
    for _ in range(0, int(sample_rate / chunk * duration)):
        data = stream.read(chunk)
        frames.append(data)

    print("10 seconds reached.")
    stream.stop_stream()
    stream.close()
    audio.terminate()

    return frames, sample_rate

def play_audio_pygame(frames, sample_rate, volume=0.2):
    pygame.mixer.init(frequency=sample_rate, size=-16, channels=1)
    
    # Create a WAV file in memory
    buffer = io.BytesIO()
    wf = wave.open(buffer, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)
    wf.writeframes(b''.join(frames))
    wf.close()

    # Load the WAV file from the buffer
    buffer.seek(0)
    pygame.mixer.music.load(buffer)
    
    # Set the volume (0.0 to 1.0)
    pygame.mixer.music.set_volume(volume)
    
    # Play the audio
    pygame.mixer.music.play()
    
    # Wait for the audio to finish playing
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    
    # Clean up
    pygame.mixer.quit()

def main():
    frames, sample_rate = record_audio()
    play_audio_pygame(frames, sample_rate, volume=0.2)  # Set volume to 50%


if __name__ == "__main__":
    main()
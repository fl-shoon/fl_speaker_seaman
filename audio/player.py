import pygame, threading
from pygame import mixer

# Initialize Pygame mixer
mixer.init()

def play_audio(filename):
    mixer.music.load(filename)
    mixer.music.play()

def sync_audio_and_gif(display, audio_file, gif_path):
    play_audio(audio_file)
    
    gif_thread = threading.Thread(target=display.update_gif, args=(gif_path,))
    gif_thread.start()

    while mixer.music.get_busy():
        pygame.time.Clock().tick(10)

    gif_thread.join()
    display.send_white_frames()
import pygame, threading, os
from pygame import mixer
from contextlib import contextmanager

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

# Suppress Pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# Initialize Pygame mixer with suppressed output
with suppress_stdout_stderr():
    mixer.init()

def play_audio(filename):
    with suppress_stdout_stderr():
        mixer.music.load(filename)
        mixer.music.play()

def sync_audio_and_gif(display, audio_file, gif_path):
    play_audio(audio_file)
    
    gif_thread = threading.Thread(target=display.update_gif, args=(gif_path,))
    gif_thread.start()

    while mixer.music.get_busy():
        with suppress_stdout_stderr():
            pygame.time.Clock().tick(10)

    gif_thread.join()
    display.send_white_frames()
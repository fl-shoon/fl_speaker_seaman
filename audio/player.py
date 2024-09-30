import pygame, threading, os, sys
from pygame import mixer
from contextlib import contextmanager

@contextmanager
def suppress_stdout_stderr():
    """A context manager that redirects stdout and stderr to devnull"""
    _stdout = sys.stdout
    _stderr = sys.stderr
    null = open(os.devnull, 'w')
    try:
        sys.stdout = null
        sys.stderr = null
        yield
    finally:
        sys.stdout = _stdout
        sys.stderr = _stderr
        null.close()

# Suppress Pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# Initialize Pygame mixer with suppressed output
with suppress_stdout_stderr():
    pygame.init()
    mixer.init()

def play_audio(filename):
    with suppress_stdout_stderr():
        mixer.music.load(filename)
        mixer.music.play()
        mixer.music.set_volume(0.2)

def sync_audio_and_gif(display, audio_file, gif_path):
    play_audio(audio_file)
    
    gif_thread = threading.Thread(target=display.update_gif, args=(gif_path,))
    gif_thread.start()

    clock = pygame.time.Clock()
    while mixer.music.get_busy():
        with suppress_stdout_stderr():
            clock.tick(10)

    gif_thread.join()
    display.send_white_frames()
import pygame, threading, os, sys, asyncio
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
        mixer.music.set_volume(0.5)
    while mixer.music.get_busy():
        pygame.time.Clock().tick(10)

async def play_audio_async(filename):
    with suppress_stdout_stderr():
        mixer.music.load(filename)
        mixer.music.play()
        mixer.music.set_volume(0.5)
    while mixer.music.get_busy():
        await asyncio.sleep(0.1)

def sync_audio_and_gif(display, audio_file, gif_path):
    play_audio(audio_file)
    
    gif_thread = threading.Thread(target=display.update_gif, args=(gif_path,))
    gif_thread.start()

    clock = pygame.time.Clock()
    while mixer.music.get_busy():
        with suppress_stdout_stderr():
            clock.tick(10)

    display.stop_animation()
    gif_thread.join()
    display.send_white_frames()

async def sync_audio_and_gif_async(display, audio_file, gif_path):
    audio_task = asyncio.create_task(play_audio_async(audio_file))
    gif_task = asyncio.create_task(display.update_gif_async(gif_path))
    
    await audio_task
    display.stop_animation()
    await gif_task

    await display.send_white_frames_async()

# Synchronous wrapper for async function
def sync_audio_and_gif_wrapper(display, audio_file, gif_path):
    asyncio.run(sync_audio_and_gif_async(display, audio_file, gif_path))
import os, sys
from io import StringIO

class PyMixerModule:
    def __init__(self):
        self.player = None
        self.clock = None

    def initialize(self):
        # Suppress Pygame welcome message
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

        # Store the original stdout to hide pygame message
        original_stdout = sys.stdout

        # Create a string buffer to capture any output
        string_buffer = StringIO()

        try:
            # Redirect stdout to string buffer
            sys.stdout = string_buffer

            import pygame
            from pygame import mixer

            # Initialize Pygame mixer
            mixer.init()

            self.player = mixer
            self.clock = pygame.time.Clock()
        except ImportError:
            print("Error: Pygame module not found. Please install it using 'pip install pygame'")
        except Exception as e:
            print(f"Error initializing Pygame mixer: {e}")
        finally:
            # Restore stdout
            sys.stdout = original_stdout

    def get_player(self):
        if not self.player:
            self.initialize()
        return self.player
    
    def get_clock(self):
        if not self.clock:
            self.initialize()
        return self.clock

class AudioPlayerModule:
    def __init__(self):
        self.mixer_module = PyMixerModule()
        self.audio_player = self.mixer_module.get_player()
        self.audio_clock = self.mixer_module.get_clock()
        self.current_track = None

    def play(self, filename):
        if self.audio_player:
            try:
                self.audio_player.music.load(filename)
                self.audio_player.music.play()
                self.current_track = filename
                print(f"Now playing: {filename}")
            except Exception as e:
                print(f"Error playing {filename}: {e}")
        else:
            print("Failed to initialize PyMixer")

    def stop(self):
        if self.audio_player and self.audio_player.music.get_busy():
            self.audio_player.music.stop()
            print("Playback stopped")

    def pause(self):
        if self.audio_player and self.audio_player.music.get_busy():
            self.audio_player.music.pause()
            print("Playback paused")

    def unpause(self):
        if self.audio_player:
            self.audio_player.music.unpause()
            print("Playback resumed")

    def set_volume(self, volume):
        if self.audio_player:
            self.audio_player.music.set_volume(volume)
            print(f"Volume set to {volume}")

    def get_volume(self):
        if self.audio_player:
            return self.audio_player.music.get_volume()
        return 0.0

    def is_playing(self):
        if self.audio_player:
            return self.audio_player.music.get_busy()
        return False

    def get_current_track(self):
        return self.current_track

# Usage example
if __name__ == "__main__":
    player = AudioPlayerModule()
    player.play("path/to/your/audio/file.mp3")
    print(f"Current volume: {player.get_volume()}")
    player.set_volume(0.5)
    print(f"Is playing: {player.is_playing()}")
    player.pause()
    player.unpause()
    player.stop()
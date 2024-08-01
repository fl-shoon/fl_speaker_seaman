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
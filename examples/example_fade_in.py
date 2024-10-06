import sys
import time
from PIL import Image, ImageEnhance
import io
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer
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

class AudioPlayer:
    def __init__(self):
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
        with suppress_stdout_stderr():
            pygame.init()
            mixer.init()
        self.is_playing = mixer.music.get_busy()

    def play_audio(self, filename):
        with suppress_stdout_stderr():
            mixer.music.load(filename)
            mixer.music.play()
            mixer.music.set_volume(0.5)

class DisplayModule:
    def __init__(self, window):
        self.window = window
        self.current_brightness = 1.0

    def prepare_gif(self, gif_path, target_size=(240, 240)):
        gif = Image.open(gif_path)
        frames = []
        try:
            while True:
                gif.seek(gif.tell() + 1)
                frame = gif.copy().convert('RGB').resize(target_size)
                frames.append(np.array(frame))
        except EOFError:
            pass  
        return frames
    
    def frame_to_bytes(self, frame):
        img = Image.fromarray(frame)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    
    def precompute_frames(self, frames):
        return [self.frame_to_bytes(frame) for frame in frames]
    
    def update_gif(self, gif_path, max_brightness=0.3):
        frames = self.prepare_gif(gif_path)
        all_frames = self.precompute_frames(frames)
        
        frame_index = 0
        while mixer.music.get_busy():
            # Get the current frame
            frame = Image.open(io.BytesIO(all_frames[frame_index]))
            width, height = frame.size
            
            # Adjust brightness
            enhancer = ImageEnhance.Brightness(frame)
            brightened_frame = enhancer.enhance(max_brightness)
            
            # Convert back to byte array
            # img_byte_arr = io.BytesIO()
            # brightened_frame.save(img_byte_arr, format='PNG')
            # img_byte_arr = img_byte_arr.getvalue()
            
            # Send to display
            # self.serial_module.send_image_data(img_byte_arr)

            qim = QImage(brightened_frame.tobytes("raw", "RGB"), width, height, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qim)
            self.window.image_label.setPixmap(pixmap)
            self.window.image_label.repaint()
            
            QApplication.processEvents()  # Ensure the GUI updates
            time.sleep(0.1)
            
            frame_index = (frame_index + 1) % len(all_frames)
            time.sleep(0.1)  # Adjust this delay as needed
        
        # Update current brightness
        # self.current_brightness = max_brightness
    
    def fade_in_logo(self, logo_path, steps=7, max_brightness=1.0):
        img = Image.open(logo_path)
        width, height = img.size
        
        for i in range(steps):
            # Calculate alpha and brightness for this step
            alpha = int(255 * (i + 1) / steps)
            current_brightness = max_brightness * (i + 1) / steps
            
            # Create faded image with alpha
            faded_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            faded_img.paste(img, (0, 0))
            faded_img.putalpha(alpha)

            # Convert to RGB
            rgb_img = Image.new("RGB", faded_img.size, (0, 0, 0))
            rgb_img.paste(faded_img, mask=faded_img.split()[3])
            
            # Adjust brightness
            enhancer = ImageEnhance.Brightness(rgb_img)
            brightened_img = enhancer.enhance(current_brightness)

            # Convert PIL Image to QPixmap and display
            qim = QImage(brightened_img.tobytes("raw", "RGB"), width, height, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qim)
            self.window.image_label.setPixmap(pixmap)
            self.window.image_label.repaint()
            
            QApplication.processEvents()  # Ensure the GUI updates
            time.sleep(0.1)  # Slow down the animation for visibility
        
        # Update current brightness
        self.current_brightness = max_brightness

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fade-in Logo Test")
        self.image_label = QLabel(self)
        self.setCentralWidget(self.image_label)
        self.display_module = DisplayModule(self)

    def start_fade_in(self, logo_path):
        QTimer.singleShot(100, lambda: self.display_module.fade_in_logo(logo_path, steps=30, max_brightness=0.2))

    def start_gif_play(self):
        AudioPlayer().play_audio("assets/output.wav")
        gif_thread = threading.Thread(target=self.display_module.update_gif, args=("assets/speakingGif.gif",))
        gif_thread.start()

        clock = pygame.time.Clock()
        while mixer.music.get_busy():
            with suppress_stdout_stderr():
                clock.tick(10)

        gif_thread.join()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.resize(300, 300)  # Set a default size
    window.show()
    
    # Replace with the path to your logo image
    logo_path = "assets/logo.png"
    
    # window.start_fade_in(logo_path)
    window.start_gif_play()
    
    sys.exit(app.exec_())
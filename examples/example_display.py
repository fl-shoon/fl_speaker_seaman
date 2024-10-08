import threading, time, io, pygame, os, logging
from PIL import Image
from pygame import mixer
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

class DisplayModule:
    def __init__(self, serial_module):
        self.serial_module = serial_module
        # os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
        # with suppress_stdout_stderr():
        #     pygame.init()

    def fade_in_logo(self, logo_path, steps=7):
        img = Image.open(logo_path)
        width, height = img.size
        
        for i in range(steps):
            alpha = int(255 * (i + 1) / steps)
            faded_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            faded_img.paste(img, (0, 0))
            faded_img.putalpha(alpha)

            rgb_img = Image.new("RGB", faded_img.size, (0, 0, 0))
            rgb_img.paste(faded_img, mask=faded_img.split()[3])

            img_byte_arr = io.BytesIO()
            rgb_img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            self.serial_module.send_image_data(img_byte_arr)
            time.sleep(0.01)

    def play_trigger_with_logo(self, trigger_audio, logo_path, audio_player):
        audio_player.play_audio(trigger_audio)
        
        fade_thread = threading.Thread(target=self.fade_in_logo, args=(logo_path,))
        fade_thread.start()

        while mixer.music.get_busy():
            with suppress_stdout_stderr():
                pygame.time.Clock().tick(10)

        fade_thread.join()

    def update_gif(self, gif_path, frame_delay=0.1):
        frames = self.serial_module.prepare_gif(gif_path)
        all_frames = self.serial_module.precompute_frames(frames)
        
        # logger.info(f"Total pre-computed frames: {len(all_frames)}")
        frame_index = 0
        while mixer.music.get_busy():
            self.serial_module.send_image_data(all_frames[frame_index])
            frame_index = (frame_index + 1) % len(all_frames)
            time.sleep(frame_delay)

    def display_gif(self, gif_path, stop_event):
        frames = self.serial_module.prepare_gif(gif_path)
        all_frames = self.serial_module.precompute_frames(frames)
        frame_index = 0
        while not stop_event.is_set():
            self.serial_module.send_image_data(all_frames[frame_index])
            frame_index = (frame_index + 1) % len(all_frames)
            time.sleep(0.1)

    def display_image(self, image_path):
        try:
            # logger.info(f"Opening image: {image_path}")
            img = Image.open(image_path)
            width, height = img.size
            # logger.info(f"Image size: {width}x{height}")

            # Convert image to RGB mode if it's not already
            if img.mode != 'RGB':
                img = img.convert('RGB')

            if (width, height) != (240, 240):
                img = img.resize((240, 240))
                # logger.info("Image resized to 240x240")

            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            # logger.info("Sending image to display...")
            self.serial_module.send_image_data(img_byte_arr)
            # logger.info("Image sent to display")

        except Exception as e:
            logger.warning(f"Error in display_image: {e}")

    def start_listening_display(self, image_path):
        self.display_image(image_path)

    def stop_listening_display(self):
        self.serial_module.send_white_frames()

    def stop_animation(self):
        if hasattr(self, 'stop_event'):
            self.stop_event.set()
            self.display_thread.join()
        self.serial_module.send_white_frames()

    def send_white_frames(self):
        self.serial_module.send_white_frames()
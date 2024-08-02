import sys, os, ctypes, queue
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio.audioPlayer import AudioPlayerModule
from etc.define import *

import time, threading, io
from PIL import Image

class DisplayModule:
    def __init__(self, serial_module):
        self.player = AudioPlayerModule()
        self.serial = serial_module
        self.stop_display = threading.Event()
        self.display_thread = None
        self.display_queue = queue.Queue()
        self.is_running = False

    def fade_in_logo(self, logo_path, steps=7):
        print(f"Starting fade_in_logo with {logo_path}")
        try:
            self.serial.fade_image(logo_path, fade_in=True, steps=steps)
            print("Finished fade_in_logo")
        except Exception as e:
            print(f"Error in fade_in_logo: {str(e)}")

    def play_trigger_with_logo(self, trigger_audio, logo_path):
        print("Entering play_trigger_with_logo method")
        if self.serial.open(USBPort):
            print("Serial port opened successfully")
            try:
                self.player.play(trigger_audio)
                
                fade_thread = threading.Thread(target=self.fade_in_logo, args=(logo_path,))
                fade_thread.start()

                print(f"Is playing: {self.player.is_playing()}")
                while self.player.is_playing():
                    self.player.audio_clock.tick(10)

                print("Audio playback finished, waiting for fade_thread")
                fade_thread.join(timeout=15)

                if fade_thread.is_alive():
                    print("fade_thread did not complete within the timeout period")
                else:
                    print("fade_thread completed successfully")
            except Exception as e:
                print(f"Error in play_trigger_with_logo: {str(e)}")
        else: 
            print("Failed to open display port")
            try:
                self.player.play(trigger_audio)
                while self.player.is_playing():
                    self.player.audio_clock.tick(10)
            except Exception as e:
                print(f"Error playing audio: {str(e)}")
        print("Exiting play_trigger_with_logo method")

    def start_display_thread(self, image_path):
        self.stop_display.clear()
        self.display_thread = threading.Thread(target=self.display_image, args=(image_path,))
        self.display_thread.start()

    def stop_display_thread(self, timeout=5):
        if self.display_thread and self.display_thread.is_alive():
            print("Stopping display thread...")
            self.stop_display.set()
            self.display_thread.join(timeout=timeout)
            if self.display_thread.is_alive():
                print(f"Warning: Display thread did not stop within the {timeout}-second timeout period.")
            else:
                print("Display thread stopped successfully.")

    def _display_loop(self):
        while self.is_running:
            try:
                item = self.display_queue.get(timeout=0.1)
                if item is None:
                    break  # Exit signal received
                image_path, fade_in, steps = item
                self.serial.fade_image(image_path, fade_in=fade_in, steps=steps)
            except queue.Empty:
                continue  # No item in queue, continue looping
            except Exception as e:
                print(f"Error in display loop: {str(e)}")
        print("Display thread stopped")

    def queue_image(self, image_path, fade_in=True, steps=1):
        self.display_queue.put((image_path, fade_in, steps))

    def _force_stop_thread(self, thread):
        if not thread.is_alive():
            return

        exc = ctypes.py_object(SystemExit)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread.ident), exc)
        if res == 0:
            raise ValueError("Invalid thread ID")
        elif res != 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")
    
    def display_image(self, image_path):
        print(f"Starting display of image: {image_path}")
        start_time = time.time()
        display_timeout = 30  # 30 seconds timeout for entire display operation
        retry_delay = 0.5  # Delay between retries
        max_retries = 3

        try:
            with Image.open(image_path) as img:
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_data = img_byte_arr.getvalue()

            while not self.stop_display.is_set() and time.time() - start_time < display_timeout:
                for attempt in range(max_retries):
                    if self.stop_display.is_set():
                        print("Stop signal received. Exiting display_image.")
                        return

                    try:
                        print(f"Sending image data (Attempt {attempt + 1}/{max_retries})")
                        success = self.serial.send_image_data(img_data, timeout=5)
                        if success:
                            print("Image sent successfully")
                            time.sleep(0.1)  # Short delay before next display attempt
                            break
                        else:
                            print(f"Failed to send image (Attempt {attempt + 1}/{max_retries})")
                    except Exception as e:
                        print(f"Error sending image: {str(e)}")

                    if attempt < max_retries - 1:
                        print(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)

                if self.stop_display.wait(0.1):  # Check stop_display every 100ms
                    print("Stop signal received. Exiting display_image.")
                    return

            if time.time() - start_time >= display_timeout:
                print("Display operation timed out")

        except Exception as e:
            print(f"Error in display_image: {str(e)}")

        print("Exiting display_image method")

    def update_gif(self, gif_path, frame_delay=0.1):
        frames = self.serial.prepare_gif(gif_path)
        all_frames = self.serial.precompute_frames(frames)
        
        print(f"Total pre-computed frames: {len(all_frames)}")
        frame_index = 0
        print(f"Is playing: {self.player.is_playing()}")
        while self.player.is_playing():
            self.serial.send_image_data(all_frames[frame_index])
            frame_index = (frame_index + 1) % len(all_frames)
            time.sleep(frame_delay)

    def display_gif(self,gif_path, stop_event=threading.Event()):
        frames = self.serial.prepare_gif(gif_path)
        all_frames = self.serial.precompute_frames(frames)
        frame_index = 0
        while not stop_event.is_set():
            self.serial.send_image_data(all_frames[frame_index])
            frame_index = (frame_index + 1) % len(all_frames)
            time.sleep(0.1)

    def sync_audio_and_gif(self, audio_file, gif_path):
        if self.serial.open(USBPort):
            self.player.play(audio_file)
            
            gif_thread = threading.Thread(target=self.update_gif, args=(gif_path,))
            gif_thread.start()

            print(f"Is playing: {self.player.is_playing()}")
            while self.player.is_playing():
                self.player.audio_clock.tick(10)

            gif_thread.join()
            self.serial.send_white_frames()
        else: 
            print("Failed to display gif")
            self.player.play(audio_file)

            print(f"Is playing: {self.player.is_playing()}")
            while self.player.is_playing():
                self.player.audio_clock.tick(10)

    def close(self):
        self.stop_display_thread()
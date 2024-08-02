import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transmission.serialModule import SerialModule
from audio.audioPlayer import AudioPlayerModule
from etc.define import *

from PIL import Image
import time, io, threading

class DisplayModule:
    def __init__(self):
        self.player = AudioPlayerModule()
        self.serial = SerialModule(BautRate)
        self.stop_display = threading.Event()

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

    def display_image(self, image_path, stop_event):
        start_time = time.time()
        while not stop_event.is_set():
            try:
                self.serial.fade_image(image_path, fade_in=True, steps=1)
                for _ in range(10):  # Check stop_event more frequently
                    if stop_event.is_set():
                        break
                    time.sleep(0.01)
                if time.time() - start_time > 30:  # 30 seconds timeout
                    print("Display image timeout reached")
                    break
            except Exception as e:
                print(f"Error in display_image: {str(e)}")
                break
        print("Display thread stopped")

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
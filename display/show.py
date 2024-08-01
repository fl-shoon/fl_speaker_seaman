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
        self.display = SerialModule(BautRate)

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

            self.display.send_image_data(img_byte_arr)
            time.sleep(0.01) 

    def play_trigger_with_logo(self, trigger_audio, logo_path):
        if self.display.open(USBPort):
            self.player.play(trigger_audio)
            
            fade_thread = threading.Thread(target=self.fade_in_logo, args=(logo_path))
            fade_thread.start()

            print(f"Is playing: {self.player.is_playing()}")
            while self.player.is_playing():
                self.player.audio_clock.tick(10)

            fade_thread.join()
        else: 
            print("Failed to open display port")
            self.player.play(trigger_audio)
            print(f"Is playing: {self.player.is_playing()}")
            while self.player.is_playing():
                self.player.audio_clock.tick(10)

    def update_gif(self, gif_path, frame_delay=0.1):
        frames = self.display.prepare_gif(gif_path)
        all_frames = self.display.precompute_frames(frames)
        
        print(f"Total pre-computed frames: {len(all_frames)}")
        frame_index = 0
        print(f"Is playing: {self.player.is_playing()}")
        while self.player.is_playing():
            self.display.send_image_data(all_frames[frame_index])
            frame_index = (frame_index + 1) % len(all_frames)
            time.sleep(frame_delay)

    def display_image(self, image_path, stop_event):
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            img = img.resize((240, 240), Image.LANCZOS)
            
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_data = img_byte_arr.getvalue()

        while not stop_event.is_set():
            self.display.send_image_data(img_data)
            time.sleep(0.1)  

    def display_gif(self,gif_path, stop_event=threading.Event()):
        frames = self.display.prepare_gif(gif_path)
        all_frames = self.display.precompute_frames(frames)
        frame_index = 0
        while not stop_event.is_set():
            self.display.send_image_data(all_frames[frame_index])
            frame_index = (frame_index + 1) % len(all_frames)
            time.sleep(0.1)

    def sync_audio_and_gif(self, audio_file, gif_path):
        if self.display.open(USBPort):
            self.player.play(audio_file)
            
            gif_thread = threading.Thread(target=self.update_gif, args=(self.display, gif_path))
            gif_thread.start()

            print(f"Is playing: {self.player.is_playing()}")
            while self.player.is_playing():
                self.player.audio_clock.tick(10)

            gif_thread.join()
            self.display.send_white_frames()
        else: 
            print("Failed to display gif")
            self.player.play(audio_file)

            print(f"Is playing: {self.player.is_playing()}")
            while self.player.is_playing():
                self.player.audio_clock.tick(10)
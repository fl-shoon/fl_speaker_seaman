import serial, time, io
from PIL import Image
import numpy as np
from threading import Timer

class SerialModule:
    def __init__(self, baud_rate='230400'):
        self.isPortOpen = False
        self.baud_rate = baud_rate
        self.comm = None

    def open(self, tty):
        try:
            self.comm = serial.Serial(tty, self.baud_rate, timeout=0.1)
            self.isPortOpen = True
            print(f"Port opened successfully at {self.baud_rate} baud")
        except Exception as e:
            self.isPortOpen = False
            print(f"Failed to open port: {e}")
        return self.isPortOpen

    def send(self, data):
        self.comm.write(data)

    def send_text(self):
        self.send('test'.encode())
        time.sleep(0.01)
        self.comm.read_all()

    def send_image_data(self, img_data, timeout=5):
        if not self.isPortOpen or self.comm is None:
            print("Serial port is not open")
            return False

        print(f"Sending image data of size: {len(img_data)} bytes")
        
        try:
            print("Clearing input buffer...")
            self.comm.reset_input_buffer()
            print("Clearing output buffer...")
            self.comm.reset_output_buffer()
            
            print("Writing data...")
            self.comm.write(img_data)
            
            print("Flushing output...")
            self.comm.flush()
            
            print("Waiting for response...")
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.comm.in_waiting:
                    response = self.comm.read_all()
                    print(f"Received response: {response}")
                    return True
                time.sleep(0.1)
            
            print(f"No response received within {timeout} seconds")
            return False
            
        except serial.SerialTimeoutException:
            print("Timeout occurred while writing image data")
        except Exception as e:
            print(f"Error in send_image_data: {str(e)}")
        
        return False

    def fade_image(self, image_path, fade_in=True, steps=20):
        img = Image.open(image_path)
        width, height = img.size

        for i in range(steps):
            if fade_in:
                alpha = int(255 * (i + 1) / steps)
            else:
                alpha = int(255 * (steps - i) / steps)

            faded_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            faded_img.paste(img, (0, 0))
            faded_img.putalpha(alpha)

            rgb_img = Image.new("RGB", faded_img.size, (0, 0, 0))
            rgb_img.paste(faded_img, mask=faded_img.split()[3])

            img_byte_arr = io.BytesIO()
            rgb_img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            success = self.send_image_data(img_byte_arr)
            if not success:
                print(f"Failed to send image for step {i+1}, continuing to next step")
            
            time.sleep(0.05) 

    def send_white_frames(self, flash_delay=0.05, max_retries=3):
        white_frame = np.full((240, 240, 3), 255, dtype=np.uint8)
        white_frame_bytes = self.frame_to_bytes(white_frame)
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1}/{max_retries} to send white frame")
                print(f"White frame size: {len(white_frame_bytes)} bytes")
                start_time = time.time()
                success = self.send_image_data(white_frame_bytes, timeout=5)  # Add a 5-second timeout
                end_time = time.time()
                print(f"Time taken to send white frame: {end_time - start_time:.2f} seconds")
                if success:
                    print("White frame sent successfully")
                    time.sleep(flash_delay)
                    return True
                else:
                    print(f"Failed to send white frame (attempt {attempt + 1}/{max_retries})")
            except Exception as e:
                print(f"Error sending white frame: {str(e)}")
            if attempt < max_retries - 1:
                print("Retrying...")
                time.sleep(1)
        print("Failed to send white frames after all retries")
        return False

    def prepare_gif(self, gif_path, target_size=(240, 240)):
        gif = Image.open(gif_path)
        frames = []
        try:
            while True:
                gif.seek(gif.tell() + 1)
                frame = gif.copy().convert('RGB').resize(target_size)
                frames.append(np.array(frame))
        except EOFError:
            pass  # End of frames
        return frames

    def frame_to_bytes(self, frame):
        img = Image.fromarray(frame)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()

    def precompute_frames(self, frames):
        return [self.frame_to_bytes(frame) for frame in frames]

    def fade_image(self, image_path, fade_in=True, steps=20):
        img = Image.open(image_path)
        width, height = img.size

        for i in range(steps):
            if fade_in:
                alpha = int(255 * (i + 1) / steps)
            else:
                alpha = int(255 * (steps - i) / steps)

            faded_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            faded_img.paste(img, (0, 0))
            faded_img.putalpha(alpha)

            rgb_img = Image.new("RGB", faded_img.size, (0, 0, 0))
            rgb_img.paste(faded_img, mask=faded_img.split()[3])

            img_byte_arr = io.BytesIO()
            rgb_img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            self.send_image_data(img_byte_arr)
            time.sleep(0.001)  
            
    def animate_gif(self, gif_path, frame_delay=0.1):
        frames = self.prepare_gif(gif_path)
        all_frames = self.precompute_frames(frames)
        
        print(f"Total pre-computed frames: {len(all_frames)}")

        while True:
            for frame_bytes in all_frames:
                self.send_image_data(frame_bytes)
                time.sleep(frame_delay)

    def close(self):
        if self.isPortOpen and self.comm is not None:
            self.comm.close()
            self.isPortOpen = False
            print("Serial connection closed")
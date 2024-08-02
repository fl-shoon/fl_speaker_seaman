import serial, time, io
from PIL import Image
import numpy as np
from threading import Timer

class SerialModule:
    def __init__(self, baud_rate='230400'):
        self.isPortOpen = False
        self.baud_rate = baud_rate

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

    def send_image_data(self, img_data, timeout=5, retries=3):
        print(f"Sending image data of size: {len(img_data)} bytes")
        
        for attempt in range(retries):
            try:
                self.send_text()
                self.comm.read_all()  # Clear any remaining data
                
                send_complete = False
                def timeout_handler():
                    nonlocal send_complete
                    if not send_complete:
                        raise serial.SerialTimeoutException("Send operation timed out")

                timer = Timer(timeout, timeout_handler)
                timer.start()

                try:
                    bytes_written = self.comm.write(img_data)
                    send_complete = True
                    print(f"Bytes written: {bytes_written}")
                    
                    response = self.comm.read_all()
                    if response:
                        print(f"Received response after sending image: {response}")
                    
                    success = bytes_written == len(img_data)
                    print(f"Send operation {'successful' if success else 'failed'}")
                    return success
                finally:
                    timer.cancel()

            except serial.SerialTimeoutException:
                print(f"Timeout occurred while writing image data (attempt {attempt + 1}/{retries})")
            except Exception as e:
                print(f"Error in send_image_data: {str(e)} (attempt {attempt + 1}/{retries})")

            if attempt < retries - 1:
                print("Retrying...")
                time.sleep(1)  # Wait a bit before retrying

        print("Failed to send image data after all retries")
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

    def send_white_frames(self, flash_delay=0.05):
        white_frame = np.full((240, 240, 3), 255, dtype=np.uint8)
        white_frame_bytes = self.frame_to_bytes(white_frame)
        # Display white frame
        self.send_image_data(white_frame_bytes)
        time.sleep(flash_delay)

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
        if self.isPortOpen:
            self.comm.close()
            self.isPortOpen = False
            print("Serial connection closed")
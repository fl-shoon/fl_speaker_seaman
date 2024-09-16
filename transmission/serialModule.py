import serial, time, io, logging
from PIL import Image, ImageEnhance
import numpy as np
import RPi.GPIO as GPIO

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SerialModule:
    def __init__(self, baud_rate='230400'):
        self.isPortOpen = False
        self.baud_rate = baud_rate
        self.comm = None
        self.current_brightness = 1.0  
        self.current_image = None

        GPIO.setmode(GPIO.BCM)
        self.right_button_pin = 22  
        GPIO.setup(self.right_button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def open(self, tty):
        try:
            self.comm = serial.Serial(tty, self.baud_rate, timeout=0.1)
            self.isPortOpen = True
            logger.info(f"Port opened successfully at {self.baud_rate} baud")
        except Exception as e:
            self.isPortOpen = False
            logger.warning(f"Failed to open port: {e}")
        return self.isPortOpen

    def send(self, data):
        self.comm.write(data)

    def send_text(self):
        self.send('test'.encode())
        time.sleep(0.01)
        self.comm.read_all()

    def send_image_data(self, img_data, timeout=5, retries=3):
        if not self.isPortOpen or self.comm is None:
            logger.warning("Serial port is not open")
            return False

        if isinstance(img_data, bytes):
            img = Image.open(io.BytesIO(img_data))
        elif isinstance(img_data, Image.Image):
            img = img_data
        else:
            logger.warning("Unsupported image data type")
            return False

        # Apply brightness adjustment
        enhancer = ImageEnhance.Brightness(img)
        brightened_img = enhancer.enhance(self.current_brightness)

        # Convert the brightened image back to bytes
        img_byte_arr = io.BytesIO()
        brightened_img.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()

        for attempt in range(retries):
            try:
                self.send_text()
                self.comm.read_all()  
                self.comm.flush()  
                
                response_start_time = time.time()
                while time.time() - response_start_time < timeout:
                    if self.comm.in_waiting:
                        self.comm.read_all()
                        return True
                    time.sleep(0.1)
                
                logger.info(f"No response received within {timeout} seconds")
                
            except serial.SerialTimeoutException:
                logger.warning(f"Timeout occurred while writing image data (attempt {attempt + 1}/{retries})")
            except Exception as e:
                logger.warning(f"Error in send_image_data: {str(e)} (attempt {attempt + 1}/{retries})")
            
            if attempt < retries - 1:
                logger.info("Retrying...")
                time.sleep(1)
        
        logger.warning("Failed to send image data after all retries")
        return False

    def set_brightness(self, brightness):
        self.current_brightness = brightness
        logger.info(f"Brightness set to {self.current_brightness}")
        
    def check_right_button(self):
        return GPIO.input(self.right_button_pin) == GPIO.LOW
    
    def send_white_frames(self, flash_delay=0.05, max_retries=3, timeout=5):
        white_frame = np.full((240, 240, 3), 255, dtype=np.uint8)
        white_frame_bytes = self.frame_to_bytes(white_frame)

        for attempt in range(max_retries):
            try:
                start_time = time.time()
                
                self.comm.reset_input_buffer()
                self.comm.reset_output_buffer()
                
                self.comm.write(b'TEST')
                time.sleep(0.1)

                self.comm.flush()

                ack_received = False
                while time.time() - start_time < timeout:
                    if self.comm.in_waiting:
                        ack_received = True
                        break
                    time.sleep(0.1)

                if ack_received:
                    logger.info("Turned screen to white successfully")
                    time.sleep(flash_delay)
                    return True
                else:
                    logger.info(f"Failed to turn screen into white within {timeout} seconds")

            except Exception as e:
                logger.warning(f"Error in turning white screen: {str(e)}")

            if attempt < max_retries - 1:
                logger.info("Retrying...")
                time.sleep(1)

        logger.warning("Failed to send white frames after all retries")
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
            pass  
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
        
        while True:
            for frame_bytes in all_frames:
                self.send_image_data(frame_bytes)
                time.sleep(frame_delay)

    def set_current_image(self, image):
        self.current_image = image

    def set_brightness_image(self, brightness, steps=10, transition_time=0.5):
        if not self.isPortOpen or self.comm is None:
            logger.error("Serial port is not open")
            return False

        if self.current_image is None:
            logger.error("No current image to adjust brightness")
            return False

        start_brightness = self.current_brightness
        brightness_step = (brightness - start_brightness) / steps
        step_time = transition_time / steps

        for i in range(steps + 1):
            current_step_brightness = start_brightness + brightness_step * i
            try:
                # Adjust image brightness
                enhancer = ImageEnhance.Brightness(self.current_image)
                adjusted_image = enhancer.enhance(current_step_brightness)

                # Convert to bytes
                img_byte_arr = io.BytesIO()
                adjusted_image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()

                # Send to display
                self.send_image_data(img_byte_arr)
                
                logger.debug(f"Adjusted brightness to {current_step_brightness:.2f}")
                time.sleep(step_time)

            except Exception as e:
                logger.error(f"Error adjusting brightness: {str(e)}")
                return False

        self.current_brightness = brightness
        logger.info(f"Brightness adjustment completed. Final brightness: {brightness:.2f}")
        return True

    def close(self):
        if self.isPortOpen and self.comm is not None:
            self.comm.close()
            self.isPortOpen = False
            logger.info("Serial connection closed")
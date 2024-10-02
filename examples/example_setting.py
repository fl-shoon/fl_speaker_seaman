from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# from serialModule import SerialModule
from transmission.serialModule import SerialModule
# from brightness import BrightnessModule
# from volume import VolumeModule
from display.brightness import BrightnessModule

import RPi.GPIO as GPIO 
import time, io, math, logging, serial.tools.list_ports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_device():
    result = '/dev/ttyACM0'
    ports = [tuple(p) for p in list(serial.tools.list_ports.comports())]
    logger.info(ports)
    for device, description, _ in ports:
        if description == 'RP2040 LCD 1.28 - Board CDC' or 'RP2040' in description or 'LCD' in description:
            result = device
    return result  

class SettingModule:
    def __init__(self, serial_module):
        self.serial_module = serial_module
        self.background_color = (73, 80, 87)  # Darker gray for the background
        self.text_color = (255, 255, 255)  # White for text and icons
        self.highlight_color = (255, 255, 255)  # Light gray for highlighting
        self.display_size = (240, 240)
        self.highlight_text_color = (0, 0, 0)
        self.icon_size = 24
        self.font_path = "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"
        
        # GPIO setup
        GPIO.setmode(GPIO.BCM)
        self.buttons = {
            'up': 4,
            'down': 17,
            'left': 27,
            'right': 22
        }
        for pin in self.buttons.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        self.menu_items = [
            {'icon': 'volume', 'text': '音量'}, # y-position : 20
            {'icon': 'brightness', 'text': '輝度'}, # y-position : 60
            {'icon': 'character', 'text': 'キャラ'}, # y-position : 100
            {'icon': 'settings', 'text': '設定'}, # y-position : 140
            {'icon': 'exit', 'text': '終了'} # y-position : 180
        ]
        
        self.selected_item = 1  # Start with the second item selected (輝度/brightness)
        self.font = self.load_font()

        self.brightness = 1.0  # Full brightness
        self.brightness_control = BrightnessModule(serial_module, self.brightness)
        self.current_menu_image = None

        # self.volume_control = VolumeModule(serial_module, self.brightness)

    def load_font(self):
        font_paths = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",  
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  
        ]
        
        for font_path in font_paths:
            try:
                self.font_path = font_path
                return ImageFont.truetype(font_path, 20)
            except IOError:
                logging.warning(f"Could not load font: {font_path}")
        
        logging.error("Could not load any fonts. Using default font.")
        return ImageFont.load_default()
    
    def draw_icon(self, draw, icon, position, icon_color=(255, 255, 255)):
        x, y = position
        size = self.icon_size  

        if icon == 'volume':
            # Volume icon 
            icon_width = size * 0.9  
            icon_height = size * 0.9  
            speaker_width = icon_width * 0.4
            speaker_height = icon_height * 0.6

            # Calculate positions
            speaker_x = x + (size - speaker_width) // 2
            speaker_y = y + (size - speaker_height) // 2

            # Draw the speaker part
            draw.polygon([
                (speaker_x, speaker_y + speaker_height * 0.3),
                (speaker_x + speaker_width * 0.6, speaker_y + speaker_height * 0.3),
                (speaker_x + speaker_width, speaker_y),
                (speaker_x + speaker_width, speaker_y + speaker_height),
                (speaker_x + speaker_width * 0.6, speaker_y + speaker_height * 0.7),
                (speaker_x, speaker_y + speaker_height * 0.7)
            ], fill=icon_color)

            # Draw the three arcs
            arc_center_x = x + size * 0.7
            arc_center_y = y + size // 2
            for i in range(3):
                arc_radius = size * (0.15 + i * 0.1)  
                arc_bbox = [
                    arc_center_x - arc_radius,
                    arc_center_y - arc_radius,
                    arc_center_x + arc_radius,
                    arc_center_y + arc_radius
                ]
                draw.arc(arc_bbox, start=300, end=60, fill=icon_color, width=2)

        elif icon == 'brightness':
            # Half-filled sun icon
            center = size // 2
            
            # Draw the full circle outline
            draw.ellipse([x+size*0.17, y+size*0.17, x+size*0.83, y+size*0.83], outline=icon_color, width=2)
            
            # Fill the left half of the circle
            draw.pieslice([x+size*0.17, y+size*0.17, x+size*0.83, y+size*0.83], start=90, end=270, fill=icon_color)
            
            # Draw the rays
            for i in range(8):
                angle = i * 45
                x1 = x + center + int(size*0.58 * math.cos(math.radians(angle)))
                y1 = y + center + int(size*0.58 * math.sin(math.radians(angle)))
                x2 = x + center + int(size*0.42 * math.cos(math.radians(angle)))
                y2 = y + center + int(size*0.42 * math.sin(math.radians(angle)))
                draw.line([x1, y1, x2, y2], fill=icon_color, width=2)

        elif icon == 'character':
            # Smiling face icon 
            padding = size * 0.1
            center_x = x + size // 2
            center_y = y + size // 2
            face_radius = (size - 2 * padding) // 2

            # Draw the face outline
            draw.ellipse([x + padding, y + padding, x + size - padding, y + size - padding], outline=icon_color, width=2)

            # Draw eyes 
            eye_radius = size * 0.06
            eye_offset = face_radius * 0.35
            left_eye_center = (center_x - eye_offset, center_y - eye_offset)
            right_eye_center = (center_x + eye_offset, center_y - eye_offset)
            draw.ellipse([left_eye_center[0] - eye_radius, left_eye_center[1] - eye_radius,
                          left_eye_center[0] + eye_radius, left_eye_center[1] + eye_radius], fill=icon_color)
            draw.ellipse([right_eye_center[0] - eye_radius, right_eye_center[1] - eye_radius,
                          right_eye_center[0] + eye_radius, right_eye_center[1] + eye_radius], fill=icon_color)

            # Draw a smile 
            smile_y = center_y + face_radius * 0.1  
            smile_width = face_radius * 0.9  
            smile_height = face_radius * 0.7  
            smile_bbox = [center_x - smile_width/2, smile_y - smile_height/2,
                          center_x + smile_width/2, smile_y + smile_height/2]
            draw.arc(smile_bbox, start=0, end=180, fill=icon_color, width=2)
            
        elif icon == 'settings':
            # Solid gear icon with square teeth
            center = size // 2
            outer_radius = size * 0.45
            num_teeth = 8
            tooth_depth = size * 0.15
            tooth_width = size * 0.12

            # Create a list to hold the points of the gear
            gear_shape = []

            for i in range(num_teeth * 2):
                angle = i * (360 / (num_teeth * 2))
                if i % 2 == 0:
                    # Outer points (teeth)
                    x1 = x + center + outer_radius * math.cos(math.radians(angle - 360/(num_teeth*4)))
                    y1 = y + center + outer_radius * math.sin(math.radians(angle - 360/(num_teeth*4)))
                    x2 = x + center + outer_radius * math.cos(math.radians(angle + 360/(num_teeth*4)))
                    y2 = y + center + outer_radius * math.sin(math.radians(angle + 360/(num_teeth*4)))
                    gear_shape.extend([(x1, y1), (x2, y2)])
                else:
                    # Inner points (between teeth)
                    x1 = x + center + (outer_radius - tooth_depth) * math.cos(math.radians(angle - tooth_width))
                    y1 = y + center + (outer_radius - tooth_depth) * math.sin(math.radians(angle - tooth_width))
                    x2 = x + center + (outer_radius - tooth_depth) * math.cos(math.radians(angle + tooth_width))
                    y2 = y + center + (outer_radius - tooth_depth) * math.sin(math.radians(angle + tooth_width))
                    gear_shape.extend([(x1, y1), (x2, y2)])

            # Draw the gear as a single polygon
            draw.polygon(gear_shape, fill=icon_color)

            # Draw a small circle in the center
            center_radius = size * 0.15
            draw.ellipse([x + center - center_radius, y + center - center_radius,
                          x + center + center_radius, y + center + center_radius],
                         fill=self.background_color)

        elif icon == 'exit':
            # X icon
            draw.line([x+size*0.17, y+size*0.17, x+size*0.83, y+size*0.83], fill=icon_color, width=3)
            draw.line([x+size*0.17, y+size*0.83, x+size*0.83, y+size*0.17], fill=icon_color, width=3)

    def update_display(self):
        # Create a base image
        image = Image.new('RGB', self.display_size, self.background_color)
        draw = ImageDraw.Draw(image)

        # Drawing highlight
        y_position = 15 + self.selected_item * 40
        draw.rounded_rectangle([45, y_position, 185, y_position+35], radius = 8, fill=self.highlight_color)

        for i, item in enumerate(self.menu_items):
            y_position = 20 + i * 40
            # Choose text and icon color based on whether this item is selected
            selected_color = self.highlight_text_color if i == self.selected_item else self.text_color
            self.draw_icon(draw, item['icon'], (60, y_position), icon_color=selected_color)
            
            draw.text((90, y_position), item['text'], font=self.font, fill=selected_color)
        
        # Draw navigation buttons
        draw.polygon([(20, 120), (30, 110), (30, 130)], fill=self.text_color)  # Left arrow
        draw.polygon([(220, 120), (210, 110), (210, 130)], fill=self.text_color)  # Right arrow
        fixFont = ImageFont.truetype(self.font_path, 12)
        draw.text((20, 135), "戻る", font=fixFont, fill=self.text_color)
        draw.text((200, 135), "決定", font=fixFont, fill=self.text_color)

        self.current_menu_image = image
        
        self.serial_module.send_image_data(image)

    def check_buttons(self):
        if GPIO.input(self.buttons['up']) == GPIO.LOW:
            self.selected_item = max(0, self.selected_item - 1)
            self.update_display()
            time.sleep(0.2)
        elif GPIO.input(self.buttons['down']) == GPIO.LOW:
            self.selected_item = min(len(self.menu_items) - 1, self.selected_item + 1)
            self.update_display()
            time.sleep(0.2)
        elif GPIO.input(self.buttons['right']) == GPIO.LOW:
            if self.selected_item == 1: # Brightness control
                self.serial_module.set_current_image(self.current_menu_image)  # Ensure current image is set
                action, new_brightness = self.brightness_control.run()
                if action == 'confirm':
                    self.brightness = new_brightness
                    self.serial_module.set_brightness_image(self.brightness)
                    logger.info(f"Brightness updated to {self.brightness:.2f}")
                else:
                    logger.info("Brightness adjustment cancelled")
                self.update_display()
            # elif self.selected_item == 0: # Volume control
            #     self.serial_module.set_current_image(self.current_menu_image)  # Ensure current image is set
            #     action, new_brightness = self.volume_control.run()
            #     if action == 'confirm':
            #         self.brightness = new_brightness
            #         self.serial_module.set_brightness_image(self.brightness)
            #         logger.info(f"Volume updated to {self.brightness:.2f}")
            #     else:
            #         logger.info("Volume adjustment cancelled")
            #     self.update_display()
            time.sleep(0.2)
        elif GPIO.input(self.buttons['left']) == GPIO.LOW:
            return 'back'

    def run(self):
        try:
            self.update_display()  
            while True:
                action = self.check_buttons()
                if action == 'back':
                    logger.info("Returning to main app.")
                    return 'exit', self.brightness
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.error("\nProgram terminated by user")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
        finally:
            logger.info("Cleaning up...")
            GPIO.cleanup()
            logger.info("Sending white frames...")
            self.serial_module.send_white_frames()
            logger.info("Closing serial connection...")
            self.serial_module.close()
            logger.info("Program ended")

# if __name__ == "__main__":
#     serial_module = SerialModule()
#     if serial_module.open(extract_device()):  
#         ui = SettingModule(serial_module)
#         ui.run()
#     else:
#         logger.info("Failed to open serial port")
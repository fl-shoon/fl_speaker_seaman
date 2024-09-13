import RPi.GPIO as GPIO 
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io, time, math, logging

logging.basicConfig(level=logging.INFO)

class VolumeModule:
    def __init__(self, serial_module, initial_brightness=0.5):
        self.serial_module = serial_module
        self.background_color = (73, 80, 87)
        self.text_color = (255, 255, 255)
        self.highlight_color = (0, 119, 255)
        self.display_size = (240, 240)
        self.initial_brightness = initial_brightness
        self.current_brightness = initial_brightness
        self.font_path = "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"

        self.buttons = {
            'up': 4,
            'down': 17,
            'left': 27,
            'right': 22
        }
        for pin in self.buttons.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self.font = self.load_font()

    def load_font(self):
        font_paths = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",  
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  
        ]
        
        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, 20)
            except IOError:
                logging.warning(f"Could not load font: {font_path}")
        
        logging.error("Could not load any fonts. Using default font.")
        return None
    
    def create_brightness_image(self):
        if self.font is None:
            return None
        
        image = Image.new('RGB', self.display_size, self.background_color)
        draw = ImageDraw.Draw(image)

        # Draw brightness icon and text
        icon_size = 24
        icon_x = self.display_size[0] // 2 - icon_size // 2
        icon_y = 20
        self.draw_icon(draw, 'brightness', (icon_x, icon_y))
        
        small_font = ImageFont.truetype(self.font_path, 14)
        text = "輝度"
        text_bbox = draw.textbbox((0, 0), text, font=small_font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = self.display_size[0] // 2 - text_width // 2
        draw.text((text_x, icon_y + icon_size + 5), text, font=small_font, fill=self.text_color)

        # Draw vertical brightness bar
        bar_width = 20
        bar_height = 140
        bar_x = (self.display_size[0] - bar_width) // 2
        bar_y = 80
        draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], outline=self.text_color)
        filled_height = int(bar_height * self.current_brightness)
        draw.rectangle([bar_x, bar_y + bar_height - filled_height, bar_x + bar_width, bar_y + bar_height], fill=self.highlight_color)

        # Draw white horizontal bar (slider)
        slider_width = 30
        slider_height = 4
        slider_y = bar_y + bar_height - filled_height - slider_height // 2
        draw.rectangle([bar_x - (slider_width - bar_width) // 2, slider_y, 
                        bar_x + bar_width + (slider_width - bar_width) // 2, slider_y + slider_height], 
                    fill=self.text_color)

        # Draw brightness value in a circle
        value_size = 30
        value_x = bar_x + bar_width + 20
        value_y = slider_y + slider_height // 2
        draw.ellipse([value_x, value_y - value_size//2, value_x + value_size, value_y + value_size//2], fill=self.text_color)
        brightness_percentage = int(self.current_brightness * 100)
        percentage_font = ImageFont.truetype(self.font_path, 14)
        percentage_text = f"{brightness_percentage}"
        text_bbox = draw.textbbox((0, 0), percentage_text, font=percentage_font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = value_x + (value_size - text_width) // 2
        text_y = value_y - text_height // 2
        vertical_adjustment = -1  
        text_y += vertical_adjustment
        draw.text((text_x, text_y), percentage_text, font=percentage_font, fill=self.background_color)

        # Draw navigation buttons
        draw.polygon([(20, 120), (30, 110), (30, 130)], fill=self.text_color)  # Left arrow
        draw.polygon([(220, 120), (210, 110), (210, 130)], fill=self.text_color)  # Right arrow
        fixFont = ImageFont.truetype(self.font_path, 12)
        draw.text((20, 135), "戻る", font=fixFont, fill=self.text_color)
        draw.text((200, 135), "決定", font=fixFont, fill=self.text_color)

        return image

    def update_display(self):
        image = self.create_brightness_image()
        
        # Apply current brightness to the image
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(self.current_brightness)

        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()

        self.serial_module.send_image_data(img_byte_arr)

    def draw_icon(self, draw, icon, position):
        x, y = position
        size = 24  

        if icon == 'brightness':
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
            ], fill=self.text_color)

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
                draw.arc(arc_bbox, start=300, end=60, fill=self.text_color, width=2)

    def check_buttons(self):
        if GPIO.input(self.buttons['up']) == GPIO.LOW:
            self.current_brightness = min(1.0, self.current_brightness + 0.05)
            self.update_display()
            time.sleep(0.2)
            return 'adjust'
        elif GPIO.input(self.buttons['down']) == GPIO.LOW:
            self.current_brightness = max(0.0, self.current_brightness - 0.05)
            self.update_display()
            time.sleep(0.2)
            return 'adjust'
        elif GPIO.input(self.buttons['left']) == GPIO.LOW:
            return 'back'
        elif GPIO.input(self.buttons['right']) == GPIO.LOW:
            return 'confirm'
        return None

    def run(self):
        image = self.create_brightness_image()
        if image is None:
            return 'back', self.current_brightness
        self.update_display()
        while True:
            action = self.check_buttons()
            if action == 'back':
                # Revert to initial brightness without saving
                self.current_brightness = self.initial_brightness
                return 'back', self.current_brightness
            elif action == 'confirm':
                # Save the new brightness
                return 'confirm', self.current_brightness
            time.sleep(0.1)
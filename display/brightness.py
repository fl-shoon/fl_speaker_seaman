import RPi.GPIO as GPIO 
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io
import time
import math

class BrightnessModule:
    def __init__(self, serial_module, initial_brightness=0.5):
        self.serial_module = serial_module
        self.background_color = (73, 80, 87)
        self.text_color = (255, 255, 255)
        self.highlight_color = (0, 119, 255)
        self.display_size = (240, 240)
        self.initial_brightness = initial_brightness
        self.current_brightness = initial_brightness

        self.buttons = {
            'up': 4,
            'down': 17,
            'left': 27,
            'right': 22
        }
        for pin in self.buttons.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        self.font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 20)

    def create_brightness_image(self):
        image = Image.new('RGB', self.display_size, self.background_color)
        draw = ImageDraw.Draw(image)

        # Draw brightness icon and text
        self.draw_icon(draw, 'brightness', (120, 40))
        draw.text((100, 80), "輝度", font=self.font, fill=self.text_color)

        # Draw brightness bar
        bar_width = 140
        bar_height = 20
        bar_x = (self.display_size[0] - bar_width) // 2
        bar_y = 120
        draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], outline=self.text_color)
        filled_width = int(bar_width * self.current_brightness)
        draw.rectangle([bar_x, bar_y, bar_x + filled_width, bar_y + bar_height], fill=self.highlight_color)

        # Draw brightness value
        brightness_percentage = int(self.current_brightness * 100)
        draw.text((110, 150), f"{brightness_percentage}%", font=self.font, fill=self.text_color)

        # Draw navigation buttons
        draw.polygon([(20, 120), (30, 110), (30, 130)], fill=self.text_color)  # Left arrow
        draw.polygon([(220, 120), (210, 110), (210, 130)], fill=self.text_color)  # Right arrow
        navigationTextFont = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 12)
        draw.text((20, 135), "戻る", font=navigationTextFont, fill=self.text_color)
        draw.text((200, 135), "決定", font=navigationTextFont, fill=self.text_color)

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
            center = size // 2
            draw.ellipse([x-size//2, y-size//2, x+size//2, y+size//2], outline=self.text_color, width=2)
            draw.pieslice([x-size//2, y-size//2, x+size//2, y+size//2], start=90, end=270, fill=self.text_color)
            for i in range(8):
                angle = i * 45
                x1 = x + int(size*0.58 * math.cos(math.radians(angle)))
                y1 = y + int(size*0.58 * math.sin(math.radians(angle)))
                x2 = x + int(size*0.42 * math.cos(math.radians(angle)))
                y2 = y + int(size*0.42 * math.sin(math.radians(angle)))
                draw.line([x1, y1, x2, y2], fill=self.text_color, width=2)

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
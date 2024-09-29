"""usbserial4a example with UI.

This example directly works on Android 6.0+ with Pydroid App.
And it also works on main stream desktop OS like Windows, Linux and OSX.
To make it work on Android 4.0+, please follow the readme file on
https://github.com/jacklinquan/usbserial4a
"""

import json
import time
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.behaviors import CompoundSelectionBehavior
from kivy.core import window
from kivy.clock import mainthread
from kivy.utils import platform
from kivy.clock import Clock
from kivy.core.audio import SoundLoader

import threading
import sys

DEBUG = True

# Motor Params
NEUTRAL = 1500
OFFSET = 150
OPEN_USEC = NEUTRAL - OFFSET
CLOSE_USEC = NEUTRAL + OFFSET
TIMEOUT = 4

OPEN_VALUE = -600

# Buttons
LEFT = 0
RIGHT = 1
DOWN = 2
UP = 3
RIGHTSIDE = 4
LEFTSIDE = 5

if platform == "android":
    from usb4a import usb
    from usbserial4a import serial4a
else:
    from serial.tools import list_ports
    from serial import Serial
import time


class FocusButton(FocusBehavior, Button):
    def on_focus(self, instance, value, *largs):
        if value:
            self.background_color = (0, 1, 1, 1)
        else:
            self.background_color = (1, 1, 1, 1)


class FocusBoxLayout(FocusBehavior, CompoundSelectionBehavior, BoxLayout):
    pass


def openPort(device_name):
    serial_port = None
    if platform == "android":
        device = usb.get_usb_device(device_name)
        if not device:
            raise Exception("Device {} not present!".format(device_name))
        if not usb.has_usb_permission(device):
            usb.request_usb_permission(device)
            return None
        serial_port = serial4a.get_serial_port(
            device_name, 230400, 8, "N", 1, timeout=0.5
        )
    else:
        serial_port = Serial(device_name, 230400, 8, "N", 1, timeout=0.5)
    return serial_port


kv = """
FocusBoxLayout:
    id: box_root
    on_parent: app.uiDict['box_root'] = self
    orientation: 'vertical'
    
    Label:
        size_hint_y: None
        height: '50dp'
        text: 'Seaman Demo'
        font_size: '20sp'
        bold: True
    Label:
        id: status_label
        on_parent: app.uiDict['status_label'] = self
        size_hint_y: None
        height: '50dp'
        text: ''
    Label:
        id: accel_label
        on_parent: app.uiDict['accel_label'] = self
        size_hint_y: None
        height: '50dp'
        text: ''
    Label:
        id: buttons_label
        on_parent: app.uiDict['buttons_label'] = self
        size_hint_y: None
        height: '50dp'
        text: ''
    Label:
        id: inputs_label
        on_parent: app.uiDict['inputs_label'] = self
        size_hint_y: None
        height: '50dp'
        text: ''
    FocusButton:
        id: btn_open0
        on_parent: app.uiDict['btn_open0'] = self
        size_hint_y: None
        height: '50dp'
        text: 'Open LCD'
        keyboard_mode: 'managed'
        on_press: app.on_btn0_press()
    FocusButton:
        id: btn_open1
        on_parent: app.uiDict['btn_open1'] = self
        size_hint_y: None
        height: '50dp'
        text: 'Open MCU'
        keyboard_mode: 'managed'
        on_press: app.on_btn1_press()
    FocusButton:
        id: btn_start
        on_parent: app.uiDict['btn_start'] = self
        size_hint_y: None
        height: '50dp'
        text: 'Start Control'
        keyboard_mode: 'managed'
        disabled: True
        on_press: app.on_btn_press()
    FocusButton:
        id: btn_exit
        on_parent: app.uiDict['btn_exit'] = self
        size_hint_y: None
        height: '50dp'
        text: 'App Exit'
        keyboard_mode: 'managed'
        on_press: app.stop()
"""


class MainApp(App):
    """
    Kivy Application Lifecycle
    ============================

    1) Application Class Definition: You define a subclass of App. 
    This subclass usually includes the build() method. (e.g class MainApp(App))
    2) Starting the App: When you call the run() method on an instance of your App subclass, 
    Kivy starts the application. (e.g MainApp().run())
    3) Calling build(): The run() method internally calls the build() method 
    to get the root widget of the application. 
    This root widget is then added to the window and displayed.
    """
    def __init__(self, *args, **kwargs):
        self.uiDict = {}
        self.device_name_list = []
        self.serial_port = None
        self.read_thread = None
        self.port_thread_lock = threading.Lock()
        self.lcd = None
        self.mcu = None
        self.mode = "idle"
        self.cover = "unknown"
        self.motor_begin = 0
        self.toggle = False
        self.sound = None
        self.offset = 0
        super(MainApp, self).__init__(*args, **kwargs)

    def build(self):
        """
         In a Kivy application, the build() method is a special method 
         that is automatically called by the Kivy framework when the app is started. 
         
         When you run a Kivy application, 
         the framework looks for the build() method in the App subclass 
         to construct and initialize the user interface of the application.
        """

        """
        Binding joystick button event: 

        window.Window.bind(on_joy_button_down=self.key_action) 
        binds the on_joy_button_down event to the key_action method of the class instance. 
        When a joystick button is pressed, the key_action method will be called.
        """
        window.Window.bind(on_joy_button_down=self.key_action)
        window.Window.bind(on_key_down=self.on_key_down)

        """
        Loading the KV string: 
        return Builder.load_string(kv) loads and 
        returns the UI components defined in the kv string. 
        This string typically contains the layout and widgets of the Kivy application.
        """
        return Builder.load_string(kv)

    def getFocusPrev(self):
        old = self.buttons[self.focused]
        for i in range(len(self.buttons)):
            self.focused = (self.focused - 1) % len(self.buttons)
            next = self.buttons[self.focused]
            if next and not next.disabled:
                break
        if old:
            old.focus = False
        if next:
            next.focus = True

    def getFocusNext(self):
        old = self.buttons[self.focused]
        for i in range(len(self.buttons)):
            self.focused = (self.focused + 1) % len(self.buttons)
            next = self.buttons[self.focused]
            if next and not next.disabled:
                break
        if old:
            old.focus = False
        if next:
            next.focus = True

    def on_key_down(self, *args):
        """
        In the on_key_down method, the key codes 
        273, 274, 32, ...
        correspond to specific keys on the keyboard:
        """
        print("button:", args[1], self.focused)
        if args[1] == 273: # Up arrow key
            self.getFocusPrev()
        if args[1] == 274: # Down arrow key
            self.getFocusNext()
        elif args[1] == 32: # Spacebar
            focused = self.buttons[self.focused]
            if focused:
                focused.dispatch("on_press")
        elif args[1] == 50: # '2' key
            if self.mode == "idle":
                self.offset += 10
                print("offset:", self.offset)
                self.command("setServo", {"usec": NEUTRAL + self.offset})
        elif args[1] == 56: # '8' key
            if self.mode == "idle":
                self.offset -= 10
                print("offset:", self.offset)
                self.command("setServo", {"usec": NEUTRAL + self.offset})


    def key_action(self, src, stickid, buttonid):
        """
        In the key_action method, the key codes 
        11, 12, 4, 0
        correspond to specific keys on the joystick or gamepad.

        When a joystick or gamepad button is pressed, 
        the key_action method will be called by the Kivy framework, 
        and it will receive the following arguments:
        1) src: The source of the event 
        (typically the instance of the Window).
        2) stickid: The ID of the joystick or gamepad.
        3) buttonid: The ID of the button that was pressed.
        """
        print("button:", buttonid, self.mode)
        if buttonid == 11:  # up
            self.getFocusPrev()
        elif buttonid == 12:  # down
            self.getFocusNext()
        elif buttonid == 4:  # back
            self.stop()
        elif buttonid == 0:  # ok
            focused = self.buttons[self.focused]
            if focused:
                focused.dispatch("on_press")

    def command(self, method, params=None):
        m = {"method": method}
        if params is not None:
            m["params"] = params
        # self.mcu.read_all()
        self.mcu.write(bytes(json.dumps(m), "utf-8") + b"\n")
        b = self.mcu.read_until().decode("utf-8").strip()
        try:
            res = json.loads(b)
            result = res.get("result")
            error = res.get("error")
        except:
            return None
        if error is not None:
            raise (error)
        return result

    def on_start(self, *args):
        """
        Automatically get called when the application starts and is ready to run.

        """
        SoundLoader.load("assets/silent.wav").play()
        self.focused = 0
        self.buttons = [
            None,
            self.uiDict["btn_open0"],
            self.uiDict["btn_open1"],
            self.uiDict["btn_start"],
            self.uiDict["btn_exit"],
        ]
        self.device_name_list = []

        if platform == "android":
            usb_device_list = usb.get_usb_device_list()
            self.device_name_list = [
                device.getDeviceName()
                for device in usb_device_list
                if device.getVendorId() == 0x2E8A  # rp2040 only
            ]
        else:
            usb_device_list = list_ports.comports()
            self.device_name_list = [
                port.device
                for port in usb_device_list
                if port.device.startswith("/dev/cu.usb")
            ]

        self.device_name_list.sort()
        print(self.device_name_list)
        Clock.schedule_once(self.on_btn0_press, 4)
        Clock.schedule_once(self.on_btn1_press, 5)

    def error(self, msg):
        print(msg)
        self.on_stop()
        self.uiDict["btn_open0"].disabled = False
        self.uiDict["btn_open1"].disabled = False
        self.uiDict["btn_start"].disabled = True
        Clock.schedule_once(self.on_start, 6)

    def on_btn0_press(self, *args):
        if self.lcd and self.lcd.is_open:
            self.lcd.close()
        print("try lcd open")
        if len(self.device_name_list) < 1:
            print("not found lcd device")
            return
        self.lcd = openPort(self.device_name_list[1])
        if self.lcd is not None:
            self.uiDict["btn_open0"].disabled = True
            if self.mcu is not None:
                self.uiDict["btn_start"].disabled = False
                Clock.schedule_once(self.on_btn_press, 1)
        else:
            Clock.schedule_once(self.on_btn0_press, 6)

    def on_btn1_press(self, *args):
        if self.mcu and self.mcu.is_open:
            self.mcu.close()
        print("try mcu open")
        if len(self.device_name_list) < 2:
            print("not found lcd device")
            return
        self.mcu = openPort(self.device_name_list[0])
        if self.mcu is not None:
            self.uiDict["btn_open1"].disabled = True
            if self.lcd is None:
                Clock.schedule_once(self.on_btn0_press, 3)
            else:
                self.uiDict["btn_start"].disabled = False
                Clock.schedule_once(self.on_btn_press, 1)
        else:
            Clock.schedule_once(self.on_btn1_press, 6)

    def on_btn_press(self, *args):
        if self.lcd is None or self.mcu is None:
            return
        self.command("setServo", {"usec": NEUTRAL + self.offset})
        self.showImage("assets/logo.png")
        self.schedule = Clock.schedule_interval(self.interval, 1 / 15)
        self.uiDict["btn_start"].disabled = True

    def showImage(self, fname):
        if self.lcd is None:
            return
        self.lcd.read_all()
        self.lcd.write(open(fname, "rb").read())

    def interval(self, dt):
        if self.lcd is None or self.mcu is None:
            return
        try:
            accel = [0.0, 0.0, 0.0]
            # gyro = (0.0, 0.0, 0.0)
            # self.lcd.read_all()
            if self.lcd.write(b"\n"):
                res = self.lcd.read_until().decode("utf-8")
                fields = [f.strip() for f in res.split(",")]
                if len(fields) == 7:
                    # tm = int(fields[0])
                    accel[0] = float(fields[1])
                    accel[1] = float(fields[2])
                    accel[2] = float(fields[3])
                    # gyro = tuple(float(a) for a in fields[4:7])
                    # print(tm, accel, gyro)
            if DEBUG:
                self.uiDict["status_label"].text = " ".join([self.cover, self.mode])
                self.uiDict["accel_label"].text = " ".join([str(s) for s in accel])
            info = self.command("getInputs")
            if info is None:
                return
            if DEBUG:
                self.uiDict["inputs_label"].text = repr(info)
            buttons = info.get("buttons")
            if buttons is None:
                return
            if DEBUG:
                self.uiDict["buttons_label"].text = repr(buttons)
                self.uiDict["inputs_label"].text = " ".join(
                    [
                        str(info["thermal"]),
                        str(info["ir_detect"]),
                        str(info["luminosity"]),
                    ]
                )
            if self.mode == "idle" and self.cover == "unknown":
                self.mode = "calibration"
            if self.mode == "calibration":
                if accel[0] < -500:
                    self.command("setServo", {"usec": OPEN_USEC + self.offset})  # open
                else:
                    self.mode = "cover-close"
                    self.motor_begin = time.time()
            elif self.mode == "idle":
                if buttons[DOWN]:
                    self.command("setServo", {"usec": OPEN_USEC + self.offset})  # open
                elif buttons[UP]:
                    self.command(
                        "setServo", {"usec": CLOSE_USEC + self.offset}
                    )  # close
                elif buttons[RIGHT] and self.cover != "open":
                    self.mode = "cover-open"
                    self.motor_begin = time.time()
                elif buttons[LEFT] and self.cover != "close":
                    self.mode = "cover-close"
                    self.motor_begin = time.time()
                elif buttons[LEFTSIDE]:
                    if self.sound is None:
                        self.sound = SoundLoader.load("assets/short44100c2.wav")
                    if self.sound:
                        print("Sound found at %s" % self.sound.source)
                        print("Sound is %.3f seconds" % self.sound.length)
                        self.sound.play()
                elif buttons[RIGHTSIDE]:
                    self.toggle = not self.toggle
                    if self.toggle:
                        self.showImage("assets/face.png")
                    else:
                        self.showImage("assets/logo.png")
                else:
                    self.command("setServo", {"usec": NEUTRAL + self.offset})
                    # image update timing is here !
            elif self.mode == "cover-open":
                if accel[0] < OPEN_VALUE or time.time() - self.motor_begin > TIMEOUT:
                    self.command("setServo", {"usec": NEUTRAL + self.offset})
                    self.mode = "idle"
                    self.cover = "open"
                    print(self.cover, accel[0])
                else:
                    self.command("setServo", {"usec": OPEN_USEC + self.offset})  # open
            elif self.mode == "cover-close":
                if accel[0] > -100 or time.time() - self.motor_begin > TIMEOUT:
                    self.command("setServo", {"usec": NEUTRAL + self.offset})
                    self.cover = "close"
                    self.mode = "idle"
                    print(self.cover, accel[0])
                else:
                    self.command(
                        "setServo", {"usec": CLOSE_USEC + self.offset}
                    )  # close
        except Exception as ex:
            self.error(ex)

    def on_stop(self):
        if self.mcu and self.mcu.is_open:
            try:
                self.command("setServo", {"usec": NEUTRAL + self.offset})
            except:
                pass
            self.mcu.close()
            self.mcu = None
        if self.lcd and self.lcd.is_open:
            self.lcd.close()
            self.lcd = None


if __name__ == "__main__":
    MainApp().run()

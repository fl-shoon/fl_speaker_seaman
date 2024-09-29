import serial
import json
import time

NEUTRAL = 1500
OFFSET = 150
OPEN_USEC = NEUTRAL - OFFSET
CLOSE_USEC = NEUTRAL + OFFSET
TIMEOUT = 4
OPEN_VALUE = -600

class MCUCOM:
    def __init__(self, port="/dev/ttyACM0", baudrate=230400):
        self.serial = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  
        self.offset = 0
        self.mode = "idle"
        self.cover = "unknown"
        self.motor_begin = 0

    def command(self, method, params=None):
        message = {"method": method}
        if params:
            message["params"] = params
        
        self.serial.write(json.dumps(message).encode() + b'\n')
        response = self.serial.readline().decode().strip()
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            print(f"Failed to parse response: {response}")
            return None

    def get_mcu_data(self):
        return self.command("getInputs")

    def set_servo(self, usec):
        return self.command("setServo", {"usec": usec})

    def run(self, duration=60):
        end_time = time.time() + duration

        self.set_servo(NEUTRAL + self.offset)

        while time.time() < end_time:
            mcu_data = self.get_mcu_data()
            if mcu_data and 'result' in mcu_data:
                result = mcu_data['result']
                buttons = result['buttons']
                accel = [0.0, 0.0, 0.0]  
                
                # print(f"Mode: {self.mode}, Cover: {self.cover}")

                if self.mode == "idle" and self.cover == "unknown":
                    self.mode = "calibration"

                if self.mode == "calibration":
                    if accel[0] < -500:
                        self.set_servo(OPEN_USEC + self.offset)
                    else:
                        self.mode = "cover-close"
                        self.motor_begin = time.time()

                elif self.mode == "idle":
                    # DOWN
                    if buttons[2]:  
                        self.set_servo(OPEN_USEC + self.offset)
                    
                    # UP
                    elif buttons[3]:  
                        self.set_servo(CLOSE_USEC + self.offset)
                    
                    # RIGHT
                    elif buttons[1] and self.cover != "open":  
                        self.mode = "cover-open"
                        self.motor_begin = time.time()
                    
                    # LEFT
                    elif buttons[0] and self.cover != "close":  
                        self.mode = "cover-close"
                        self.motor_begin = time.time()
                    else:
                        self.set_servo(NEUTRAL + self.offset)

                elif self.mode == "cover-open":
                    if accel[0] < OPEN_VALUE or time.time() - self.motor_begin > TIMEOUT:
                        self.set_servo(NEUTRAL + self.offset)
                        self.mode = "idle"
                        self.cover = "open"
                        print(f"Cover opened. Accel: {accel[0]}")
                    else:
                        self.set_servo(1300)

                elif self.mode == "cover-close":
                    if accel[0] > -100 or time.time() - self.motor_begin > TIMEOUT:
                        self.set_servo(NEUTRAL + self.offset)
                        self.cover = "close"
                        self.mode = "idle"
                    else:
                        self.set_servo(CLOSE_USEC + self.offset)

            else:
                print("Failed to retrieve sensor data")
            
            time.sleep(1/15)  

    def close(self):
        self.set_servo(NEUTRAL + self.offset)
        self.serial.close()

if __name__ == "__main__":
    try:
        mcuControl = MCUCOM("/dev/ttyACM0")
        mcuControl.run(duration=60)  
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        mcuControl.close()
        print("Test completed")
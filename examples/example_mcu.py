import serial
import json
import time

class MCUControl:
    def __init__(self, port="/dev/ttyACM0", baudrate=230400):
        self.serial = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  
        self.NEUTRAL = 1500
        self.OFFSET = 100
        self.OPEN_USEC = self.NEUTRAL - self.OFFSET
        self.CLOSE_USEC = self.NEUTRAL + self.OFFSET
        self.TIMEOUT = 4
        self.STEP_SIZE = 25
        self.current_position = self.NEUTRAL
        self.mode = "idle"
        self.cover = "unknown"
        self.motor_begin = 0
        self.offset = 0

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

    def get_sensor_data(self):
        return self.command("getInputs")

    def set_servo(self, usec):
        usec = max(self.OPEN_USEC, min(self.CLOSE_USEC, usec))
        self.current_position = usec
        return self.command("setServo", {"usec": usec})

    def move_servo_step(self, direction):
        if direction == "open":
            new_position = max(self.OPEN_USEC, self.current_position - self.STEP_SIZE)
        elif direction == "close":
            new_position = min(self.CLOSE_USEC, self.current_position + self.STEP_SIZE)
        else:
            return  

        if new_position != self.current_position:
            self.set_servo(new_position)
            print(f"Moved to position: {new_position}")
        else:
            print(f"Already at limit: {new_position}")

    def run_test(self, duration=60, interval=0.1):
        print("Press Ctrl+C to stop the test")
        end_time = time.time() + duration

        # Initial servo position
        self.set_servo(self.NEUTRAL + self.offset)

        while time.time() < end_time:
            sensor_data = self.get_sensor_data()
            if sensor_data and 'result' in sensor_data:
                result = sensor_data['result']
                buttons = result['buttons']

                # DOWN button (step open)
                if buttons[2]:  
                    self.move_servo_step("open")

                # UP button (step close)
                elif buttons[3]:  
                    self.move_servo_step("close")
                
                # RIGHT button (full open)
                elif buttons[1]:  
                    if self.cover != "open":
                        print("=================Debug===================")
                        print(f"open usec {self.OPEN_USEC}")
                        print(f"offset {self.offset}")
                        print(f"vs {self.OPEN_USEC - self.offset}")
                        print("=========================================")
                        self.set_servo(self.OPEN_USEC + self.offset)
                        self.mode = "cover-open"
                        self.motor_begin = time.time()
                
                # LEFT button (full close)
                elif buttons[0]:  
                    if self.cover != "close":
                        print("=================Debug===================")
                        print(f"close usec {self.CLOSE_USEC}")
                        print(f"offset {self.offset}")
                        print(f"vs {self.CLOSE_USEC + self.offset}")
                        print("=========================================")
                        self.set_servo(self.CLOSE_USEC + self.offset)
                        self.mode = "cover-close"
                        self.motor_begin = time.time()
                
                else:
                    if self.mode == "idle":
                        self.set_servo(self.NEUTRAL + self.offset)

                if self.mode == "cover-open":
                    if time.time() - self.motor_begin > self.TIMEOUT:
                        self.mode = "idle"
                        self.cover = "open"
                        print("Cover opened")
                elif self.mode == "cover-close":
                    if time.time() - self.motor_begin > self.TIMEOUT:
                        self.mode = "idle"
                        self.cover = "close"
                        print("Cover closed")
                
                if self.current_position <= self.OPEN_USEC + self.offset:
                    self.cover = "open"
                elif self.current_position >= self.CLOSE_USEC + self.offset:
                    self.cover = "close"
                else:
                    self.cover = "partially open"

            else:
                print("Failed to retrieve sensor data")
            
            time.sleep(interval)

    def close(self):
        self.set_servo(self.NEUTRAL)
        time.sleep(0.5)  
        self.serial.close()
        print("Servo stopped and connection closed.")

if __name__ == "__main__":
    try:
        test = MCUControl("/dev/ttyACM0")
        test.run_test(duration=60, interval=0.1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'test' in locals():
            test.close()
        print("Test completed")
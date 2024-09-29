import serial
import json
import time

class MCUSensorTest:
    def __init__(self, port="/dev/ttyACM0", baudrate=230400):
        self.serial = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  

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

    def run_test(self, duration=60, interval=1):
        print(f"Running sensor test for {duration} seconds, polling every {interval} second(s)")
        end_time = time.time() + duration

        while time.time() < end_time:
            sensor_data = self.get_sensor_data()
            if sensor_data and 'result' in sensor_data:
                result = sensor_data['result']
                print("\n--- Sensor Data ---")
                print(f"Buttons: {result['buttons']}")
                print(f"Thermal: {result['thermal']:.2f}°C")
                print(f"IR Detect: {result['ir_detect']}")
                print(f"Luminosity: {result['luminosity']:.2f} lux")
                
                print("LED toggled")
            else:
                print("Failed to retrieve sensor data")
            
            time.sleep(interval)

    def close(self):
        self.serial.close()

if __name__ == "__main__":
    try:
        test = MCUSensorTest("/dev/ttyACM0")
        test.run_test(duration=60, interval=1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        test.close()
        print("Test completed")
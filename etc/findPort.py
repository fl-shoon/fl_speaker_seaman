from subprocess import run
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_main():
    import serial.tools.list_ports # type: ignore
    ports = [tuple(p) for p in list(serial.tools.list_ports.comports())]
    logger.info(ports)
    result = extract_device(ports)
    if result:
        logger.info(f"port found : {result}")
    else:
        logger.info("port not found")
    return result

def extract_device(tuple_list):
    for device, description, _ in tuple_list:
        if description == 'RP2040 LCD 1.28 - Board CDC' or 'RP2040' in description or 'LCD' in description:
            return device
    return None  # Return None if no matching device is found

def find_port():
    result = '/dev/ttyACM0'
    try:
        import serial.tools.list_ports # type: ignore
    except ModuleNotFoundError:
        run(f"sudo python -m pip install pyserial --break-system-packages", shell=True)
    finally:
        if run_main(): result = run_main()
    return result
from enum import Enum, auto

import logging
import os
import pyaudio
import serial.tools.list_ports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API variables
SPEAKER_ID = os.environ["SPEAKER_ID"]
SERVER_URL = os.environ["SERVER_URL"]

# Get the current directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Get the parent directory
PARENT_DIR = os.path.dirname(CURRENT_DIR)

# Define the assets directory
ASSETS_DIR = os.path.join(PARENT_DIR, 'assets')

# Define subdirectories for different types of assets
AUDIO_DIR = os.path.join(ASSETS_DIR, 'audio')
IMAGE_DIR = os.path.join(ASSETS_DIR, 'images')
GIF_DIR = os.path.join(ASSETS_DIR, 'gifs')
VOICE_TRIGGER_DIR = os.path.join(ASSETS_DIR, 'trigger')

# Define the temporary ai output audio file
TEMP_AUDIO_FILE = os.path.join(AUDIO_DIR, 'output.wav')

# Define the firebase credentials directory
FIRE_CRED_DIR = os.path.join(PARENT_DIR, 'secrets')

# Define the firebase credentials file
FIRE_CRED = os.path.join(FIRE_CRED_DIR, 'firebase_admin.json')

# Function to get all files with a specific extension in a directory
def get_files_with_extension(directory, extension):
    return [f for f in os.listdir(directory) if f.endswith(extension)]

# Function to create an empty WAV file
def create_empty_wav_file(file_path):
    import wave
    with wave.open(file_path, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 2 bytes per sample
        wav_file.setframerate(44100)  # 44.1kHz sampling rate
        wav_file.writeframes(b'')  # Empty audio data

# Check if temporary audio file exists, create it if it doesn't
if not os.path.exists(TEMP_AUDIO_FILE):
    create_empty_wav_file(TEMP_AUDIO_FILE)

# Get lists of files
AUDIO_FILES = [os.path.basename(TEMP_AUDIO_FILE)] + [f for f in get_files_with_extension(AUDIO_DIR, '.wav') if f != os.path.basename(TEMP_AUDIO_FILE)]
IMAGE_FILES = get_files_with_extension(IMAGE_DIR, '.png') + get_files_with_extension(IMAGE_DIR, '.jpg')
GIF_FILES = get_files_with_extension(GIF_DIR, '.gif')

# Create dictionaries mapping filenames to full paths
AUDIO_PATHS = {file: os.path.join(AUDIO_DIR, file) for file in AUDIO_FILES}
IMAGE_PATHS = {file: os.path.join(IMAGE_DIR, file) for file in IMAGE_FILES}
GIF_PATHS = {file: os.path.join(GIF_DIR, file) for file in GIF_FILES}

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000 # Higher rates require more CPU power to process in real-time
RECORD_SECONDS = 8

# File Locations
# =========================
# conversation 
ResponseAudio = os.path.join(AUDIO_DIR, "response_audio.wav") 
TriggerAudio = os.path.join(AUDIO_DIR, "startUp.wav")
ErrorAudio = os.path.join(AUDIO_DIR, "errorSpeech.wav")
AIOutputAudio = TEMP_AUDIO_FILE

# display
SpeakingGif = os.path.join(GIF_DIR, "speakingGif.gif")
SeamanLogo = os.path.join(IMAGE_DIR, "logo.png")
SatoruHappy = os.path.join(IMAGE_DIR, "happy.png")

# voice trigger 
PicoLangModel = os.path.join(VOICE_TRIGGER_DIR,"pico_voice_language_model_ja.pv")
PicoWakeWordSatoru = os.path.join(VOICE_TRIGGER_DIR,"pico_voice_wake_word_satoru.ppn") 
ToshibaVoiceDictionary = os.path.join(VOICE_TRIGGER_DIR,"toshiba_voice_dict_jaJP.vtdic")
ToshibaVoiceLibrary = os.path.join(VOICE_TRIGGER_DIR,"libVT_ARML64h.so")

# Serial/Display Settings
BautRate = '230400'

# finding lcd display's device name
def extract_device():
    rp2040_port = None
    pico_arduino_port = None
    
    ports = list(serial.tools.list_ports.comports())
    logger.info(f"Available ports: {ports}")
    
    for port, desc, hwid in ports:
        if "RP2040 LCD 1.28" in desc:
            rp2040_port = port
        elif "PicoArduino" in desc:
            pico_arduino_port = port
    
    if rp2040_port is None:
        logger.warning("RP2040 LCD 1.28 port not found. Defaulting to /dev/ttyACM1")
        rp2040_port = '/dev/ttyACM1'
    
    if pico_arduino_port is None:
        logger.warning("PicoArduino port not found. Defaulting to /dev/ttyACM0")
        pico_arduino_port = '/dev/ttyACM0'
    
    logger.info(f"Selected RP2040 LCD port: {rp2040_port}")
    logger.info(f"Selected PicoArduino port: {pico_arduino_port}")
    
    return rp2040_port, pico_arduino_port 

USBPort, MCUPort = extract_device()

class WakeWorkType(str, Enum):
    TRIGGER = auto()
    SCHEDULE = auto()

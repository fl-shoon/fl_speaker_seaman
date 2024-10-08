from apiService.service_get import GetData
from apiService.service_put import PutData
from audio.player import AudioPlayer
from audio.recorder import InteractiveRecorder
from collections import deque
from display.display import DisplayModule
from display.setting import SettingMenu
from etc.define import *
from openAI.conversation import OpenAIClient
from pvrecorder import PvRecorder
from pico.pico import PicoVoiceTrigger
from threading import Event
from transmission.serialModule import SerialModule

import argparse
import asyncio
import datetime
import numpy as np
import schedule
import signal
import time
import wave

exit_event = Event()

class VoiceAssistant:
    def __init__(self, args):
        self.args = args
        self.serial_module = None
        self.display = None
        self.recorder = None
        self.porcupine = None
        self.ai_client = None
        self.interactive_recorder = InteractiveRecorder()
        self.calibration_buffer = deque(maxlen=100)  
        self.energy_levels = deque(maxlen=100)
        self.volume = 0.5
        self.speaker_id = os.environ["SPEAKER_ID"]
        self.server_url = os.environ["SERVER_URL"]
        self.auth_token = None
        self.schedule = {}
        self.schedule_seconds = 30
        self.http_get = GetData(self.speaker_id, self.server_url)
        self.http_put = PutData(self.speaker_id, self.server_url)
        self.sensor_data = {}
        self.initialize(self.args.aiclient)

    def initialize(self, aiclient):
        try:
            self.serial_module = SerialModule(BautRate)
            self.display = DisplayModule(self.serial_module)
            self.audioPlayer = AudioPlayer(self.display)
            self.setting_menu = SettingMenu(self.serial_module, self.audioPlayer)
            
            if not self.serial_module.open(USBPort):
                # FIXME: Send a failure notice post request to server later
                raise ConnectionError(f"Failed to open serial port {USBPort}")

            self.ai_client = aiclient
            self.auth_token = self.http_get.token

            schedule.every(self.schedule_seconds).seconds.do(self.get_schedule)
            schedule.every(50).seconds.do(self.update_sensor_data)

            self.porcupine = PicoVoiceTrigger(self.args)
            self.recorder = PvRecorder(frame_length=self.porcupine.frame_length)
            
            logger.info("Voice Assistant initialized successfully")
        except Exception as e:
            # FIXME: Send a failure notice post request to server later
            logger.error(f"Initialization error: {e}")
            self.cleanup()
            raise

    def get_schedule(self):
        if self.auth_token: self.schedule = self.http_get.fetch_schedule()

    def update_sensor_data(self):
        if self.auth_token: self.http_put.update_sensor_data(self.auth_token, self.sensor_data)

    def check_buttons(self):
        try:
            inputs = self.serial_module.get_inputs()
            if inputs and 'result' in inputs:
                result = inputs['result']
                buttons = result.get('buttons', [])

                self.sensor_data = {
                    'temperatureSensor': f"{result['thermal']:.2f}",
                    'irSensor': result['ir_detect'],
                    'brightnessSensor': f"{result['luminosity']:.2f}"
                }

                '''
                Thermal: 30.24°C
                IR Detect: True
                Luminosity: 20.00 lux
                '''

                if len(buttons) > 1 and buttons[1]:  # RIGHT button
                    response = self.setting_menu.display_menu()
                    if response:
                        new_response = response
                        return new_response
                    time.sleep(0.2)
            return None
        except Exception as e:
            logger.error(f"Error in check_buttons: {e}")
            return None
        
    def listen_for_wake_word(self):
        self.recorder.start()
        self.calibration_buffer.clear()
        self.energy_levels.clear()
        calibration_interval = 50  # 50 -> frames
        frames_since_last_calibration = 0
        last_button_check_time = time.time()
        button_check_interval = 1.5 # 1 -> check buttons every 1 seconds
        hour = None 
        minute = None
        detections = -1
        
        try:
            while not exit_event.is_set():
                schedule.run_pending()
                audio_frame = self.recorder.read()
                audio_data = np.array(audio_frame, dtype=np.int16)

                self.update_calibration(audio_data)
                frames_since_last_calibration += 1

                if frames_since_last_calibration >= calibration_interval:
                    self.perform_calibration()
                    frames_since_last_calibration = 0

                detections = self.porcupine.process(audio_frame)
                wake_word_triggered = detections >= 0
                
                if wake_word_triggered:
                    logger.info("Wake word detected")
                    self.audioPlayer.play_audio(ResponseAudio)
                    return True, WakeWorkType.TRIGGER
                
                now = datetime.datetime.now()

                if self.schedule: 
                    hour = self.schedule['hour']
                    minute = self.schedule['minute']

                if hour and minute: 
                    scheduled_datetime = datetime.datetime.strptime(
                        f"{hour}:{minute}:{00}", 
                        "%H:%M:%S"
                    ).replace(year=now.year, month=now.month, day=now.day)
                    time_diff = abs((now - scheduled_datetime).total_seconds())
                    if time_diff <= self.schedule_seconds:
                        return True, WakeWorkType.SCHEDULE
                    
                current_time = time.time() # timestamp
                if current_time - last_button_check_time >= button_check_interval:
                    res = self.check_buttons()
                    
                    if res == 'exit':
                        self.audioPlayer.play_trigger_with_logo(TriggerAudio, SeamanLogo)
                    if res == 'clean':
                        self.cleanup()
                    
                    last_button_check_time = current_time

        except Exception as e:
            logger.error(f"Error in wake word detection: {e}")
        finally:
            self.recorder.stop()
        return False

    async def process_conversation(self):
        conversation_active = True
        silence_count = 0
        max_silence = 2

        while conversation_active and not exit_event.is_set():
            if not self.serial_port_check():
                break

            self.display.start_listening_display(SatoruHappy)
            audio_data = self.interactive_recorder.record_question(silence_duration=2, max_duration=30, audio_player=self.audioPlayer)

            if not audio_data:
                silence_count += 1
                if silence_count >= max_silence:
                    logger.info("Maximum silence reached. Ending conversation.")
                    conversation_active = False
                continue
            else:
                silence_count = 0

            input_audio_file = AIOutputAudio
            with wave.open(input_audio_file, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(RATE)
                wf.writeframes(audio_data)

            self.display.stop_listening_display()

            try:
                conversation_ended = await self.ai_client.process_audio(input_audio_file)
                if conversation_ended:
                    conversation_active = False
            except Exception as e:
                logger.error(f"Error processing conversation: {e}")
                self.audioPlayer.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                conversation_active = False

        self.display.fade_in_logo(SeamanLogo)

    async def scheduled_conversation(self):
        conversation_active = True
        silence_count = 0
        max_silence = 2
        text_initiation ="こんにちは"
        input_audio_file = None

        while conversation_active and not exit_event.is_set():
            if not self.serial_port_check():
                break

            if input_audio_file:
                self.display.start_listening_display(SatoruHappy)
                audio_data = self.interactive_recorder.record_question(silence_duration=2, max_duration=30, audio_player=self.audioPlayer)

                if not audio_data:
                    silence_count += 1
                    if silence_count >= max_silence:
                        logger.info("Maximum silence reached. Ending conversation.")
                        conversation_active = False
                    continue
                else:
                    silence_count = 0

                with wave.open(input_audio_file, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(2)
                    wf.setframerate(RATE)
                    wf.writeframes(audio_data)

                self.display.stop_listening_display()

            try:
                if input_audio_file:
                    conversation_ended = await self.ai_client.process_audio(input_audio_file)
                else:
                    conversation_ended, audio_file = await self.ai_client.process_text(text_initiation)
                    input_audio_file = audio_file
                    
                if conversation_ended:
                    conversation_active = False
            except Exception as e:
                logger.error(f"Error processing conversation: {e}")
                self.audioPlayer.sync_audio_and_gif(ErrorAudio, SpeakingGif)
                conversation_active = False

        self.display.fade_in_logo(SeamanLogo)

    def update_calibration(self, audio_data):
        chunk = audio_data[:self.interactive_recorder.CHUNK_SIZE]
        filtered_audio = self.interactive_recorder.butter_lowpass_filter(chunk, cutoff=1000, fs=RATE)
        energy = np.sum(filtered_audio**2) / len(filtered_audio)
        self.energy_levels.append(energy)

    def perform_calibration(self):
        if len(self.energy_levels) > 0:
            self.interactive_recorder.silence_energy = np.mean(self.energy_levels)
            self.interactive_recorder.energy_threshold = self.interactive_recorder.silence_energy * 3
            # logger.info(f"Calibration updated. Silence energy: {self.interactive_recorder.silence_energy}, Threshold: {self.interactive_recorder.energy_threshold}")
        else:
            logger.warning("No energy data available for calibration")

    def serial_port_check(self):
        if not self.serial_module.isPortOpen:
            logger.info("Serial connection closed. Attempting to reopen...")
            for attempt in range(3):
                if self.serial_module.open(USBPort):
                    logger.info("Successfully reopened serial connection.")
                    return True
                logger.info(f"Attempt {attempt + 1} failed. Retrying in 1 second...")
                time.sleep(1)
            logger.error("Failed to reopen serial connection after 3 attempts.")
            # FIXME: Send a failure notice post request to server later
            return False
        return True
    
    def cleanup(self):
        logger.info("Starting cleanup process...")
        if self.recorder:
            self.recorder.stop()
            self.recorder.delete()
        if self.display and self.serial_module and self.serial_module.isPortOpen:
            self.display.send_white_frames()
        if self.serial_module:
            self.serial_module.close()
        logger.info("Cleanup process completed.")

def signal_handler(signum, frame):
    # Handle the signals when either signal is received
    logger.info(f"Received {signum} signal. Initiating graceful shutdown...")
    exit_event.set()

async def main():
    aiClient = OpenAIClient()
    await aiClient.initialize()

    parser = argparse.ArgumentParser()
    # Pico
    parser.add_argument('--access_key', help='AccessKey for Porcupine', default=os.environ["PICO_ACCESS_KEY"])
    parser.add_argument('--keyword_paths', nargs='+', help="Paths to keyword model files", default=[PicoWakeWordSatoru])
    parser.add_argument('--model_path', help='Path to Porcupine model file', default=PicoLangModel)
    parser.add_argument('--sensitivities', nargs='+', help="Sensitivities for keywords", type=float, default=[0.5])

    # OpenAi
    parser.add_argument('--aiclient', help='Asynchronous openAi client', default=aiClient)

    args = parser.parse_args()

    assistant = VoiceAssistant(args)
    aiClient.setAudioPlayer(assistant.audioPlayer)

    try:
        assistant.audioPlayer.play_trigger_with_logo(TriggerAudio, SeamanLogo)

        while not exit_event.is_set():
            res, trigger_type = assistant.listen_for_wake_word()
            if res and trigger_type == WakeWorkType.TRIGGER:
                await assistant.process_conversation()
            if res and trigger_type == WakeWorkType.SCHEDULE:
                await assistant.scheduled_conversation()

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Shutting down...")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        await assistant.ai_client.close()
        assistant.cleanup()
        
if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    asyncio.run(main())
import subprocess
import sys
import os
import venv
import argparse
import urllib.request
import json

class RaspberryPiSetup:
    def __init__(self, venv_path=".venv"):
        self.venv_path = venv_path
        self.python_path = os.path.join(self.venv_path, "bin", "python")
        self.pip_path = os.path.join(self.venv_path, "bin", "pip")
        self.audio_processing_model_url = "https://models.silero.ai/vad_models/silero_vad.jit"
        self.audio_processing_model_path = 'silero_vad.jit'

    def run_command(self, command):
        try:
            subprocess.run(command, check=True, shell=True)
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {command}")
            print(f"Error message: {e}")
            return False
        return True

    def create_virtual_environment(self):
        print(f"Creating virtual environment at {self.venv_path}...")
        try:
            venv.create(self.venv_path, with_pip=True)
        except Exception as e:
            print(f"Error creating virtual environment: {e}")
            print("Attempting to create virtual environment using system command...")
            self.run_command(f"python3 -m venv {self.venv_path}")

    def install_package(self, package_name):
        print(f"Installing {package_name}...")
        return self.run_command(f"{self.pip_path} install {package_name}")

    def update_system(self):
        print("Updating system...")
        self.run_command("sudo apt-get update")
        self.run_command("sudo apt-get upgrade -y")

    def install_system_dependencies(self):
        print("Installing system dependencies...")
        dependencies = ["python3-dev", "python3-pip", "portaudio19-dev", "libatlas-base-dev", "fonts-ipafont"]
        for dep in dependencies:
            if not self.run_command(f"sudo apt-get install -y {dep}"):
                print(f"Failed to install system dependency: {dep}")
                return False
        return True

    def install_python_packages(self):
        print("Installing Python packages...")
        packages = [
            "pyserial",
            "pygame",
            "pvrecorder",
            "openai",
            "PyAudio",
            "webrtcvad",
            "rx",
            "Pillow",
            "numpy",
            "torch",
            "torchaudio"
        ]
        for package in packages:
            if not self.install_package(package):
                print(f"Failed to install Python package: {package}")
                return False
        return True

    def setup(self, update_system=False):
        if update_system:
            self.update_system()
        if not self.install_system_dependencies():
            print("Failed to install system dependencies. Exiting.")
            return False
        self.create_virtual_environment()
        if not self.install_python_packages():
            print("Failed to install Python packages. Exiting.")
            return False
        if not self.download_silero_vad_model():
            print("Failed to download Silero VAD model. Exiting.")
            return False
        print("Setup completed successfully!")
        print(f"To activate the virtual environment, run: source {os.path.join(self.venv_path, 'bin', 'activate')}")
        return True
    
    def download_silero_vad_model(self):
        print("Downloading Silero VAD model...")
        script = f"""
import torch

model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                              model='silero_vad',
                              force_reload=True,
                              onnx=False)

torch.jit.save(model, '{self.model_path}')
print(f"Model downloaded and saved to {self.model_path}")
"""
        with open("download_model.py", "w") as f:
            f.write(script)

        result = self.run_command(f"{self.python_path} download_model.py")
        os.remove("download_model.py")
        return result

def main():
    parser = argparse.ArgumentParser(description="Raspberry Pi Setup Script")
    parser.add_argument("--update-system", action="store_true", help="Update system before installation")
    args = parser.parse_args()

    setup = RaspberryPiSetup()
    if not setup.setup(update_system=args.update_system):
        sys.exit(1)

if __name__ == "__main__":
    main()
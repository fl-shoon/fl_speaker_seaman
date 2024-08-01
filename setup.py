import subprocess
import sys
import os
import venv

class RaspberryPiSetup:
    def __init__(self, venv_path=".venv"):
        self.venv_path = venv_path
        self.python_path = os.path.join(self.venv_path, "bin", "python")
        self.pip_path = os.path.join(self.venv_path, "bin", "pip")

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
        venv.create(self.venv_path, with_pip=True)

    def install_package(self, package_name):
        print(f"Installing {package_name}...")
        return self.run_command(f"{self.pip_path} install {package_name}")

    def update_system(self):
        print("Updating system...")
        self.run_command("sudo apt-get update")
        self.run_command("sudo apt-get upgrade -y")

    def install_system_dependencies(self):
        print("Installing system dependencies...")
        dependencies = ["python3-dev", "python3-pip", "portaudio19-dev", "libatlas-base-dev"]
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
            "rx",
            "Pillow",
            "numpy"
        ]
        for package in packages:
            if not self.install_package(package):
                print(f"Failed to install Python package: {package}")
                return False
        return True

    def setup(self):
        self.update_system()
        if not self.install_system_dependencies():
            print("Failed to install system dependencies. Exiting.")
            return False
        self.create_virtual_environment()
        if not self.install_python_packages():
            print("Failed to install Python packages. Exiting.")
            return False
        print("Setup completed successfully!")
        print(f"To activate the virtual environment, run: source {os.path.join(self.venv_path, 'bin', 'activate')}")
        return True

if __name__ == "__main__":
    setup = RaspberryPiSetup()
    if not setup.setup():
        sys.exit(1)
import subprocess
import sys
import os
import venv

class RaspberryPiSetup:
    def __init__(self, venv_path=".venv"):
        self.venv_path = venv_path
        self.python_path = os.path.join(self.venv_path, "bin", "python")
        self.pip_path = os.path.join(self.venv_path, "bin", "pip")
        self.version = None

    def run_command(self, command):
        try:
            subprocess.run(command, check=True, shell=True)
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {command}")
            print(f"Error message: {e}")
            sys.exit(1)

    def create_virtual_environment(self):
        print(f"Creating virtual environment at {self.venv_path}...")
        venv.create(self.venv_path, with_pip=True)

    def install_package(self, package_name):
        self.run_command(f"{self.pip_path} install {package_name}")

    def install_packaging(self):
        self.install_package("packaging")
        
        sys.path.insert(0, os.path.join(self.venv_path, "lib", "python3.9", "site-packages"))
        from packaging import version # type: ignore
        self.version = version

    def update_system(self):
        print("Updating system...")
        self.run_command("sudo apt-get update")
        self.run_command("sudo apt-get upgrade -y")

    def install_system_dependencies(self):
        print("Installing system dependencies...")
        dependencies = ["python3-dev", "python3-pip", "portaudio19-dev", "libatlas-base-dev"]
        for dep in dependencies:
            self.run_command(f"sudo apt-get install -y {dep}")

    def get_latest_version(self, package_name):
        try:
            output = subprocess.check_output([self.pip_path, 'install', f'{package_name}==', '--use-deprecated=legacy-resolver'], stderr=subprocess.STDOUT)
            output = output.decode('utf-8')
            lines = output.split('\n')
            for line in lines:
                if "from versions:" in line:
                    versions = line.split('from versions:')[1].strip().split(', ')
                    return versions[-1]  # Return the last (latest) version
        except subprocess.CalledProcessError:
            return None

    def version_major_change(self, v1, v2):
        v1 = self.version.parse(v1)
        v2 = self.version.parse(v2)
        return v1.major != v2.major

    def install_python_packages(self):
        print("Installing Python packages...")
        packages = [
            "pyserial",
            "pygame",
            "pvrecorder",
            "openai",
            "PyAudio",
            "rx",
            "pillow",
            "numpy"
        ]
        for package in packages:
            self.install_package(package)

    def setup(self):
        self.update_system()
        self.install_system_dependencies()
        self.create_virtual_environment()
        self.install_packaging()
        self.install_python_packages()
        print("Setup completed successfully!")
        os.path.join(self.venv_path, 'bin', 'activate')
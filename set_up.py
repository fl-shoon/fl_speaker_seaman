import subprocess
import sys
import pkg_resources

class RaspberryPiSetup:
    def __init__(self):
        self.version = None

    def run_command(self, command):
        try:
            subprocess.run(command, check=True, shell=True)
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {command}")
            print(f"Error message: {e}")
            sys.exit(1)

    def package_installed(self, package_name):
        try:
            return pkg_resources.get_distribution(package_name)
        except pkg_resources.DistributionNotFound:
            return None

    def install_packaging(self):
        if not self.package_installed("packaging"):
            print("Installing packaging library...")
            self.run_command(f"{sys.executable} -m pip install packaging")
        
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
            output = subprocess.check_output([sys.executable, '-m', 'pip', 'install', f'{package_name}==', '--use-deprecated=legacy-resolver'], stderr=subprocess.STDOUT)
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
        print("Checking Python packages...")
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
            installed_package = self.package_installed(package)
            if installed_package:
                installed_version = installed_package.version
                latest_version = self.get_latest_version(package)
                if latest_version and self.version_major_change(installed_version, latest_version):
                    print(f"Major version change detected for {package}:")
                    print(f"Installed version: {installed_version}")
                    print(f"Latest version: {latest_version}")
                    update = input(f"Do you want to update {package}? (y/n): ").lower().strip() == 'y'
                    if update:
                        print(f"Updating {package}...")
                        self.run_command(f"{sys.executable} -m pip install --no-cache-dir --upgrade {package}")
                    else:
                        print(f"Skipping update for {package}")
                else:
                    print(f"{package} is up to date.")
            else:
                print(f"Installing {package}...")
                self.run_command(f"{sys.executable} -m pip install --no-cache-dir {package}")

    def install_pyaudio(self):
        if not self.package_installed("PyAudio"):
            print("Installing PyAudio...")
            self.run_command("sudo apt-get install -y python3-pyaudio")

    def setup(self):
        self.update_system()
        self.install_system_dependencies()
        self.install_packaging()
        self.install_pyaudio()
        self.install_python_packages()
        print("Setup completed successfully!")
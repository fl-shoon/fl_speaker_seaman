import subprocess
import sys
import os
import venv
import argparse

class RaspberryPiSetup:
    def __init__(self, venv_path=".venv"):
        self.venv_path = venv_path
        self.python_path = os.path.join(self.venv_path, "bin", "python")
        self.pip_path = os.path.join(self.venv_path, "bin", "pip")
        self.system_packages = [
            "python3-dev",
            "python3-pip",
            "portaudio19-dev",
            "libatlas-base-dev",
            "fonts-ipafont"
        ]

    def run_command(self, command):
        try:
            subprocess.run(command, check=True, shell=True)
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {command}")
            print(f"Error message: {e}")
            return False
        return True

    def update_system(self):
        print("Updating package lists...")
        if not self.run_command("sudo apt-get update"):
            print("Failed to update package lists.")
            return False

        print("Checking for updates to required packages...")
        packages_to_upgrade = " ".join(self.system_packages)
        if not self.run_command(f"sudo apt-get install --only-upgrade -y {packages_to_upgrade}"):
            print("Failed to upgrade required packages.")
            return False

        return True

    # ... [other methods remain unchanged] ...

    def setup(self, update_system=False):
        if update_system:
            if not self.update_system():
                print("System update failed. Continuing with setup...")
        if not self.install_system_dependencies():
            print("Failed to install system dependencies. Exiting.")
            return False
        if not self.create_or_update_virtual_environment():
            print("Failed to create or update virtual environment. Exiting.")
            return False
        self.activate_virtual_environment()
        if not self.install_python_packages():
            print("Failed to install Python packages. Exiting.")
            return False
        # ... [rest of setup method remains unchanged] ...

def main():
    parser = argparse.ArgumentParser(description="Raspberry Pi Setup Script")
    parser.add_argument("--update-system", action="store_true", help="Update system packages related to this project")
    args = parser.parse_args()

    setup = RaspberryPiSetup()
    if not setup.setup(update_system=args.update_system):
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/bin/bash

# Redirect output to a log file
exec > >(tee -a "/tmp/seaman_ai_speaker.log") 2>&1

echo "Starting runApp.sh at $(date)"
echo "Current user: $(whoami)"
echo "Current directory: $(pwd)"
echo "Environment variables:"
env

# Start PulseAudio if it's not running
if ! pulseaudio --check; then
    echo "Starting PulseAudio..."
    pulseaudio --start --exit-idle-time=-1 &
    sleep 2
else
    echo "PulseAudio is already running."
fi

# Function to clean up before exiting
cleanup() {
    echo "Cleaning up..."
    if [ ! -z "$PYTHON_PID" ]; then
        echo "Sending termination signal to Python script..."
        kill -TERM "$PYTHON_PID"

        # Wait for the Python script to finish its cleanup
        echo "Waiting for Python script to finish cleanup..."
        wait "$PYTHON_PID"
        echo "Python script has finished."
    fi
    exit 0
}

# Set up trap to catch Ctrl+C and other termination signals
trap cleanup SIGINT SIGTERM

# Run setup
echo "Running setup..."
python3 setup.py
if [ $? -ne 0 ]; then
    echo "Setup failed. Please check the error messages above."
    exit 1
fi

# Export environment variables
export OPENAI_API_KEY='key'
# Add more environment variables:
# export PICCO_ACCESS_KEY='another_key'
# export CONFIG_PATH='/path/to/config'

# Function to run the main program
run_main_program() {
    echo "Starting AI Speaker System..."
    python3 debug.py &
    PYTHON_PID=$!
    wait $PYTHON_PID
    exit_code=$?

    if [ $exit_code -eq 1 ]; then
        echo "Error occurred. Checking if it's due to a missing module..."
        if grep -q "ModuleNotFoundError" error.log; then
            echo "Module not found. Running setup again..."
            python3 setup.py
            run_main_program
        else
            echo "AI Speaker System exited with code $exit_code."
        fi
    elif [ $exit_code -eq 130 ] || [ $exit_code -eq 143 ]; then
        echo "AI Speaker System was interrupted. Shutting down..."
    fi
}

# Run the main program
run_main_program

# This point will be reached if the main program exits normally or is interrupted
echo "AI Speaker System has shut down."

# Clean up
cleanup
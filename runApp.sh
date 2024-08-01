#!/bin/bash

# Function to run setup
run_setup() {
    echo "Running setup..."
    sudo python3 setup.py
}

# Function to clean up before exiting
cleanup() {
    echo "Cleaning up..."
    deactivate
    exit 0
}

# Set up trap to catch Ctrl+C and other termination signals
trap cleanup SIGINT SIGTERM

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    run_setup
else
    echo "Virtual environment found. Checking for updates..."
    read -p "Do you want to run setup again? (y/n) " choice
    case "$choice" in 
        y|Y ) run_setup;;
        * ) echo "Skipping setup.";;
    esac
fi

# Activate virtual environment
source .venv/bin/activate

# Function to run the main program
run_main_program() {
    echo "Starting AI Speaker System..."
    python3 app.py
    exit_code=$?

    if [ $exit_code -ne 0 ] && [ $exit_code -ne 130 ]; then
        echo "AI Speaker System exited with code $exit_code. Restarting in 5 seconds..."
        sleep 5
        run_main_program
    elif [ $exit_code -eq 130 ]; then
        echo "AI Speaker System was interrupted by Ctrl+C. Shutting down..."
    fi
}

# Run the main program
run_main_program

# When main program exits normally or is interrupted
echo "AI Speaker System has shut down."

# Clean up
cleanup
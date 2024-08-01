#!/bin/bash

# Function to run setup
run_setup() {
    echo "Running setup..."
    python3 setup.py
    if [ $? -ne 0 ]; then
        echo "Setup failed. Please check the error messages above."
        exit 1
    fi
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
    python3 test.py
    exit_code=$?

    if [ $exit_code -eq 1 ]; then
        echo "Error occurred. Checking if it's due to a missing module..."
        if grep -q "ModuleNotFoundError" error.log; then
            echo "Module not found. Would you like to run setup again? (y/n)"
            read choice
            case "$choice" in 
                y|Y ) 
                    run_setup
                    run_main_program
                    ;;
                * ) 
                    echo "Exiting due to module not found error."
                    exit 1
                    ;;
            esac
        elif [ $exit_code -ne 130 ]; then
            echo "AI Speaker System exited with code $exit_code. Restarting in 5 seconds..."
            sleep 5
            run_main_program
        fi
    elif [ $exit_code -eq 130 ]; then
        echo "AI Speaker System was interrupted by Ctrl+C. Shutting down..."
    fi
}

# Run the main program
run_main_program

# This point will be reached if the main program exits normally or is interrupted
echo "AI Speaker System has shut down."

# Clean up
cleanup
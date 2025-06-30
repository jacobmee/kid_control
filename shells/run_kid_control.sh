#!/bin/bash

# Get the absolute path of the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Create the virtual environment in the script directory
python3 -m venv "$SCRIPT_DIR/venv"

# Activate it
source "$SCRIPT_DIR/venv/bin/activate"

# Install requirements
#pip install -r "$SCRIPT_DIR/requirements.txt"

# Set the working directory to the script's location
cd "$SCRIPT_DIR"

# Run the time control script
python3 "$SCRIPT_DIR/time_control.py"

# Deactivate when done
deactivate
#!/bin/bash
# Script to run the photobooth system after setting up Hailo environment

# Function to check if we're in the Hailo environment
check_hailo_env() {
    # Check if TAPPAS_POST_PROC_DIR is set (should be set by setup_env.sh)
    if [ -z "$TAPPAS_POST_PROC_DIR" ]; then
        return 1
    fi
    
    # Try running a hailo command to see if environment is correctly set up
    if ! command -v hailortcli &> /dev/null; then
        return 1
    fi
    
    return 0
}

# First source the setup environment script
if [ -f "setup_env.sh" ]; then
    echo "Setting up Hailo environment..."
    source ./setup_env.sh
else
    echo "Error: setup_env.sh not found in current directory!"
    echo "Please make sure you have the Hailo setup script in the same directory."
    exit 1
fi

# Check if environment is properly set up
if ! check_hailo_env; then
    echo "Error: Hailo environment not properly set up!"
    echo "Make sure your setup_env.sh script correctly configures the environment."
    exit 1
fi

# Verify required files exist
required_files=(
    "main.py" 
    "idle_screen.py" 
    "user_input_app.py" 
    "detection_app.py" 
    "photo_capture.py"  # Added photo_capture.py
    "photo_preview.py"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "Error: Required file $file not found!"
        exit 1
    fi
done

# Make sure required directories exist
mkdir -p snapshots
mkdir -p cache
mkdir -p data

# Ensure scripts are executable
chmod +x main.py
chmod +x detection_app.py
chmod +x user_input_app.py
chmod +x idle_screen.py
chmod +x photo_capture.py  # Added photo_capture.py
chmod +x photo_preview.py

# Set DISPLAY variable if not already set
if [ -z "$DISPLAY" ]; then
    export DISPLAY=":0"
    echo "Set DISPLAY to :0"
fi

# Run the photobooth system
echo "Starting photobooth system..."
python3 main.py

echo "Photobooth system exited."
#!/usr/bin/env python3
import pygame
import cv2
import numpy as np
import time
import sys
import os
import signal
import json
import argparse
import datetime
import threading
from picamera2 import Picamera2

# Parse arguments
parser = argparse.ArgumentParser(description="Photo capture with countdown")
parser.add_argument("--countdown", type=int, default=5, help="Countdown duration in seconds")
parser.add_argument("--fullscreen", action="store_true", help="Run in fullscreen mode")
parser.add_argument("--json-id", type=str, help="Session ID for JSON file updates")
parser.add_argument("--cache-path", type=str, help="Path to cache image")
args = parser.parse_args()

# Ensure required directories exist
SNAPSHOT_DIR = "snapshots"
DATA_DIR = "data"
CACHE_DIR = "cache"
for directory in [SNAPSHOT_DIR, DATA_DIR, CACHE_DIR]:
    os.makedirs(directory, exist_ok=True)

# Global variables
running = True
camera = None
display_screen = None
preview_taken = False
current_count = args.countdown

# Function to initialize pygame
def init_pygame():
    pygame.init()
    
    if args.fullscreen:
        display_screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        display_screen = pygame.display.set_mode((1280, 720))
    
    pygame.display.set_caption("Photo Capture")
    return display_screen

# Function to clean up resources
def cleanup():
    print("Cleaning up resources...")
    
    # Release camera
    if camera:
        try:
            camera.stop()
            camera.close()
        except:
            pass
    
    # Quit pygame
    pygame.quit()

# Signal handlers
def handle_sigterm(signum, frame):
    global running
    print("Received termination signal")
    running = False

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

# Function to initialize and start camera
def init_camera():
    global camera
    
    try:
        camera = Picamera2()
        
        # Configure camera for desired resolution
        capture_config = camera.create_still_configuration(
            main={"size": (2304, 1296)},  # 16:9 aspect ratio
            lores={"size": (1280, 720)},  # Preview size
            display="lores"
        )
        
        camera.configure(capture_config)
        camera.start()
        print("Camera initialized successfully")
        return True
    except Exception as e:
        print(f"Error initializing camera: {e}")
        return False

# Function to take a cache photo
def take_cache_photo():
    global camera, preview_taken
    
    if not camera:
        print("Camera not initialized")
        return None
    
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        preview_path = os.path.join(SNAPSHOT_DIR, f"preview_{timestamp}.jpg")
        cache_path = os.path.join(CACHE_DIR, f"cache_{timestamp}.jpg")
        
        # Capture a frame
        camera.capture_file(preview_path)
        print(f"Preview saved to {preview_path}")
        
        # Create smaller version for cache
        img = cv2.imread(preview_path)
        if img is not None:
            small_img = cv2.resize(img, (640, 360))  # Half resolution
            cv2.imwrite(cache_path, small_img)
            print(f"Cache image saved to {cache_path}")
            
            # Update JSON with cache path
            if args.json_id:
                update_json_data(cache_img_path=cache_path)
        
        preview_taken = True
        return cache_path
    except Exception as e:
        print(f"Error taking cache photo: {e}")
        return None

# Function to take a final snapshot
def take_final_snapshot():
    global camera
    
    if not camera:
        print("Camera not initialized")
        return None
    
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_path = os.path.join(SNAPSHOT_DIR, f"snapshot_{timestamp}.jpg")
        
        # Capture a high-quality image
        camera.capture_file(snapshot_path)
        print(f"Final snapshot saved to {snapshot_path}")
        
        # Update JSON with image path
        if args.json_id:
            update_json_data(image_path=snapshot_path)
        
        return snapshot_path
    except Exception as e:
        print(f"Error taking snapshot: {e}")
        return None

# Function to update JSON data
def update_json_data(image_path=None, cache_img_path=None):
    if not args.json_id:
        return
    
    # File paths
    user_data_file = os.path.join(DATA_DIR, f"temp_user_data_{args.json_id}.json")
    
    # Prepare data
    data = {
        "timestamp": datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    }
    
    if image_path:
        data["image_path"] = image_path
    
    if cache_img_path:
        data["cache_img_path"] = cache_img_path
    
    # Try to merge with existing user data
    if os.path.exists(user_data_file):
        try:
            with open(user_data_file, 'r') as f:
                user_data = json.load(f)
            
            # Merge data
            for key, value in user_data.items():
                if key not in data:
                    data[key] = value
        except Exception as e:
            print(f"Error reading user data: {e}")
    
    # Write updated data
    output_file = os.path.join(DATA_DIR, f"photo_data_{args.json_id}.json")
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Updated session data saved to {output_file}")

# Main function
def main():
    global running, current_count, preview_taken
    
    # Initialize camera
    if not init_camera():
        print("Failed to initialize camera, exiting")
        return 1
    
    # Initialize pygame display
    display = init_pygame()
    
    try:
        # Set up fonts
        font_large = pygame.font.Font(None, 300)
        font_medium = pygame.font.Font(None, 100)
        
        # Countdown loop
        start_time = time.time()
        preview_time = start_time + (args.countdown / 2)  # Halfway point
        end_time = start_time + args.countdown
        
        while running and time.time() < end_time:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
            
            # Calculate remaining time
            remaining = end_time - time.time()
            count = max(0, int(remaining))
            
            # Take cache photo at halfway point
            if not preview_taken and time.time() >= preview_time:
                print("Taking cache photo at halfway point")
                take_cache_photo()
            
            # Prepare display
            display.fill((0, 0, 0))
            
            # Determine text color (red for last second)
            text_color = (255, 255, 255) if count > 1 else (255, 50, 50)
            
            # Render countdown number
            count_text = font_large.render(str(count), True, text_color)
            count_rect = count_text.get_rect(center=display.get_rect().center)
            display.blit(count_text, count_rect)
            
            # Render message
            message = "Get ready!" if count > 1 else "SMILE!"
            msg_text = font_medium.render(message, True, (255, 255, 255))
            msg_rect = msg_text.get_rect(center=(display.get_rect().centerx, display.get_rect().centery - 200))
            display.blit(msg_text, msg_rect)
            
            # Update display
            pygame.display.flip()
            
            # Sleep briefly
            time.sleep(0.05)
        
        if running:
            # Countdown finished, take final photo
            print("Countdown complete, taking final snapshot")
            snapshot_path = take_final_snapshot()
            
            # Display "Processing..." message
            display.fill((0, 0, 0))
            processing_text = font_medium.render("Processing...", True, (255, 255, 255))
            processing_rect = processing_text.get_rect(center=display.get_rect().center)
            display.blit(processing_text, processing_rect)
            pygame.display.flip()
            
            # Wait briefly to show processing message
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Program interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up resources
        cleanup()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

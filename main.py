#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
import subprocess
import os
import signal
import sys
import threading
import json
import datetime
import shutil
import glob

# GPIO Configuration
PIR_PIN = 23
BUTTON_PIN = 17
LED_PIN = 24

# States
IDLE = "idle"
USER_INPUT = "input"
DETECTION = "detect"
PHOTO = "photo"
REVIEW = "review"


class PhotoboothSystem:
    def __init__(self):
        self.current_state = IDLE
        self.ui_process = None
        self.detection_process = None
        self.photo_process = None
        self.review_process = None
        self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.skip_key_pressed = False

        # Initialize session data
        self.session_data = {
            "story_id": None,
            "users": {"names": [], "detected_props": [], "appearance": ""},
            "timestamp": "",
            "image_path": "",
            "cache_image_path": "",
        }

        # Create directories
        os.makedirs("cache", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        os.makedirs("snapshots", exist_ok=True)

        try:
            # Setup GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(PIR_PIN, GPIO.IN)
            GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(LED_PIN, GPIO.OUT)
            GPIO.output(LED_PIN, GPIO.LOW)

            # Register interrupts with longer debounce
            GPIO.add_event_detect(
                PIR_PIN, GPIO.RISING, callback=self.motion_detected, bouncetime=500
            )
            GPIO.add_event_detect(
                BUTTON_PIN, GPIO.FALLING, callback=self.button_pressed, bouncetime=500
            )
        except Exception as e:
            print(f"GPIO setup error (this is normal on non-RPi systems): {e}")
            print("Continuing in keyboard-control mode.")

        print("Photobooth system initialized.")
        print("Displaying idle screen. Press 's' to skip PIR and go to user input")
        self.start_idle_screen()

        # Start key press monitoring thread
        threading.Thread(target=self.monitor_skip_key, daemon=True).start()

    def monitor_skip_key(self):
        """Monitor for 's' key press to skip PIR motion detection"""
        try:
            # First try to import getch for non-blocking keyboard input
            try:
                import getch

                has_getch = True
            except ImportError:
                has_getch = False

            print("Key monitoring active. Press 's' to skip to user input.")
            while self.current_state == IDLE:
                if has_getch:
                    # Non-blocking method
                    if getch.kbhit():  # Check if a key is pressed
                        key = getch.getch()
                        if key.lower() == "s":
                            print("Skip key pressed, going to user input")
                            self.skip_key_pressed = True
                            self.transition_to_user_input()
                else:
                    # Fallback to input() method (will block until Enter is pressed)
                    threading.Thread(
                        target=self.alternate_key_monitor, daemon=True
                    ).start()
                    break  # Exit this loop since we're using the alternate method

                time.sleep(0.1)
        except Exception as e:
            print(f"Error in key monitoring: {e}")
            # Fall back to alternate method
            threading.Thread(target=self.alternate_key_monitor, daemon=True).start()

    def alternate_key_monitor(self):
        """Alternative method to monitor for 's' key if getch is not available"""
        print("Key monitoring active. Press 's' and Enter to skip to user input.")
        while self.current_state == IDLE:
            try:
                key = input("")
                if key.lower() == "s":
                    print("Skip key pressed, going to user input")
                    self.skip_key_pressed = True
                    self.transition_to_user_input()
            except Exception:
                pass
            time.sleep(0.1)

    def start_idle_screen(self):
        """Display the idle screen"""
        self.stop_all_processes()

        try:
            self.ui_process = subprocess.Popen(
                ["python3", "idle_screen.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            self.current_state = IDLE
            print("Idle screen started. Waiting for motion...")

            # Monitor idle screen output
            threading.Thread(target=self.monitor_idle_screen, daemon=True).start()
        except FileNotFoundError:
            print("Warning: idle_screen.py not found. Continuing without idle screen.")
            self.current_state = IDLE

    def monitor_idle_screen(self):
        """Monitor idle screen process for any output"""
        if not self.ui_process:
            return

        try:
            self.read_process_output(self.ui_process.stdout, "IDLE")
            self.read_process_output(self.ui_process.stderr, "IDLE ERROR")
        except Exception as e:
            print(f"Error monitoring idle screen: {e}")

    def motion_detected(self, channel):
        """Callback when motion is detected"""
        if self.current_state == IDLE and not self.skip_key_pressed:
            print("Motion detected! Starting user input screen...")
            time.sleep(0.5)
            try:
                if GPIO.input(PIR_PIN):
                    self.transition_to_user_input()
            except Exception:
                # If GPIO error, just proceed anyway
                self.transition_to_user_input()

    def button_pressed(self, channel):
        """Callback when button is pressed"""
        if self.current_state == DETECTION:
            print("Snapshot button pressed! Starting photo capture...")
            try:
                if not GPIO.input(BUTTON_PIN):
                    # Stop detection process
                    self.stop_process(self.detection_process)
                    self.detection_process = None

                    # Turn on LED
                    try:
                        GPIO.output(LED_PIN, GPIO.HIGH)
                    except Exception:
                        pass  # Ignore GPIO errors

                    # Start photo capture
                    self.start_photo_capture()
            except Exception:
                # If GPIO error, just proceed anyway
                self.stop_process(self.detection_process)
                self.detection_process = None
                self.start_photo_capture()

    def start_photo_capture(self):
        """Start photo capture with countdown"""
        self.current_state = PHOTO

        # Generate temp file path for user data
        data_json_path = os.path.join("data", f"temp_user_data_{self.session_id}.json")

        # Save current session data to temp file
        with open(data_json_path, "w") as f:
            json.dump(self.session_data, f, indent=2)

        # Start photo capture process
        cmd = [
            "python3",
            "photo_capture.py",
            "--fullscreen",
            "--countdown",
            "5",
            "--json-id",
            self.session_id,
        ]

        # Add cache path if available
        if self.session_data.get("cache_image_path"):
            cmd.extend(["--cache-path", self.session_data["cache_image_path"]])

        print(f"Starting photo capture with command: {' '.join(cmd)}")

        # Run photo capture app
        self.photo_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        # Monitor photo capture
        threading.Thread(target=self.monitor_photo_process).start()

    def monitor_photo_process(self):
        """Monitor the photo capture process"""
        if not self.photo_process:
            return

        try:
            # Process stdout and stderr
            stdout_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.photo_process.stdout, "PHOTO"),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.photo_process.stderr, "PHOTO ERROR"),
                daemon=True,
            )

            stdout_thread.start()
            stderr_thread.start()

            # Wait for process to complete
            self.photo_process.wait()

            # After photo capture is complete, update data and transition to review
            self.update_session_data_from_json()
            self.transition_to_snapshot_review()

        except Exception as e:
            print(f"Error in photo capture: {e}")
        finally:
            self.stop_process(self.photo_process)
            self.photo_process = None
            try:
                GPIO.output(LED_PIN, GPIO.LOW)
            except Exception:
                pass  # Ignore GPIO errors

    def read_process_output(self, stream, prefix):
        """Read and log process output"""
        if not stream:
            return

        try:
            for line in stream:
                line = line.strip()
                if line:
                    print(f"{prefix}: {line}")

                    # Parse important output from photo_capture
                    if "Final snapshot saved to" in line:
                        path = line.split("to", 1)[1].strip()
                        if os.path.exists(path):
                            self.session_data["image_path"] = path
                            print(f"Updated session with image path: {path}")
                    elif "Cache image saved to" in line:
                        path = line.split("to", 1)[1].strip()
                        if os.path.exists(path):
                            self.session_data["cache_image_path"] = path
                            print(f"Updated session with cache path: {path}")
                    # Parse important output from review
                    elif line.startswith("PREVIEW_RESULT:"):
                        result = line.split(":", 1)[1]
                        print(f"Got preview result: {result}")
                        if result == "continue":
                            # Save and continue
                            self.save_session_data()
                            self.start_idle_screen()
                        elif result == "try_again":
                            # Try again
                            self.transition_to_detection()
                    # Parse user data from user input
                    elif line.startswith("USER_DATA:"):
                        try:
                            data_json = line[len("USER_DATA:") :]
                            user_data = json.loads(data_json)
                            print(f"User data received: {user_data}")

                            # Update session data
                            self.session_data["story_id"] = user_data.get("STORY_ID")

                            # Extract names
                            names = []
                            for key in [
                                "NAME_A",
                                "NAME_B",
                                "NAME_C",
                                "NAME_D",
                                "NAME_E",
                            ]:
                                if key in user_data and user_data[key].strip():
                                    names.append(user_data[key])

                            self.session_data["users"]["names"] = names

                            # Save to JSON file for other components
                            data_json_path = os.path.join(
                                "data", f"temp_user_data_{self.session_id}.json"
                            )
                            with open(data_json_path, "w") as f:
                                json.dump(self.session_data, f, indent=2)
                            print(f"User data saved to: {data_json_path}")

                            # Go to detection state
                            self.transition_to_detection()
                        except json.JSONDecodeError as e:
                            print(f"Error parsing user data: {e}")
        except Exception as e:
            print(f"Error reading output: {e}")

    def update_session_data_from_json(self):
        """Update session data from latest JSON files"""
        try:
            # Find JSON files for this session
            json_files = glob.glob(os.path.join("data", f"*{self.session_id}*.json"))

            if json_files:
                # Get the most recent file
                latest_file = sorted(json_files)[-1]
                print(f"Loading session data from {latest_file}")

                with open(latest_file, "r") as f:
                    data = json.load(f)

                # Update our session data with new information
                for key in ["image_path", "cache_image_path"]:
                    if key in data and data[key]:
                        self.session_data[key] = data[key]
                        print(f"Updated {key} to: {data[key]}")

                # Update props if available
                if "users" in data and "detected_props" in data["users"]:
                    self.session_data["users"]["detected_props"] = data["users"][
                        "detected_props"
                    ]
                    print(
                        f"Updated detected_props to: {data['users']['detected_props']}"
                    )

                # Update story_id if needed
                if (
                    "story_id" in data
                    and data["story_id"]
                    and not self.session_data["story_id"]
                ):
                    self.session_data["story_id"] = data["story_id"]
                    print(f"Updated story_id to: {data['story_id']}")
        except Exception as e:
            print(f"Error updating session data from JSON: {e}")

    def transition_to_snapshot_review(self):
        """Transition to reviewing the snapshot"""
        print("Transitioning to snapshot review...")
        self.current_state = REVIEW

        # Update from JSON files first
        self.update_session_data_from_json()

        # Check if we have a snapshot to review
        if not self.session_data.get("image_path") or not os.path.exists(
            self.session_data["image_path"]
        ):
            print("No valid snapshot found, looking for latest snapshot")
            self.find_latest_snapshot()

        # Now check again
        if self.session_data.get("image_path") and os.path.exists(
            self.session_data["image_path"]
        ):
            print(f"Using image path: {self.session_data['image_path']}")
            self.show_review_screen(self.session_data["image_path"])
        else:
            print("No valid snapshot found, returning to detection")
            self.transition_to_detection()

    def find_latest_snapshot(self):
        """Find the latest snapshot file"""
        try:
            snapshot_files = [
                f
                for f in os.listdir("snapshots")
                if f.startswith("snapshot_") and f.endswith(".jpg")
            ]

            if snapshot_files:
                latest = sorted(snapshot_files)[-1]
                snapshot_path = os.path.join("snapshots", latest)
                self.session_data["image_path"] = snapshot_path
                print(f"Found latest snapshot: {snapshot_path}")
        except Exception as e:
            print(f"Error finding latest snapshot: {e}")

    def show_review_screen(self, image_path):
        """Show review screen"""
        print(f"Showing review screen: {image_path}")

        # Check if review script exists
        if os.path.exists("photo_preview.py"):
            preview_script = "photo_preview.py"
        elif os.path.exists("preview_screen.py"):
            preview_script = "preview_screen.py"
        else:
            print("No review script found, saving data and returning to idle")
            self.save_session_data()
            self.start_idle_screen()
            return

        # Start preview process
        cmd = ["python3", preview_script, "--image", image_path]
        print(f"Running command: {' '.join(cmd)}")

        self.review_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
        )

        # Monitor for result
        threading.Thread(target=self.monitor_review_process).start()

    def monitor_review_process(self):
        """Monitor the review process"""
        if not self.review_process:
            return

        try:
            # Read stdout and stderr
            stdout_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.review_process.stdout, "REVIEW"),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.review_process.stderr, "REVIEW ERROR"),
                daemon=True,
            )

            stdout_thread.start()
            stderr_thread.start()

            # Wait for process to complete
            self.review_process.wait()

            print(f"DEBUG: Review process ended. Current state: {self.current_state}")

            # Process ended, save data and return to idle or detection
            if self.current_state == REVIEW:
                print("DEBUG: Transitioning from review state")
                self.save_session_data()
                self.start_idle_screen()

        except Exception as e:
            print(f"Error in review: {e}")
            self.save_session_data()
            self.start_idle_screen()
        finally:
            self.stop_process(self.review_process)
            self.review_process = None

    def save_session_data(self):
        """Save the session data to file"""
        # Add timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_data["timestamp"] = timestamp

        # Save to file
        filename = f"data/session_{timestamp}.json"
        try:
            with open(filename, "w") as f:
                json.dump(self.session_data, f, indent=2)
            print(f"Session data saved: {filename}")

            # Clean up temp files
            temp_files = glob.glob(
                os.path.join("data", f"temp_user_data_{self.session_id}.json")
            )
            for file in temp_files:
                try:
                    os.remove(file)
                except:
                    pass

        except Exception as e:
            print(f"Error saving session data: {e}")

    def transition_to_user_input(self):
        """Transition to user input screen"""
        self.stop_all_processes()
        self.skip_key_pressed = False  # Reset skip flag

        # Generate new session ID for this user interaction
        self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Reset session data
        self.session_data = {
            "story_id": None,
            "users": {"names": [], "detected_props": [], "appearance": ""},
            "timestamp": "",
            "image_path": "",
            "cache_image_path": "",
        }

        print("Starting user input...")
        try:
            self.ui_process = subprocess.Popen(
                ["python3", "user_input_app.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            self.current_state = USER_INPUT

            # Monitor for user data
            threading.Thread(target=self.monitor_ui_process).start()
        except FileNotFoundError:
            print("Warning: user_input_app.py not found. Using mock user input.")
            self.mock_user_input()

    def mock_user_input(self):
        """Create mock user input for testing"""
        print("Creating mock user data...")

        # Create mock user data
        user_data = {
            "STORY_ID": 1,
            "NAME_A": "User A",
            "NAME_B": "User B",
            "NAME_C": "",
            "NAME_D": "",
            "NAME_E": "",
        }

        # Update session data
        self.session_data["story_id"] = user_data["STORY_ID"]

        # Extract names
        names = []
        for key in ["NAME_A", "NAME_B", "NAME_C", "NAME_D", "NAME_E"]:
            if key in user_data and user_data[key].strip():
                names.append(user_data[key])

        self.session_data["users"]["names"] = names

        # Save to temp file
        data_json_path = os.path.join("data", f"temp_user_data_{self.session_id}.json")
        with open(data_json_path, "w") as f:
            json.dump(self.session_data, f, indent=2)
        print(f"Mock user data saved to: {data_json_path}")

        # Proceed to detection
        self.transition_to_detection()

    def monitor_ui_process(self):
        """Monitor UI process for user data"""
        if not self.ui_process:
            return

        print("Monitoring UI process")
        try:
            # Use the read_process_output method to handle both stdout and stderr
            # This will automatically handle the USER_DATA parsing
            stdout_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.ui_process.stdout, "UI"),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.ui_process.stderr, "UI ERROR"),
                daemon=True,
            )

            stdout_thread.start()
            stderr_thread.start()

            # Wait for process to complete
            self.ui_process.wait()

            # If we get here and still in USER_INPUT state, no data was received
            if self.current_state == USER_INPUT:
                print("UI process ended without providing user data")
                self.start_idle_screen()

        except Exception as e:
            print(f"Error monitoring UI: {e}")
            self.start_idle_screen()
        finally:
            self.stop_process(self.ui_process)
            self.ui_process = None

    def monitor_review_process(self):
        """Monitor the review process"""
        if not self.review_process:
            return

        try:
            # Read stdout and stderr
            stdout_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.review_process.stdout, "REVIEW"),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.review_process.stderr, "REVIEW ERROR"),
                daemon=True,
            )

            stdout_thread.start()
            stderr_thread.start()

            # Wait for process to complete
            self.review_process.wait()

            print(f"DEBUG: Review process ended. Current state: {self.current_state}")

            # Process ended, save data and return to idle or detection
            if self.current_state == REVIEW:
                print("DEBUG: Transitioning from review state")
                self.save_session_data()
                self.start_idle_screen()

        except Exception as e:
            print(f"Error in review: {e}")
            self.save_session_data()
            self.start_idle_screen()
        finally:
            self.stop_process(self.review_process)
            self.review_process = None

    def transition_to_detection(self):
        """Transition to detection state"""
        self.stop_all_processes()

        try:
            # Attempt to release any existing camera resources
            try:
                import subprocess

                # Kill any existing camera-related processes
                subprocess.run(
                    ["pkill", "-f", "python.*camera"], stderr=subprocess.DEVNULL
                )
                subprocess.run(["pkill", "-f", "libcamera"], stderr=subprocess.DEVNULL)
                time.sleep(1)  # Give some time for processes to terminate
            except Exception as e:
                print(f"Error releasing camera resources: {e}")

            # Make sure we have current data
            self.update_session_data_from_json()

            # Prepare command with session ID
            cmd = ["python3", "detection_app.py", "-i", "rpi"]

            # Prepare environment
            env = os.environ.copy()
            if "DISPLAY" not in env:
                env["DISPLAY"] = ":0"

            # Prepare additional arguments
            additional_args = {
                "json_id": self.session_id,
                "cache_path": self.session_data.get("cache_image_path"),
                "prop_list": self.session_data["users"].get("detected_props", []),
            }

            # Pass additional arguments as a JSON-encoded environment variable
            env["DETECTION_ARGS"] = json.dumps(additional_args)

            print(f"Starting detection with command: {' '.join(cmd)}")

            # Run detection app
            self.detection_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                env=env,
            )
            self.current_state = DETECTION
            print(f"Detection process started. Press button to take photo.")

            # Monitor detection process
            threading.Thread(target=self.monitor_detection_process, daemon=True).start()

        except Exception as e:
            print(f"Error starting detection: {e}")
            self.start_idle_screen()

    def monitor_detection_process(self):
        """Monitor detection process and restart if needed"""
        if not self.detection_process:
            return

        try:
            # Monitor stdout and stderr
            stdout_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.detection_process.stdout, "DETECTION"),
                daemon=True,
            )
            stderr_thread = threading.Thread(
                target=self.read_process_output,
                args=(self.detection_process.stderr, "DETECTION ERROR"),
                daemon=True,
            )

            stdout_thread.start()
            stderr_thread.start()

            # Wait for process to complete
            self.detection_process.wait()

            # If we get here and still in detection state, restart
            if self.current_state == DETECTION:
                print("Detection process ended, restarting...")
                self.transition_to_detection()

        except Exception as e:
            print(f"Error monitoring detection: {e}")

    def stop_process(self, process):
        """Stop a single process safely"""
        if process and process.poll() is None:
            try:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
            except:
                pass

    def stop_all_processes(self):
        """Stop all running processes"""
        for process in [
            self.ui_process,
            self.detection_process,
            self.photo_process,
            self.review_process,
        ]:
            self.stop_process(process)

        # Reset references
        self.ui_process = None
        self.detection_process = None
        self.photo_process = None
        self.review_process = None

    def cleanup(self):
        """Clean up resources"""
        print("Cleaning up...")
        self.stop_all_processes()

        # Clean up temp files
        temp_files = glob.glob(os.path.join("data", "temp_user_data_*.json"))
        for file in temp_files:
            try:
                os.remove(file)
            except:
                pass

        try:
            GPIO.cleanup()
        except Exception:
            pass  # Ignore GPIO errors
        print("Cleanup complete.")

    def simulate_button_press(self):
        """Simulate button press for testing"""
        if self.current_state == DETECTION:
            print("Simulating button press")
            self.button_pressed(None)


def main():
    try:
        # Set signal handlers
        signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))

        # Create and run photobooth
        photobooth = PhotoboothSystem()

        print("Photobooth system running. Press CTRL+C to exit.")
        print("Press 's' to skip to user input.")
        print("Press 'b' to simulate button press when in detection state.")

        # Simple command interface for testing
        while True:
            try:
                cmd = input("")
                if cmd.lower() == "b" and photobooth.current_state == DETECTION:
                    photobooth.simulate_button_press()
            except (EOFError, KeyboardInterrupt):
                break
            except Exception:
                pass
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("Program terminated by user.")
    except SystemExit:
        print("System exit requested.")
    finally:
        if "photobooth" in locals():
            photobooth.cleanup()
        print("Photobooth system exited.")


if __name__ == "__main__":
    main()

# #!/usr/bin/env python3
# import gi
# import json
# import os
# import glob
# import argparse
# import sys
# import datetime
# import cv2
# import threading
# import time

# gi.require_version('Gst', '1.0')
# from gi.repository import Gst
# import hailo
# from hailo_apps_infra.hailo_rpi_common import app_callback_class
# from hailo_apps_infra.detection_pipeline_simple import GStreamerDetectionApp

# # Parse arguments
# parser = argparse.ArgumentParser()
# parser.add_argument("--json-id", type=str, help="Session ID for JSON handling")
# parser.add_argument("--prop-list", type=str, nargs="*", default=[], help="List of detected properties")
# parser.add_argument("--cache-path", type=str, help="Path to cache image")
# parser.add_argument("--display", action="store_true", help="Enable display window")
# parser.add_argument("--fullscreen", action="store_true", help="Enable fullscreen mode (with --display)")
# parser.add_argument("--width", type=int, default=1280, help="Display width")
# parser.add_argument("--height", type=int, default=720, help="Display height")
# parser.add_argument("--exit-after", type=int, help="Exit after N seconds")
# args = parser.parse_args()

# # Create directories
# DATA_DIR = "./data"
# os.makedirs(DATA_DIR, exist_ok=True)

# # Global variables
# display_enabled = args.display
# running = True
# last_detections = []

# # User-defined class to be used in the callback function
# class user_app_callback_class(app_callback_class):
#     def __init__(self):
#         super().__init__()
#         self.window_name = None

#         # Set up display window if requested
#         if display_enabled:
#             self.setup_display()

#     def setup_display(self):
#         """Set up display window for visualization"""
#         try:
#             self.window_name = "Detection"
#             cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
#             cv2.resizeWindow(self.window_name, args.width, args.height)

#             # Set aspect ratio preference
#             cv2.setWindowProperty(self.window_name, cv2.WND_PROP_ASPECT_RATIO, cv2.WINDOW_KEEPRATIO)

#             # Set fullscreen if requested
#             if args.fullscreen:
#                 cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
#                 print(f"Set up fullscreen window at {args.width}x{args.height}")
#             else:
#                 print(f"Set up window at {args.width}x{args.height}")
#         except Exception as e:
#             print(f"Error setting up display: {e}")
#             self.window_name = None

# # Save detections to JSON file
# def save_detections_to_json(detections):
#     """Save detection results to a JSON file"""
#     if not args.json_id:
#         return

#     # Create timestamp
#     timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

#     # Prepare data
#     data = {
#         "timestamp": timestamp,
#         "detections": detections,
#         "prop_list": args.prop_list,
#         "cache_img_path": args.cache_path
#     }

#     # Find existing session data file
#     user_data_file = os.path.join(DATA_DIR, f"temp_user_data_{args.json_id}.json")
#     if os.path.exists(user_data_file):
#         try:
#             # Load existing data
#             with open(user_data_file, 'r') as f:
#                 user_data = json.load(f)

#             # Merge with our detection data
#             if "story_id" in user_data:
#                 data["story_id"] = user_data["story_id"]

#             if "users" in user_data:
#                 data["users"] = user_data["users"]

#                 # Update detected props
#                 if detections:
#                     props = [d["label"] for d in detections if d.get("confidence", 0) >= 0.7]
#                     if props:
#                         data["users"]["detected_props"] = props
#         except Exception as e:
#             print(f"Error loading user data: {e}")

#     # Create output filename with session ID and timestamp
#     filename = os.path.join(DATA_DIR, f"detection_data_{args.json_id}_{timestamp}.json")

#     # Write data to file
#     try:
#         with open(filename, 'w') as f:
#             json.dump(data, f, indent=2)
#         print(f"Saved detections to {filename}")
#     except Exception as e:
#         print(f"Error saving detections: {e}")

# # Extract frame from buffer for display
# def extract_frame(buffer, pad):
#     """Extract frame from GStreamer buffer for display"""
#     if not buffer or not display_enabled:
#         return None

#     try:
#         # Get frame dimensions from caps
#         caps = pad.get_current_caps()
#         if not caps:
#             return None

#         structure = caps.get_structure(0)
#         width = structure.get_value("width")
#         height = structure.get_value("height")

#         # Map buffer to get data
#         success, mapinfo = buffer.map(Gst.MapFlags.READ)
#         if not success:
#             return None

#         try:
#             # Convert buffer data to numpy array
#             frame_data = mapinfo.data
#             frame_array = np.frombuffer(frame_data, dtype=np.uint8)

#             # Reshape based on dimensions
#             if len(frame_array) == width * height * 3:  # RGB/BGR format
#                 frame = frame_array.reshape((height, width, 3))

#                 # Resize to target dimensions if needed
#                 if width != args.width or height != args.height:
#                     frame = cv2.resize(frame, (args.width, args.height))

#                 return frame.copy()  # Make a copy before unmapping
#             else:
#                 return None
#         finally:
#             buffer.unmap(mapinfo)
#     except Exception as e:
#         print(f"Error extracting frame: {e}")

#     return None

# # Draw detection overlays on frame
# def draw_detections(frame, detections):
#     """Draw detection boxes and labels on frame"""
#     if frame is None or not detections:
#         return frame

#     # Create a copy to avoid modifying the original
#     result = frame.copy()

#     # Draw each detection
#     for det in detections:
#         label = det.get("label", "Unknown")
#         confidence = det.get("confidence", 0)

#         # Each detection might have different bbox format
#         # Try to handle common cases
#         try:
#             bbox = None
#             if "bbox" in det:
#                 if isinstance(det["bbox"], dict):
#                     if all(k in det["bbox"] for k in ["xmin", "ymin", "xmax", "ymax"]):
#                         bbox = [
#                             int(det["bbox"]["xmin"]),
#                             int(det["bbox"]["ymin"]),
#                             int(det["bbox"]["xmax"]),
#                             int(det["bbox"]["ymax"])
#                         ]
#                 elif isinstance(det["bbox"], (list, tuple)) and len(det["bbox"]) >= 4:
#                     bbox = [int(v) for v in det["bbox"][:4]]

#             if bbox:
#                 # Draw rectangle
#                 cv2.rectangle(result, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)

#                 # Draw label with confidence
#                 text = f"{label}: {confidence:.2f}"
#                 cv2.putText(result, text, (bbox[0], bbox[1] - 10),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
#             else:
#                 # If no valid bbox, just show label at top of screen
#                 y_pos = 30 + (detections.index(det) * 30)
#                 text = f"{label}: {confidence:.2f}"
#                 cv2.putText(result, text, (10, y_pos),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
#         except Exception as e:
#             print(f"Error drawing detection: {e}")

#     return result

# # User-defined callback function
# def app_callback(pad, info, user_data):
#     global running, last_detections

#     # Check if we should exit
#     if not running:
#         return Gst.PadProbeReturn.REMOVE

#     # Count frames
#     user_data.increment()
#     frame_count = user_data.get_count()

#     # Only log every 30 frames to reduce console output
#     log_frame = (frame_count % 30 == 0)
#     if log_frame:
#         print(f"Frame count: {frame_count}")

#     # Get buffer and check validity
#     buffer = info.get_buffer()
#     if buffer is None:
#         return Gst.PadProbeReturn.OK

#     # Process detections
#     detections = []
#     roi = hailo.get_roi_from_buffer(buffer)
#     if roi:
#         for detection in roi.get_objects_typed(hailo.HAILO_DETECTION):
#             # Extract detection info
#             detection_info = {
#                 "label": detection.get_label(),
#                 "confidence": detection.get_confidence()
#             }

#             # Try to get bounding box info if available
#             try:
#                 # Get bounding box (handle different API versions)
#                 bbox = {}

#                 # Try different methods based on API version
#                 if hasattr(detection, "get_bbox_xmin"):
#                     bbox = {
#                         "xmin": detection.get_bbox_xmin(),
#                         "ymin": detection.get_bbox_ymin(),
#                         "xmax": detection.get_bbox_xmax(),
#                         "ymax": detection.get_bbox_ymax()
#                     }
#                 elif hasattr(detection, "get_bbox"):
#                     bbox_obj = detection.get_bbox()
#                     if bbox_obj:
#                         bbox = {
#                             "xmin": bbox_obj.xmin(),
#                             "ymin": bbox_obj.ymin(),
#                             "xmax": bbox_obj.xmax(),
#                             "ymax": bbox_obj.ymax()
#                         }

#                 detection_info["bbox"] = bbox
#             except Exception:
#                 # Ignore bbox errors - not all detections have bounding boxes
#                 pass

#             # Add to detections list
#             detections.append(detection_info)

#             # Log detection info
#             if log_frame:
#                 print(f"Detection: {detection.get_label()} Confidence: {detection.get_confidence():.2f}")

#     # Update last detections
#     if detections:
#         last_detections = detections

#     # Save detections occasionally
#     if frame_count % 60 == 0 and args.json_id:
#         save_detections_to_json(last_detections)

#     # Display frame if enabled
#     if display_enabled and hasattr(user_data, 'window_name') and user_data.window_name:
#         # Extract frame for display
#         try:
#             frame = extract_frame(buffer, pad)

#             if frame is not None:
#                 # Draw detection overlays
#                 display_frame = draw_detections(frame, detections)

#                 # Show frame
#                 cv2.imshow(user_data.window_name, display_frame)

#                 # Process keyboard input
#                 key = cv2.waitKey(1) & 0xFF
#                 if key == 27:  # ESC
#                     print("ESC key pressed, exiting")
#                     running = False
#                 elif key == ord('s'):  # 's' key for saving detections
#                     print("Saving current detections")
#                     save_detections_to_json(last_detections)
#         except Exception as e:
#             print(f"Error displaying frame: {e}")

#     return Gst.PadProbeReturn.OK

# # Function to auto-exit after timeout
# def exit_timer():
#     """Exit the application after specified timeout"""
#     if not args.exit_after:
#         return

#     print(f"Will exit after {args.exit_after} seconds")
#     time.sleep(args.exit_after)

#     global running
#     print("Exit timer expired, shutting down")
#     running = False

# if __name__ == "__main__":
#     # Initialize GStreamer
#     Gst.init(None)

#     # Print configuration
#     print(f"Detection app starting with configuration:")
#     print(f"  JSON ID: {args.json_id}")
#     print(f"  Cache path: {args.cache_path}")
#     print(f"  Props list: {args.prop_list}")
#     print(f"  Display: {args.display}")
#     if args.display:
#         print(f"  Resolution: {args.width}x{args.height}")
#         print(f"  Fullscreen: {args.fullscreen}")

#     try:
#         # Create user data instance
#         user_data = user_app_callback_class()

#         # Create and start the app
#         app = GStreamerDetectionApp(app_callback, user_data)

#         # Start exit timer if specified
#         if args.exit_after:
#             timer_thread = threading.Thread(target=exit_timer)
#             timer_thread.daemon = True
#             timer_thread.start()

#         # Run the app (this blocks until completion)
#         app.run()

#     except KeyboardInterrupt:
#         print("Interrupted by user")
#     except Exception as e:
#         print(f"Error running detection app: {e}")
#         import traceback
#         traceback.print_exc()
#     finally:
#         # Final cleanup
#         if display_enabled:
#             cv2.destroyAllWindows()

#         # Save final detections
#         if args.json_id and last_detections:
#             save_detections_to_json(last_detections)

#!/usr/bin/env python3
import gi
import json
import os
import argparse
import sys
import datetime
import cv2
import numpy as np
import threading
import time

gi.require_version("Gst", "1.0")
from gi.repository import Gst
import hailo
from hailo_apps_infra.hailo_rpi_common import app_callback_class
from hailo_apps_infra.detection_pipeline_simple import GStreamerDetectionApp

# Global variables
running = True
last_detections = []
display_window = None
additional_args = {}


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Hailo Detection Application")

    # Hailo standard arguments
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        help="Input source. Can be a file, USB (webcam), RPi camera (CSI camera module) or ximage. "
        "For RPi camera use '-i rpi'. For USB camera use '-i usb' or '/dev/video<X>'",
    )
    parser.add_argument(
        "--use-frame",
        "-u",
        action="store_true",
        help="Use frame from the callback function",
    )
    parser.add_argument(
        "--show-fps", "-f", action="store_true", help="Print FPS on sink"
    )
    parser.add_argument(
        "--arch",
        choices=["hailo8", "hailo8l"],
        help="Specify the Hailo architecture (hailo8 or hailo8l)",
    )
    parser.add_argument("--hef-path", type=str, help="Path to HEF file")
    parser.add_argument(
        "--disable-sync",
        action="store_true",
        help="Disables display sink sync, will run as fast as possible",
    )
    parser.add_argument(
        "--disable-callback",
        action="store_true",
        help="Disables the user's custom callback function in the pipeline",
    )
    parser.add_argument(
        "--dump-dot",
        action="store_true",
        help="Dump the pipeline graph to a dot file pipeline.dot",
    )
    parser.add_argument(
        "--labels-json", type=str, help="Path to custom labels JSON file"
    )

    return parser.parse_args()


# Create data directory
DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)


def load_additional_args():
    """Load additional arguments from environment variable"""
    global additional_args
    try:
        detection_args_str = os.environ.get("DETECTION_ARGS", "{}")
        additional_args = json.loads(detection_args_str)
        print("Loaded additional arguments:", additional_args)
    except Exception as e:
        print(f"Error loading additional arguments: {e}")
        additional_args = {}


def save_detections_to_json(detections):
    """Save detection results to a JSON file"""
    # Use json_id from additional args if available
    json_id = additional_args.get("json_id")
    if not json_id:
        return

    # Create timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Prepare data
    data = {
        "timestamp": timestamp,
        "detections": detections,
        "prop_list": additional_args.get("prop_list", []),
        "cache_img_path": additional_args.get("cache_path"),
    }

    # Find existing session data file
    user_data_file = os.path.join(DATA_DIR, f"temp_user_data_{json_id}.json")
    if os.path.exists(user_data_file):
        try:
            # Load existing data
            with open(user_data_file, "r") as f:
                user_data = json.load(f)

            # Merge with our detection data
            if "story_id" in user_data:
                data["story_id"] = user_data["story_id"]

            if "users" in user_data:
                data["users"] = user_data["users"]

                # Update detected props
                if detections:
                    props = [
                        d["label"] for d in detections if d.get("confidence", 0) >= 0.7
                    ]
                    if props:
                        data["users"]["detected_props"] = props
        except Exception as e:
            print(f"Error loading user data: {e}")

    # Create output filename with session ID and timestamp
    filename = os.path.join(DATA_DIR, f"detection_data_{json_id}_{timestamp}.json")

    # Write data to file
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved detections to {filename}")
    except Exception as e:
        print(f"Error saving detections: {e}")


# User-defined class to be used in the callback function
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()

        # Setup display window if enabled in additional args
        self.window_name = None
        # Visualization handled within the app, not through additional args


def draw_detections(frame, detections):
    """Draw detection boxes and labels on frame"""
    if frame is None or not detections:
        return frame

    result = frame.copy()

    for det in detections:
        label = det.get("label", "Unknown")
        confidence = det.get("confidence", 0)

        try:
            bbox = det.get("bbox", {})
            if bbox and all(k in bbox for k in ["xmin", "ymin", "xmax", "ymax"]):
                cv2.rectangle(
                    result,
                    (int(bbox["xmin"]), int(bbox["ymin"])),
                    (int(bbox["xmax"]), int(bbox["ymax"])),
                    (0, 255, 0),
                    2,
                )

                text = f"{label}: {confidence:.2f}"
                cv2.putText(
                    result,
                    text,
                    (int(bbox["xmin"]), int(bbox["ymin"]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )
        except Exception as e:
            print(f"Error drawing detection: {e}")

    return result


def app_callback(pad, info, user_data):
    global running, last_detections

    # Check if we should exit
    if not running:
        return Gst.PadProbeReturn.REMOVE

    # Count frames
    user_data.increment()
    frame_count = user_data.get_count()

    # Get buffer
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    # Process detections
    detections = []
    roi = hailo.get_roi_from_buffer(buffer)
    if roi:
        for detection in roi.get_objects_typed(hailo.HAILO_DETECTION):
            # Extract detection info
            detection_info = {
                "label": detection.get_label(),
                "confidence": detection.get_confidence(),
            }

            # Try to get bounding box info
            try:
                bbox = {}
                if hasattr(detection, "get_bbox_xmin"):
                    bbox = {
                        "xmin": detection.get_bbox_xmin(),
                        "ymin": detection.get_bbox_ymin(),
                        "xmax": detection.get_bbox_xmax(),
                        "ymax": detection.get_bbox_ymax(),
                    }
                elif hasattr(detection, "get_bbox"):
                    bbox_obj = detection.get_bbox()
                    if bbox_obj:
                        bbox = {
                            "xmin": bbox_obj.xmin(),
                            "ymin": bbox_obj.ymin(),
                            "xmax": bbox_obj.xmax(),
                            "ymax": bbox_obj.ymax(),
                        }

                detection_info["bbox"] = bbox
            except Exception:
                pass

            detections.append(detection_info)

    # Update last detections
    if detections:
        last_detections = detections

    # Save detections occasionally
    if frame_count % 60 == 0:
        save_detections_to_json(last_detections)

    return Gst.PadProbeReturn.OK


def main():
    global running

    # Parse arguments
    args = parse_arguments()

    # Load additional arguments from environment
    load_additional_args()

    # Initialize GStreamer
    Gst.init(None)

    try:
        # Create user data instance
        user_data = user_app_callback_class()

        # Create and start the app
        app = GStreamerDetectionApp(app_callback, user_data)

        # Run the app
        app.run()

    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error running detection app: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Save final detections
        if additional_args.get("json_id") and last_detections:
            save_detections_to_json(last_detections)


if __name__ == "__main__":
    main()

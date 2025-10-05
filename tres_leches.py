import os
import json
import random
from pathlib import Path

# Supported video file extensions
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}

def get_video_files(directory):
    """Get a set of video files in the given directory."""
    return {f.name for f in Path(directory).iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS}

def confirm_to_continue(message=""):
    """Ask the user to confirm with a keyboard press to continue."""
    try:
        if message:
            print(message)
        input("Press Enter to continue...")
    except KeyboardInterrupt:
        print("Exit signal received.")
        exit()

def handle_inprogress_files(existing_videos, data, json_file):
    """Handle files currently marked as 'inprogress'."""
    print("Files are currently marked as in progress.\n")
    for file in existing_videos["inprogress"]:
        print(f"  - {file}")

    while True:
        user_input = input("Mark files as done by entering 'd', leave the files and continue by entering 'c', or exit by entering 'x'.").strip().lower()
        if user_input == 'd':
            for file in list(existing_videos["inprogress"]):
                existing_videos["inprogress"].remove(file)
                data.setdefault("used", []).append(file)
            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Moved {len(existing_videos["inprogress"])} file(s) to 'used'.")
            break
        elif user_input == 'c':
            print("Leaving files marked as in progress.")
            break
        elif user_input == 'x':
            print("Leaving lists unchanged and exiting.")
            exit()
        else:
            print("Unrecognized input. Please try again.")
            continue

def update_json_with_videos(json_file, directory):
    """Update or create a JSON file with video files from a directory."""
    json_file_path = Path(json_file)
    
    # Get current video files in the directory
    current_videos = get_video_files(directory)

    # If the JSON file doesn't exist, create it
    if not json_file_path.exists():
        data = {
            "unused": list(current_videos),
            "used": [],
            "inprogress": [],
            "ignore": []
        }
        with open(json_file, "w") as f:
            json.dump(data, f, indent=4)
        print(f"Created {json_file} with {len(current_videos)} video(s) in 'unused'.")
    else:
        # Load existing data from JSON
        with open(json_file, "r") as f:
            data = json.load(f)
            existing_videos = {
                "unused": set(data.get("unused", [])),
                "used": set(data.get("used", [])),
                "inprogress": set(data.get("inprogress", [])),
                "ignore": set(data.get("ignore", []))
            }

        # Find new videos
        new_videos = current_videos - existing_videos["unused"] - existing_videos["used"] - existing_videos["inprogress"] - existing_videos["ignore"]

        if new_videos:
            # Add new videos to "unused"
            data["unused"].extend(new_videos)
            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Updated {json_file} with {len(new_videos)} new video(s) in 'unused'.")
        else:
            print("No new videos to add.")

        if existing_videos["inprogress"]:
            handle_inprogress_files(existing_videos, data, json_file)

def select_and_update_files(json_file, prefix, choice_count):
    """Select random filenames from 'unused', confirm selection, and move to 'inprogress'."""
    with open(json_file, "r") as f:
        data = json.load(f)

    unused_files = [file for file in data.get("unused", []) if file.startswith(prefix)]

    if not unused_files:
        print(f"No files available in 'unused' with prefix '{prefix}' to select.")
        return

    if choice_count > len(unused_files):
        print(f"Error: Requested {choice_count} files, but only {len(unused_files)} are available.")
        return

    while True:
        selected_files = random.sample(unused_files, choice_count)
        print("Selected files:")
        for file in selected_files:
            print(f"  - {file}")

        user_input = input("Confirm selection by entering 'c', or press Enter to select again: ").strip().lower()
        if user_input == "c":
            for file in selected_files:
                unused_files.remove(file)
                data["unused"].remove(file)
                data.setdefault("inprogress", []).append(file)

            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)

            print(f"Moved {len(selected_files)} file(s) to 'inprogress'.")
            break

if __name__ == "__main__":
    # User-specified directory and JSON file
    directory = input("Enter the directory to scan for video files: ").strip()
    json_file = input("Enter the JSON file path: ").strip()

    # Ensure the directory exists
    if not Path(directory).is_dir():
        print("Error: The specified directory does not exist or is inaccessible. Please check the path and try again.")
        exit(1)
    else:
        print("Video Directory:", directory)
        print("JSON Path:      ", json_file)
        confirm_to_continue("Are these settings correct?")

        update_json_with_videos(json_file, directory)

        prefix = input("Enter a filename prefix for random file selection: ").strip()
        confirm_to_continue(f"You entered '{prefix}'. Is this correct?")

        choice_count = int(input("Input number of filenames to be selected: "))
        confirm_to_continue(f"{choice_count} filenames will be randomly selected. Is this correct?")

        select_and_update_files(json_file, prefix, choice_count)

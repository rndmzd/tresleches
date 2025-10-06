import os
import json
import random
import subprocess
import shutil
from pathlib import Path

# Supported video file extensions
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}

def iter_video_files(directory):
    try:
        with os.scandir(directory) as it:
            for entry in it:
                try:
                    if entry.is_file():
                        name = entry.name
                        ext = os.path.splitext(name)[1].lower()
                        if ext in VIDEO_EXTENSIONS:
                            yield name
                except Exception:
                    continue
    except FileNotFoundError:
        return

def get_video_files(directory):
    """Get a set of video files in the given directory."""
    return set(iter_video_files(directory))

def choose_random_by_prefix(items, prefix):
    if not items:
        return None
    if not prefix:
        return random.choice(items)
    chosen = None
    n = 0
    for f in items:
        if f.startswith(prefix):
            n += 1
            if random.randrange(n) == 0:
                chosen = f
    return chosen

def confirm_to_continue(message=""):
    """Ask the user to confirm with a keyboard press to continue."""
    try:
        if message:
            print(message)
        input("Press Enter to continue...")
    except KeyboardInterrupt:
        print("Exit signal received.")
        exit()

def copy_to_working(src, working_dir):
    try:
        if src.suffix.lower() == ".mkv":
            ff = shutil.which("ffmpeg") or "ffmpeg"
            dst = Path(working_dir) / (src.stem + ".mp4")
            dst.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([ff, "-y", "-i", str(src), "-c", "copy", "-movflags", "+faststart", str(dst)], check=True)
            print(f"Remuxed to MP4: {dst.name}")
        else:
            dst = Path(working_dir) / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"Copied: {src.name}")
        return True
    except Exception as e:
        print(f"Failed to remux/copy '{src.name}': {e}")
        try:
            dst = Path(working_dir) / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"Copied without remux: {src.name}")
            return True
        except Exception as e2:
            print(f"Fallback copy failed '{src.name}': {e2}")
            return False

def preview_video(source_dir, filename):
    path = Path(source_dir) / filename
    if not path.exists():
        print(f"Preview file not found: {path}")
        return
    player = shutil.which("ffplay")
    if player:
        try:
            subprocess.run([player, "-autoexit", "-loglevel", "error", str(path)], check=False)
            return
        except Exception as e:
            print(f"ffplay preview failed: {e}")
    player = shutil.which("mpv")
    if player:
        try:
            subprocess.run([player, "--really-quiet", str(path)], check=False)
            return
        except Exception as e:
            print(f"mpv preview failed: {e}")
    player = shutil.which("vlc")
    if player:
        try:
            subprocess.run([player, "--play-and-exit", str(path)], check=False)
            return
        except Exception as e:
            print(f"vlc preview failed: {e}")
    try:
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "start", "", "/wait", str(path)], shell=False)
        elif shutil.which("xdg-open"):
            subprocess.run(["xdg-open", str(path)], check=False)
        elif shutil.which("open"):
            subprocess.run(["open", str(path)], check=False)
        else:
            print("No preview method available. Install ffmpeg (ffplay) for preview.")
    except Exception as e:
        print(f"Preview failed: {e}")

def top_up_inprogress_one_by_one(json_file, data, source_dir, working_dir, target_total=3):
    current = len(data.get("inprogress", []))
    if current >= target_total:
        return
    print(f"There are currently {current} file(s) in 'inprogress'. Proposing files one at a time to reach {target_total}.")
    while len(data.get("inprogress", [])) < target_total:
        unused = data.get("unused", [])
        prefix = data.get("last_prefix")
        candidate = choose_random_by_prefix(unused, prefix)
        if not candidate:
            if prefix:
                print(f"No files available in 'unused' with prefix '{prefix}'.")
            else:
                print("No files available in 'unused'.")
            break
        print(f"Proposed file: {candidate}")
        while True:
            ans = input("Enter 'c' to confirm, 'p' to preview, press Enter to pick another, 'x' to stop, or 'i' to ignore, or 'b' for b-roll: ").strip().lower()
            if ans == 'p':
                preview_video(source_dir, candidate)
                continue
            break
        if ans == 'x':
            break
        if ans == 'i':
            if candidate in data.get("unused", []):
                data["unused"].remove(candidate)
            data.setdefault("ignore", []).append(candidate)
            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Ignored: {candidate}")
            continue
        if ans == 'b':
            if candidate in data.get("unused", []):
                data["unused"].remove(candidate)
            data.setdefault("b-roll", []).append(candidate)
            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Added to b-roll: {candidate}")
            continue
        if ans == 'c':
            data["unused"].remove(candidate)
            data.setdefault("inprogress", []).append(candidate)
            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Added to inprogress: {candidate}")
            if working_dir:
                copy_now = input(f"Copy '{candidate}' to working directory '{working_dir}'? (y/N): ").strip().lower()
                if copy_now == 'y':
                    src = Path(source_dir) / candidate
                    copy_to_working(src, Path(working_dir))

def handle_inprogress_files(existing_videos, data, json_file, source_dir, working_dir):
    """Handle files currently marked as 'inprogress'."""
    print("Files currently marked as in progress:")
    if not existing_videos["inprogress"]:
        print("  (none)")
        return

    while True:
        inprogress_list = list(existing_videos["inprogress"])
        for idx, file in enumerate(inprogress_list, start=1):
            print(f"  {idx}. {file}")

        selection = input("Select a file number to manage, 'c' to continue, or 'x' to exit: ").strip().lower()

        if selection == 'c':
            print("Leaving files marked as in progress.")
            break
        if selection == 'x':
            print("Leaving lists unchanged and exiting.")
            exit()
        if not selection.isdigit() or not (1 <= int(selection) <= len(inprogress_list)):
            print("Invalid selection. Please try again.")
            continue

        chosen = inprogress_list[int(selection) - 1]
        action = input("Enter 'd' to mark done, 'i' to ignore, 'r' to return to unused, 'b' to mark as b-roll, or 's' to go back: ").strip().lower()

        if action == 's':
            continue

        if action == 'r':
            if chosen in existing_videos["inprogress"]:
                existing_videos["inprogress"].remove(chosen)
            if "inprogress" in data and chosen in data["inprogress"]:
                data["inprogress"].remove(chosen)
            data.setdefault("unused", []).append(chosen)
            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Returned to unused: {chosen}")

            replace = input("Replace it with another random file from 'unused'? (y/N): ").strip().lower()
            if replace == 'y':
                prefix = data.get("last_prefix")
                unused = data.get("unused", [])
                new_file = choose_random_by_prefix(unused, prefix)
                if not new_file:
                    if prefix:
                        print(f"No files available in 'unused' with prefix '{prefix}' to replace.")
                    else:
                        print("No files available in 'unused' to replace.")
                else:
                    data["unused"].remove(new_file)
                    data.setdefault("inprogress", []).append(new_file)
                    existing_videos["inprogress"].add(new_file)
                    with open(json_file, "w") as f:
                        json.dump(data, f, indent=4)
                    print(f"Added replacement file to in progress: {new_file}")

                    if working_dir:
                        copy_choice = input(f"Copy '{new_file}' to working directory '{working_dir}'? (y/N): ").strip().lower()
                        if copy_choice == 'y':
                            src = Path(source_dir) / new_file
                            copy_to_working(src, Path(working_dir))
            continue

        if action == 'b':
            if chosen in existing_videos["inprogress"]:
                existing_videos["inprogress"].remove(chosen)
            if "inprogress" in data and chosen in data["inprogress"]:
                data["inprogress"].remove(chosen)
            data.setdefault("b-roll", []).append(chosen)
            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Marked as b-roll: {chosen}")
            continue

        if action == 'd':
            if chosen in existing_videos["inprogress"]:
                existing_videos["inprogress"].remove(chosen)
            if "inprogress" in data and chosen in data["inprogress"]:
                data["inprogress"].remove(chosen)
            data.setdefault("used", []).append(chosen)
            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Marked as done: {chosen}")
            continue

        if action == 'i':
            if chosen in existing_videos["inprogress"]:
                existing_videos["inprogress"].remove(chosen)
            if "inprogress" in data and chosen in data["inprogress"]:
                data["inprogress"].remove(chosen)
            data.setdefault("ignore", []).append(chosen)
            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Ignored: {chosen}")

            replace = input("Replace it with another random file from 'unused'? (y/N): ").strip().lower()
            if replace == 'y':
                prefix = data.get("last_prefix")
                unused = data.get("unused", [])
                new_file = choose_random_by_prefix(unused, prefix)
                if not new_file:
                    if prefix:
                        print(f"No files available in 'unused' with prefix '{prefix}' to replace.")
                    else:
                        print("No files available in 'unused' to replace.")
                else:
                    data["unused"].remove(new_file)
                    data.setdefault("inprogress", []).append(new_file)
                    existing_videos["inprogress"].add(new_file)
                    with open(json_file, "w") as f:
                        json.dump(data, f, indent=4)
                    print(f"Added replacement file to in progress: {new_file}")

                    if working_dir:
                        copy_choice = input(f"Copy '{new_file}' to working directory '{working_dir}'? (y/N): ").strip().lower()
                        if copy_choice == 'y':
                            src = Path(source_dir) / new_file
                            copy_to_working(src, Path(working_dir))
            continue

        print("Unrecognized action. Please try again.")

def update_json_with_videos(json_file, directory, working_dir):
    """Update or create a JSON file with video files from a directory."""
    json_file_path = Path(json_file)
    
    if not json_file_path.exists():
        data = {
            "unused": [],
            "used": [],
            "inprogress": [],
            "ignore": [],
            "b-roll": []
        }
        count = 0
        for name in iter_video_files(directory):
            data["unused"].append(name)
            count += 1
        with open(json_file, "w") as f:
            json.dump(data, f, indent=4)
        print(f"Created {json_file} with {count} video(s) in 'unused'.")
    else:
        with open(json_file, "r") as f:
            data = json.load(f)
            if "b-roll" not in data:
                data["b-roll"] = []
                with open(json_file, "w") as wf:
                    json.dump(data, wf, indent=4)

        known = set()
        for k in ("unused", "used", "inprogress", "ignore", "b-roll"):
            known.update(data.get(k, []))
        added = 0
        for name in iter_video_files(directory):
            if name not in known:
                data.setdefault("unused", []).append(name)
                known.add(name)
                added += 1
        if added:
            with open(json_file, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Updated {json_file} with {added} new video(s) in 'unused'.")
        else:
            print("No new videos to add.")

        if data.get("inprogress"):
            existing_videos = {"inprogress": set(data.get("inprogress", []))}
            handle_inprogress_files(existing_videos, data, json_file, directory, working_dir)


if __name__ == "__main__":
    # User-specified directory and JSON file
    directory = input("Enter the directory to scan for video files: ").strip()
    working_dir = input("Enter the working directory to copy selected files (or leave blank to skip copying): ").strip()
    json_file = input("Enter the JSON file path: ").strip()

    # Ensure the directory exists
    if not Path(directory).is_dir():
        print("Error: The specified directory does not exist or is inaccessible. Please check the path and try again.")
        exit(1)
    else:
        working_dir = working_dir or None
        if working_dir:
            try:
                Path(working_dir).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Error creating working directory: {e}")
                exit(1)

        print("Video Directory:", directory)
        if working_dir:
            print("Working Directory:", working_dir)
        else:
            print("Working Directory: (none)")
        print("JSON Path:      ", json_file)
        confirm_to_continue("Are these settings correct?")

        update_json_with_videos(json_file, directory, working_dir)

        prefix = input("Enter a filename prefix to filter proposals (or leave blank for all): ").strip()
        confirm_to_continue(f"You entered '{prefix}'. Is this correct?")

        try:
            with open(json_file, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["last_prefix"] = prefix if prefix else None
        with open(json_file, "w") as f:
            json.dump(data, f, indent=4)

        top_up_inprogress_one_by_one(json_file, data, directory, working_dir, 3)

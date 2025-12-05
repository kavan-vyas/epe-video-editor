import os
import sys
import subprocess
import uuid

# Try to import imageio_ffmpeg to get the binary path
try:
    import imageio_ffmpeg
    FFMPEG_BINARY = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    print("Error: 'imageio-ffmpeg' library not found. Please install it via pip:")
    print("pip install imageio-ffmpeg")
    sys.exit(1)

def list_recordings():
    """List all available recordings"""
    recordings_dir = "recordings"
    if not os.path.exists(recordings_dir):
        print(f"Error: '{recordings_dir}' directory not found!")
        return []
    
    videos = [f for f in os.listdir(recordings_dir) if f.endswith('.mp4')]
    return videos

def list_intros():
    """List all available intro videos"""
    intro_dir = "introandoutro"
    if not os.path.exists(intro_dir):
        print(f"Error: '{intro_dir}' directory not found!")
        return []
    
    intros = [f for f in os.listdir(intro_dir) if f.endswith('.mp4') and 'intro' in f.lower()]
    return intros

def parse_time(time_str):
    """Convert MM:SS format to seconds"""
    try:
        parts = time_str.split(':')
        if len(parts) == 2:
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        else:
            print("Invalid format. Please use MM:SS")
            return None
    except ValueError:
        print("Invalid time format. Please use numbers only.")
        return None

def main():
    print("=" * 50)
    print("Video Editing Automation (Lossless Instant Speed)")
    print("=" * 50)
    
    # Create output directory if it doesn't exist
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Step 1: List and select recording
    recordings = list_recordings()
    if not recordings:
        print("No recordings found in 'recordings' folder!")
        return
    
    print("\nAvailable recordings:")
    for i, video in enumerate(recordings, 1):
        print(f"{i}. {video}")
    
    while True:
        choice = input("\nEnter the number of the recording you want to edit: ")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(recordings):
                selected_recording = recordings[idx]
                break
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a valid number.")
    
    recording_path = os.path.abspath(os.path.join("recordings", selected_recording))
    print(f"\nSelected: {selected_recording}")
    
    # Step 2: Get trim times
    print("\n" + "-" * 50)
    print("Enter trim times (format: MM:SS)")
    print("NOTE: Cuts will snap to the nearest keyframe (approx. every 2-5s)")
    print("-" * 50)
    
    while True:
        start_time_str = input("Start time (where to begin cutting): ")
        start_time = parse_time(start_time_str)
        if start_time is not None:
            break
    
    while True:
        end_time_str = input("End time (where to stop cutting): ")
        end_time = parse_time(end_time_str)
        if end_time is not None and end_time > start_time:
            break
        elif end_time is not None:
            print("End time must be after start time!")
    
    # Step 3: Select intro
    intros = list_intros()
    intro_path = None
    if not intros:
        print("\nWarning: No intro videos found in 'introandoutro' folder!")
    else:
        print("\n" + "-" * 50)
        print("Available intro videos:")
        print("-" * 50)
        for i, intro in enumerate(intros, 1):
            print(f"{i}. {intro}")
        
        while True:
            choice = input("\nEnter the number of the intro to use: ")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(intros):
                    selected_intro = intros[idx]
                    intro_path = os.path.abspath(os.path.join("introandoutro", selected_intro))
                    break
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
    
    # Set outro path
    outro_base = os.path.abspath(os.path.join("introandoutro", "mainoutro.mp4"))
    if not os.path.exists(outro_base):
        print(f"\nWarning: '{outro_base}' not found!")
        outro_path = None
    else:
        outro_path = outro_base
    
    # Ask for output filename
    while True:
        user_filename = input("\nEnter output filename (default: final.mp4): ").strip()
        if not user_filename:
            user_filename = "final.mp4"
        # Ensure .mp4 extension
        if not user_filename.lower().endswith('.mp4'):
            user_filename += ".mp4"
        # Prevent path traversal by taking only the basename
        user_filename = os.path.basename(user_filename)
        if user_filename:
            break
        print("Invalid filename, try again.")
        
    output_path = os.path.join(output_dir, user_filename)
    
    # Processing Variables
    temp_cut_file = f"temp_cut_{uuid.uuid4()}.mp4"
    concat_list_file = f"concat_list_{uuid.uuid4()}.txt"
    
    print("\n" + "=" * 50)
    print("Step 1: Trimming Main Video (Lossless)")
    print("=" * 50)
    
    try:
        # 1. Trim the main video first using Stream Copy
        # -ss before -i is crucial for fast seek
        # -to is used to specify end time relative to input if -ss is before -i? 
        # Actually with -ss before -i, timestamps reset to 0. So we need duration using -t
        duration = end_time - start_time
        
        trim_cmd = [
            FFMPEG_BINARY,
            '-y',
            '-ss', str(start_time),
            '-t', str(duration),
            '-i', recording_path,
            '-c', 'copy',
            temp_cut_file
        ]
        
        print(f"Trimming '{selected_recording}'...", end=" ", flush=True)
        subprocess.run(trim_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Done!")
        
        # 2. Create Concat List
        # We must use absolute paths for safety with the concat demuxer
        print("Step 2: Merging (Lossless)...")
        
        temp_cut_abs = os.path.abspath(temp_cut_file)
        
        with open(concat_list_file, 'w', encoding='utf-8') as f:
            if intro_path:
                f.write(f"file '{intro_path}'\n")
            f.write(f"file '{temp_cut_abs}'\n")
            if outro_path:
                f.write(f"file '{outro_path}'\n")
        
        # 3. Concatenate using Stream Copy
        concat_cmd = [
            FFMPEG_BINARY,
            '-y',
            '-f', 'concat',
            '-safe', '0', # Allow unsafe file paths (absolute paths)
            '-i', concat_list_file,
            '-c', 'copy',
            output_path
        ]
        
        subprocess.run(concat_cmd, check=True)
        
        print("\n" + "=" * 50)
        print(f"SUCCESS! Video saved to: {output_path}")
        print("=" * 50)

    except subprocess.CalledProcessError as e:
        print(f"\nError: FFmpeg command failed with exit code {e.returncode}")
        print("NOTE: For Lossless mode, all videos (Intro, Recording, Outro) MUST have identical resolution and codecs.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        
    finally:
        # Cleanup temp files
        if os.path.exists(temp_cut_file):
            try: os.remove(temp_cut_file)
            except: pass
        if os.path.exists(concat_list_file):
            try: os.remove(concat_list_file)
            except: pass

if __name__ == "__main__":
    main()
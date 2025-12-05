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
    print("Video Editing Automation (Native FFmpeg Speed Logic)")
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
    
    recording_path = os.path.join("recordings", selected_recording)
    print(f"\nSelected: {selected_recording}")
    
    # Step 2: Get trim times
    print("\n" + "-" * 50)
    print("Enter trim times (format: MM:SS)")
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
                    intro_path = os.path.join("introandoutro", selected_intro)
                    break
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
    
    # Set outro path
    outro_path = os.path.join("introandoutro", "mainoutro.mp4")
    if not os.path.exists(outro_path):
        print(f"\nWarning: '{outro_path}' not found!")
        outro_path = None
    
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
    
    # Step 4: Construct FFmpeg Command
    print("\n" + "=" * 50)
    print("Processing video with Native FFmpeg Engine...")
    print("=" * 50)
    
    # Inputs list for the command
    inputs = []
    filter_parts = []
    input_idx = 0
    
    # 1. Intro (optional)
    if intro_path:
        inputs.extend(['-i', intro_path])
        filter_parts.append(f"[{input_idx}:v] [{input_idx}:a]")
        input_idx += 1
        
    # 2. Main Recording (with trimming)
    # We use -ss (seek) BEFORE -i for fast seeking, and -to for duration
    # Note: When using -ss before -i, -to implies duration relative to 0 of the *trimmed* clip usually,
    # but strictly it's safer to use -ss and -t (duration) or just handle the calculation.
    # Actually, simpler is: -ss start -to end -i file -> NO, that's not how ffmpeg works perfectly with fast seek.
    # Robust way: -ss start -i file -to (end-start) -copyts ...
    # Let's stick to standard accurate seek: -ss start -to end -i ... is slow?
    # FAST SEEK: -ss start -i file ...
    # But then timestamps reset.
    # BEST APPROACH: -ss start -t duration -i file
    
    duration = end_time - start_time
    
    # Note: we need to cast times to strings
    inputs.extend(['-ss', str(start_time), '-t', str(duration), '-i', recording_path])
    filter_parts.append(f"[{input_idx}:v] [{input_idx}:a]")
    input_idx += 1
    
    # 3. Outro (optional)
    if outro_path:
        inputs.extend(['-i', outro_path])
        filter_parts.append(f"[{input_idx}:v] [{input_idx}:a]")
        input_idx += 1
        
    # Construct Filter Complex for Concat
    # Format: [0:v] [0:a] [1:v] [1:a] ... concat=n=N:v=1:a=1 [v] [a]
    filter_str = "".join(filter_parts) + f"concat=n={input_idx}:v=1:a=1 [v] [a]"
    
    cmd = [
        FFMPEG_BINARY,
        '-y', # Overwrite output
    ]
    
    # Add all inputs
    cmd.extend(inputs)
    
    # Add filter complex
    cmd.extend(['-filter_complex', filter_str])
    
    # Add map to map the filter outputs to the final file
    cmd.extend(['-map', '[v]', '-map', '[a]'])
    
    # Encoding options for Speed
    cmd.extend([
        '-c:v', 'libx264',
        '-preset', 'ultrafast', # Max speed
        '-crf', '23', # Standard quality
        '-c:a', 'aac',
        '-b:a', '192k',
        output_path
    ])
    
    display_cmd = " ".join(cmd)
    # print(f"\nDebug: Executing command:\n{display_cmd}\n")
    
    print("Running FFmpeg subprocess... Please wait.")
    
    try:
        # Run subprocess
        subprocess.run(cmd, check=True)
        
        print("\n" + "=" * 50)
        print(f"SUCCESS! Video saved to: {output_path}")
        print("=" * 50)
        
    except subprocess.CalledProcessError as e:
        print(f"\nError: FFmpeg command failed with exit code {e.returncode}")
        print("Ensure input files have compatible streams (resolution/frame rate).")
    except KeyboardInterrupt:
        print("\nProcess cancelled by user.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
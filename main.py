import os
import concurrent.futures
from functools import partial
from moviepy import VideoFileClip, concatenate_videoclips

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
    print("Video Editing Automation")
    print("=" * 50)

    # Create output directory if it doesn't exist
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: List and select recording
    recordings = list_recordings()
    if not recordings:
        print("No recordings found!")
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
    if not intros:
        print("\nWarning: No intro videos found!")
        intro_path = None
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

    # Step 4: Process video
    print("\n" + "=" * 50)
    print("Processing video... This may take a few minutes.")
    print("=" * 50)

    try:
        # Prepare functions for threaded loading
        def load_clip(path, subclip=None):
            clip = VideoFileClip(path)
            if subclip is not None:
                start, end = subclip
                clip = clip.subclipped(start, end)
            # Touch some metadata to force eager probing while thread is active
            _ = (clip.duration, clip.fps)
            return clip

        clips_to_concat = []
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit main recording load+trim
            futures.append(executor.submit(load_clip, recording_path, (start_time, end_time)))
            # Submit intro if present
            if 'intro_path' in locals() and intro_path:
                futures.append(executor.submit(load_clip, intro_path))
            # Submit outro if present
            if outro_path:
                futures.append(executor.submit(load_clip, outro_path))

            # Collect in desired order: intro, main, outro
            # Map paths to futures to manage ordering
            future_map = {f: 'main' for f in futures}
            # Rebuild explicit futures for ordering
            fut_intro = None
            fut_main = None
            fut_outro = None
            for f in futures:
                args = f.args if hasattr(f, 'args') else None
            # Instead, keep references explicitly
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _noop:
                pass

        # The above "args" approach isn't reliable; resubmit with explicit handles
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            fut_main = executor.submit(load_clip, recording_path, (start_time, end_time))
            fut_intro = executor.submit(load_clip, intro_path) if ('intro_path' in locals() and intro_path) else None
            fut_outro = executor.submit(load_clip, outro_path) if outro_path else None

            intro_clip = fut_intro.result() if fut_intro else None
            main_clip = fut_main.result()
            outro_clip = fut_outro.result() if fut_outro else None

        if intro_clip:
            print("2. Adding intro...")
            clips_to_concat.append(intro_clip)

        print("1. Loading and trimming main recording...")
        clips_to_concat.append(main_clip)

        if outro_clip:
            print("3. Adding outro...")
            clips_to_concat.append(outro_clip)

        # Concatenate all clips
        print("4. Combining all clips...")
        final_clip = concatenate_videoclips(clips_to_concat)

        # Ask for output filename
        while True:
            user_filename = input("Enter output filename (default: final.mp4): ").strip()
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

        # Export with multi-threaded ffmpeg settings
        output_path = os.path.join(output_dir, user_filename)
        print(f"5. Exporting to {output_path}...")
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            threads=os.cpu_count() or 4,
            preset='faster'
        )

        # Clean up
        print("6. Cleaning up...")
        if intro_clip:
            intro_clip.close()
        main_clip.close()
        if outro_clip:
            outro_clip.close()
        final_clip.close()

        print("\n" + "=" * 50)
        print(f"SUCCESS! Video saved to: {output_path}")
        print("=" * 50)

    except Exception as e:
        print(f"\nError processing video: {e}")
        print("Make sure all video files exist and are valid MP4 files.")

if __name__ == "__main__":
    main()
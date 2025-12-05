import os
import uuid
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
    print("Video Editing Automation (Optimized)")
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
    intro_path = None
    if not intros:
        print("\nWarning: No intro videos found!")
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
    print("Processing video... (Optimized Mode)")
    print("=" * 50)
    
    # Initialize clips to None for safe cleanup
    main_clip = None
    intro_clip = None
    outro_clip = None
    final_clip = None
    
    try:
        # Load and trim main recording
        print("\n1. Loading and trimming main recording...")
        main_clip = VideoFileClip(recording_path).subclipped(start_time, end_time)
        
        clips_to_concat = []
        
        # Add intro
        if intro_path:
            print("2. Adding intro...")
            intro_clip = VideoFileClip(intro_path)
            clips_to_concat.append(intro_clip)
        
        # Add main content
        clips_to_concat.append(main_clip)
        
        # Add outro
        if outro_path:
            print("3. Adding outro...")
            outro_clip = VideoFileClip(outro_path)
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
        
        # Export
        output_path = os.path.join(output_dir, user_filename)
        print(f"5. Exporting to {output_path}...")
        
        # Use a unique temp audio file to prevent conflicts
        temp_audio = f"temp-audio-{uuid.uuid4()}.m4a"
        
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=temp_audio,
            remove_temp=True,
            preset='ultrafast',  # Much faster encoding
            threads=8  # Use multiple threads
        )
        
        print("\n" + "=" * 50)
        print(f"SUCCESS! Video saved to: {output_path}")
        print("=" * 50)
        
    except Exception as e:
        print(f"\nError processing video: {e}")
        print("Make sure all video files exist and are valid MP4 files.")
        
    finally:
        # robust cleanup
        print("\nCleaning up resources...")
        try:
            if main_clip: main_clip.close()
        except: pass
        
        try:
            if intro_clip: intro_clip.close()
        except: pass
            
        try:
            if outro_clip: outro_clip.close()
        except: pass
            
        try:
            if final_clip: final_clip.close()
        except: pass

if __name__ == "__main__":
    main()
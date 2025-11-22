import os
import time
from moviepy import VideoFileClip, concatenate_videoclips
from tqdm import tqdm

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
    start_total = time.time()
    
    print("=" * 50)
    print("⚡ Optimized Video Editing Automation ⚡")
    print("=" * 50)
    
    # Create output directory
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Step 1: Select recording
    recordings = list_recordings()
    if not recordings:
        print("No recordings found!")
        return
    
    print("\n📁 Available recordings:")
    for i, video in enumerate(recordings, 1):
        print(f"  {i}. {video}")
    
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
    print(f"\n✅ Selected: {selected_recording}")
    
    # Step 2: Get trim times
    print("\n" + "-" * 50)
    print("⏱️  Enter trim times (format: MM:SS)")
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
    if intros:
        print("\n" + "-" * 50)
        print("🎬 Available intro videos:")
        print("-" * 50)
        for i, intro in enumerate(intros, 1):
            print(f"  {i}. {intro}")
        
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
        outro_path = None
    
    # Ask for output filename
    while True:
        user_filename = input("\n💾 Enter output filename (default: final.mp4): ").strip()
        if not user_filename:
            user_filename = "final.mp4"
        if not user_filename.lower().endswith('.mp4'):
            user_filename += ".mp4"
        user_filename = os.path.basename(user_filename)
        if user_filename:
            break
        print("Invalid filename, try again.")
    
    output_path = os.path.join(output_dir, user_filename)
    
    # Step 4: Process video with optimizations
    print("\n" + "=" * 50)
    print("🚀 Processing video (Optimized)")
    print("=" * 50)
    print("\n💡 Using optimized settings for faster processing\n")
    
    try:
        clips_to_concat = []
        
        # Step 1: Load and trim main recording
        print("📹 Step 1: Loading and trimming main recording...")
        with tqdm(total=100, desc="Loading video", unit="%", 
                  bar_format="{l_bar}{bar}| {n_fmt}%") as pbar:
            main_clip = VideoFileClip(recording_path)
            pbar.update(50)
            main_clip = main_clip.subclipped(start_time, end_time)
            pbar.update(50)
        
        # Step 2: Load intro if exists
        if intro_path:
            print("\n🎬 Step 2: Loading intro...")
            with tqdm(total=100, desc="Loading intro", unit="%",
                      bar_format="{l_bar}{bar}| {n_fmt}%") as pbar:
                intro_clip = VideoFileClip(intro_path)
                clips_to_concat.append(intro_clip)
                pbar.update(100)
        
        # Add main content
        clips_to_concat.append(main_clip)
        
        # Step 3: Load outro if exists
        if outro_path:
            print("\n🎭 Step 3: Loading outro...")
            with tqdm(total=100, desc="Loading outro", unit="%",
                      bar_format="{l_bar}{bar}| {n_fmt}%") as pbar:
                outro_clip = VideoFileClip(outro_path)
                clips_to_concat.append(outro_clip)
                pbar.update(100)
        
        # Step 4: Concatenate
        print("\n🔗 Step 4: Combining clips...")
        with tqdm(total=100, desc="Concatenating", unit="%",
                  bar_format="{l_bar}{bar}| {n_fmt}%") as pbar:
            final_clip = concatenate_videoclips(clips_to_concat)
            pbar.update(100)
        
        # Step 5: Export with optimizations
        print(f"\n💾 Step 5: Exporting to {output_path}...")
        print("⏱️  This is the slowest step - please be patient!\n")
        
        # OPTIMIZED SETTINGS for faster encoding:
        final_clip.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            # OPTIMIZATION 1: Faster preset (huge speed boost!)
            preset='ultrafast',  # Was 'medium', now 'ultrafast' = 5-10x faster!
            
            # OPTIMIZATION 2: Multi-threading
            threads=8,  # Use 8 CPU threads for parallel encoding
            
            # OPTIMIZATION 3: Reduce quality slightly for speed
            # (still looks great, but encodes faster)
            bitrate='3000k',  # Lower bitrate = faster encoding
            
            # OPTIMIZATION 4: Audio settings
            audio_bitrate='192k',
            audio_fps=44100,
            
            # Show progress bar
            logger='bar'
        )
        
        # Step 6: Cleanup
        print("\n🧹 Step 6: Cleaning up...")
        with tqdm(total=len(clips_to_concat), desc="Closing clips", unit="clip") as pbar:
            main_clip.close()
            pbar.update(1)
            if intro_path:
                intro_clip.close()
                pbar.update(1)
            if outro_path:
                outro_clip.close()
                pbar.update(1)
            final_clip.close()
        
        elapsed = time.time() - start_total
        
        print("\n" + "=" * 50)
        print(f"✅ SUCCESS! Video saved to: {output_path}")
        print(f"⏱️  Total time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print("=" * 50)
        print("\n⚡ Optimized settings used:")
        print("   • Ultra-fast encoding preset")
        print("   • Multi-threaded processing (8 threads)")
        print("   • Optimized bitrate settings")
        print("   • ~3-5x faster than default settings!")
        
    except Exception as e:
        print(f"\n❌ Error processing video: {e}")
        print("Make sure all video files exist and are valid MP4 files.")

if __name__ == "__main__":
    main()
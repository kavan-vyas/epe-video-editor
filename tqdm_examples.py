"""
tqdm Examples for Video Editing Project
Demonstrates various ways to use tqdm progress bars
"""

import time
from tqdm import tqdm, trange
from progress_helper import ProgressTracker, StepTracker


def example_1_basic_loop():
    """Example 1: Basic loop with tqdm"""
    print("\n" + "="*60)
    print("Example 1: Basic Loop with tqdm")
    print("="*60)
    
    print("Processing 50 items...")
    for i in tqdm(range(50), desc="Processing"):
        time.sleep(0.05)  # Simulate work


def example_2_trange():
    """Example 2: Using trange (tqdm range)"""
    print("\n" + "="*60)
    print("Example 2: Using trange")
    print("="*60)
    
    print("Processing with trange...")
    for i in trange(50, desc="trange example"):
        time.sleep(0.05)


def example_3_manual_updates():
    """Example 3: Manual progress updates"""
    print("\n" + "="*60)
    print("Example 3: Manual Progress Updates")
    print("="*60)
    
    print("Simulating video processing steps...")
    with tqdm(total=100, desc="Video Processing") as pbar:
        # Step 1: Load video
        pbar.set_description("Loading video")
        time.sleep(1)
        pbar.update(25)
        
        # Step 2: Trim video
        pbar.set_description("Trimming video")
        time.sleep(1)
        pbar.update(25)
        
        # Step 3: Add effects
        pbar.set_description("Adding effects")
        time.sleep(1)
        pbar.update(25)
        
        # Step 4: Export
        pbar.set_description("Exporting")
        time.sleep(1)
        pbar.update(25)


def example_4_nested_bars():
    """Example 4: Nested progress bars"""
    print("\n" + "="*60)
    print("Example 4: Nested Progress Bars")
    print("="*60)
    
    print("Processing multiple videos...")
    for i in tqdm(range(3), desc="Videos", position=0):
        for j in tqdm(range(20), desc=f"Video {i+1}", leave=False, position=1):
            time.sleep(0.02)


def example_5_colored_bars():
    """Example 5: Colored progress bars"""
    print("\n" + "="*60)
    print("Example 5: Colored Progress Bars")
    print("="*60)
    
    colors = ['green', 'blue', 'yellow', 'magenta', 'cyan']
    operations = ['Loading', 'Processing', 'Combining', 'Exporting', 'Cleanup']
    
    for color, operation in zip(colors, operations):
        with tqdm(total=100, desc=operation, colour=color) as pbar:
            for _ in range(10):
                time.sleep(0.05)
                pbar.update(10)


def example_6_progress_tracker():
    """Example 6: Using ProgressTracker helper"""
    print("\n" + "="*60)
    print("Example 6: Using ProgressTracker Helper")
    print("="*60)
    
    operations = [
        (100, "Loading video", "loading"),
        (100, "Trimming", "processing"),
        (100, "Adding intro", "processing"),
        (100, "Combining clips", "combining"),
        (100, "Exporting", "exporting"),
        (100, "Cleanup", "cleanup"),
    ]
    
    for total, desc, op_type in operations:
        with ProgressTracker.progress_bar(total, desc, op_type) as pbar:
            for _ in range(10):
                time.sleep(0.05)
                pbar.update(10)


def example_7_step_tracker():
    """Example 7: Using StepTracker for multi-step process"""
    print("\n" + "="*60)
    print("Example 7: Step Tracker for Multi-Step Process")
    print("="*60)
    
    steps = [
        "Selecting recording",
        "Setting trim times",
        "Selecting intro",
        "Loading clips",
        "Combining clips",
        "Exporting video",
        "Cleanup"
    ]
    
    with StepTracker(len(steps), "Video Editing") as tracker:
        for step in steps:
            tracker.next_step(step)
            time.sleep(0.5)


def example_8_unit_scale():
    """Example 8: Using unit_scale for file sizes"""
    print("\n" + "="*60)
    print("Example 8: Unit Scale (File Sizes)")
    print("="*60)
    
    # Simulate downloading a 100MB file
    total_bytes = 100 * 1024 * 1024  # 100MB
    
    with tqdm(total=total_bytes, unit='B', unit_scale=True, desc="Downloading") as pbar:
        for _ in range(100):
            pbar.update(1024 * 1024)  # Update by 1MB
            time.sleep(0.05)


def example_9_ascii_mode():
    """Example 9: ASCII mode for compatibility"""
    print("\n" + "="*60)
    print("Example 9: ASCII Mode (Terminal Compatibility)")
    print("="*60)
    
    print("Using ASCII characters for better compatibility...")
    with tqdm(total=100, desc="Processing", ascii=True) as pbar:
        for _ in range(10):
            time.sleep(0.1)
            pbar.update(10)


def example_10_disable_progress():
    """Example 10: Disabling progress bar"""
    print("\n" + "="*60)
    print("Example 10: Disabling Progress Bar")
    print("="*60)
    
    print("Progress bar is disabled (useful for batch processing)...")
    with tqdm(total=100, desc="Processing", disable=True) as pbar:
        for _ in range(10):
            time.sleep(0.05)
            pbar.update(10)
    print("Done! (No progress bar was shown)")


def example_11_postfix():
    """Example 11: Adding postfix information"""
    print("\n" + "="*60)
    print("Example 11: Postfix Information")
    print("="*60)
    
    print("Adding custom information to progress bar...")
    with tqdm(total=100, desc="Processing") as pbar:
        for i in range(10):
            time.sleep(0.1)
            pbar.update(10)
            pbar.set_postfix({'status': 'running', 'items': i+1})


def example_12_real_world_scenario():
    """Example 12: Real-world video editing scenario"""
    print("\n" + "="*60)
    print("Example 12: Real-World Video Editing Scenario")
    print("="*60)
    
    print("\nSimulating complete video editing workflow...\n")
    
    # Step 1: Load recording
    print("Step 1: Loading recording...")
    with tqdm(total=100, desc="Loading video", colour="green") as pbar:
        time.sleep(0.5)
        pbar.update(100)
    
    # Step 2: Load intro
    print("Step 2: Loading intro...")
    with tqdm(total=100, desc="Loading intro", colour="blue") as pbar:
        time.sleep(0.3)
        pbar.update(100)
    
    # Step 3: Load outro
    print("Step 3: Loading outro...")
    with tqdm(total=100, desc="Loading outro", colour="cyan") as pbar:
        time.sleep(0.3)
        pbar.update(100)
    
    # Step 4: Combine clips
    print("Step 4: Combining clips...")
    with tqdm(total=100, desc="Combining", colour="yellow") as pbar:
        time.sleep(0.5)
        pbar.update(100)
    
    # Step 5: Export video
    print("Step 5: Exporting video...")
    with tqdm(total=100, desc="Exporting", colour="magenta") as pbar:
        for _ in range(10):
            time.sleep(0.2)
            pbar.update(10)
    
    # Step 6: Cleanup
    print("Step 6: Cleanup...")
    with tqdm(total=100, desc="Cleanup", colour="red") as pbar:
        time.sleep(0.3)
        pbar.update(100)
    
    print("\n✓ Video editing complete!")


def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("tqdm Progress Bar Examples")
    print("="*60)
    
    examples = [
        ("Basic Loop", example_1_basic_loop),
        ("trange", example_2_trange),
        ("Manual Updates", example_3_manual_updates),
        ("Nested Bars", example_4_nested_bars),
        ("Colored Bars", example_5_colored_bars),
        ("ProgressTracker Helper", example_6_progress_tracker),
        ("StepTracker", example_7_step_tracker),
        ("Unit Scale", example_8_unit_scale),
        ("ASCII Mode", example_9_ascii_mode),
        ("Disable Progress", example_10_disable_progress),
        ("Postfix Info", example_11_postfix),
        ("Real-World Scenario", example_12_real_world_scenario),
    ]
    
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"{i}. {name}")
    
    print("\nRunning all examples...\n")
    
    for name, example_func in examples:
        try:
            example_func()
        except KeyboardInterrupt:
            print("\n\nSkipped!")
            continue
    
    print("\n" + "="*60)
    print("All examples completed!")
    print("="*60)


if __name__ == "__main__":
    main()

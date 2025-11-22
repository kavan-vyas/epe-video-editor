# Video Compiler in Python

I've created a Python script that will be significantly faster than manual editing in Camtasia. This README preserves the original details and adds a complete, step-by-step guide to set up and use the repository successfully.

## Speed Comparison
- Camtasia: ~30 min conversion + ~60 min editing ≈ 90 minutes total
- This Python script: ~5–15 minutes (depends on video length and your computer specs)
- On my computer it ran quite well and it only took 7 minutes to run and output the file of length 1 hour.

## What This Tool Does
- Lets you pick a recording from the recordings folder
- Prompts you for start and end trim times (MM:SS) (and the MM part can be > 60)
- Lets you select an intro from introandoutro
- Automatically appends the main outro
- Asks you to name the output file (defaults to final.mp4)
- Exports the result to the output folder

## Requirements
- Python 3.9+ recommended
- ffmpeg (MoviePy uses it under the hood; usually auto-installed with MoviePy on most platforms, but you may need to install it manually if export fails)

## Installation
1. Install Python if you don’t already have it (macOS often has Python 3 preinstalled).
2. Install required Python packages:
   - macOS/Linux:
     - python3 -m pip install --upgrade pip
     - python3 -m pip install moviepy
   - Windows:
     - py -m pip install --upgrade pip
     - py -m pip install moviepy

If export fails with an ffmpeg error, install ffmpeg:
- macOS (Homebrew): brew install ffmpeg
- Windows (chocolatey): choco install ffmpeg
- Linux (Debian/Ubuntu): sudo apt-get update && sudo apt-get install -y ffmpeg

## Repository Structure
Your directory should look like this:

project_root/
├── main.py
├── recordings/
│   ├── maths.mp4
│   ├── english.mp4
│   └── reasoning.mp4
├── introandoutro/
│   ├── mathsintro.mp4
│   ├── englishintro.mp4
│   ├── reasoningintro.mp4
│   └── mainoutro.mp4
└── output/              # created automatically if missing

Notes:
- recordings contains your raw lesson recordings (MP4 files)
- introandoutro contains intro videos for each subject plus mainoutro.mp4
- output is where the final rendered video is saved

## Step-by-Step Guide: How to Use This Repo
1. Prepare your folders and files
   - Ensure these folders exist next to main.py: recordings and introandoutro
   - Place your raw recordings (e.g., maths.mp4, english.mp4, reasoning.mp4) into recordings/
   - Place your intro videos (e.g., mathsintro.mp4, englishintro.mp4, reasoningintro.mp4) and the outro video mainoutro.mp4 into introandoutro/
   - The script will create output/ automatically if it doesn’t exist

2. Start the program
     - On VS Code, click on Terminal on the top bar and create a new terminal
     - Enter the exact command: "python main.py"

3. Select the recording
   - The program lists all .mp4 files in recordings/
   - Enter the number corresponding to the video you want to edit

4. Enter trim times
   - Format: MM:SS (e.g., 02:30)
   - Start time: where the content should begin
   - End time: where the content should end (must be after the start time)

5. Choose an intro
   - The program lists all intro files (files containing “intro”) from introandoutro/
   - Enter the number corresponding to the intro you want to prepend

6. Name the output file
   - You’ll be asked to enter an output filename
   - Press Enter to accept the default final.mp4
   - If you omit .mp4, it will be added automatically
   - The file will be saved into output/

7. Wait for processing to complete
   - Rendering time depends on the length of the video and your hardware
   - When done, the program prints the full path to your exported file

## Features
- Interactive menu to select recordings
- Trim start and end of videos via MM:SS inputs
- Automatically adds selected intro and the main outro
- Prompts for output filename; defaults to final.mp4
- Exports to output/<your-filename>.mp4
- Error handling for missing folders/files

## Original Problem Statement (Preserved)
1 hour recording is recorded in Zoom every weekend; it takes around 30 mins for the recording to “convert”. Then it takes ~1 hour to edit the recording in Camtasia. Would a Python program for this same function be faster?

Project layout: A directory with main.py; a recordings folder containing maths.mp4, english.mp4, reasoning.mp4; and an introandoutro folder containing mathsintro.mp4, englishintro.mp4, reasoningintro.mp4, and mainoutro.mp4. The program should:
- Open the selected recording and ask for the filename to edit
- Ask for start and end times (minutes and seconds) to trim
- Ask which intro to prepend, automatically append the outro
- Create final.mp4 (or your chosen filename) in the output folder

## Tips and Best Practices
- Use consistent naming: Keep subject names aligned between recordings and intros (e.g., maths.mp4 and mathsintro.mp4)
- Check durations: Ensure your end time is after your start time
- Keep files as MP4: The script expects .mp4 files for intros, outos, and recordings
- Backups: Keep originals in case you want to re-export with different trims

## Troubleshooting
- No recordings found!
  - Ensure recordings/ exists and contains .mp4 files
- No intro videos found!
  - Ensure introandoutro/ exists and contains your intro files and mainoutro.mp4
- Export fails / ffmpeg not found
  - Install ffmpeg (see Installation section) and re-run the script
- Audio issues
  - Ensure your source files have valid audio tracks; the script exports with codec libx264 and audio aac
- Permission errors
  - Make sure you have write permissions to the output/ directory

## License
Personal/organizational use permitted. Add a LICENSE file if you need specific terms.

## Acknowledgments
- Built with Python and MoviePy
- Inspired by the need to reduce manual editing time by ~70+ minutes per video 🚀




--- 






# Notes taken:

## Iter 1:

MoviePy fix, the library works but it takes 7 mins on my macbook pro and takes more thamn 15 misn on my main deskstop computer, which I use for editing

Therefore I need to optimise this

## Iter 2:

Multithreading update/ try

Didnt really work kept on crashing

My hypothesis was that this uses 100% of the Deskstop's power 
and should speed things up.

## Iter 3:

I had fun and added tdqm actual rainbow loading bar

I eventually realised this was highly inefficient do I got rid of it:

## Iter 4:

 TBC... (To Be Continued)

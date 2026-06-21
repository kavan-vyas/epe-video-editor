"""Video Compiler — lossless, stream-copy intro + trimmed body + outro builder.

See pipeline.md for the full specification. Foundation: ffmpeg/ffprobe as a
subprocess engine (chosen over a hand-rolled MP4 muxer — see README).
"""

__version__ = "1.0.0"

# tqdm Quick Reference Guide

## Installation
```bash
pip install tqdm
```

## Basic Usage

### 1. Wrap a Loop
```python
from tqdm import tqdm

for item in tqdm(iterable):
    do_something(item)
```

### 2. Use trange (tqdm range)
```python
from tqdm import trange

for i in trange(100):
    do_something(i)
```

### 3. Manual Updates
```python
from tqdm import tqdm

with tqdm(total=100) as pbar:
    for i in range(10):
        do_something()
        pbar.update(10)
```

## Common Parameters

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `desc` | Description | `desc="Loading"` |
| `total` | Total iterations | `total=100` |
| `unit` | Unit name | `unit="items"` |
| `colour` | Bar color | `colour="green"` |
| `leave` | Keep after done | `leave=True` |
| `ascii` | ASCII chars | `ascii=True` |
| `unit_scale` | Auto-scale units | `unit_scale=True` |
| `dynamic_ncols` | Auto width | `dynamic_ncols=True` |
| `disable` | Hide bar | `disable=True` |
| `position` | Bar position | `position=0` |

## Color Options
- `green`, `blue`, `yellow`, `magenta`, `cyan`, `red`, `white`, `grey`

## Common Patterns

### Pattern 1: Simple Loop
```python
from tqdm import tqdm

for i in tqdm(range(100), desc="Processing"):
    time.sleep(0.1)
```

### Pattern 2: Context Manager (Recommended)
```python
from tqdm import tqdm

with tqdm(total=100, desc="Loading") as pbar:
    for i in range(10):
        pbar.update(10)
```

### Pattern 3: Nested Bars
```python
from tqdm import tqdm

for i in tqdm(range(5), desc="Outer"):
    for j in tqdm(range(100), desc="Inner", leave=False):
        pass
```

### Pattern 4: File Size Progress
```python
from tqdm import tqdm

with tqdm(total=file_size, unit='B', unit_scale=True) as pbar:
    for chunk in file:
        pbar.update(len(chunk))
```

### Pattern 5: Update Description
```python
from tqdm import tqdm

with tqdm(total=100) as pbar:
    pbar.set_description("Step 1")
    pbar.update(25)
    pbar.set_description("Step 2")
    pbar.update(25)
```

## In Your Video Project

### Before (No Progress)
```python
main_clip = VideoFileClip(recording_path).subclipped(start_time, end_time)
```

### After (With Progress)
```python
from tqdm import tqdm

with tqdm(total=100, desc="Loading video", colour="green") as pbar:
    main_clip = VideoFileClip(recording_path)
    pbar.update(50)
    main_clip = main_clip.subclipped(start_time, end_time)
    pbar.update(50)
```

## Using Helper Module

```python
from progress_helper import ProgressTracker, StepTracker

# Method 1: Simple progress bar
with ProgressTracker.progress_bar(100, "Loading", "loading") as pbar:
    pbar.update(100)

# Method 2: Step tracking
with StepTracker(5, "Video Editing") as tracker:
    tracker.next_step("Loading")
    tracker.next_step("Processing")
```

## Tips & Tricks

1. **Always use context manager** (`with` statement) for automatic cleanup
2. **Set meaningful descriptions** so users know what's happening
3. **Use `leave=False`** for sub-tasks to avoid clutter
4. **Use `unit_scale=True`** for file sizes (B, KB, MB, GB)
5. **Use `dynamic_ncols=True`** for responsive width
6. **Disable in batch mode** to avoid cluttering logs

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bar not showing | Check if output is redirected |
| Broken characters | Use `ascii=True` |
| Overlapping bars | Use `position` parameter |
| Too many updates | Update less frequently |

## Files in Your Project

1. **main.py** - Updated with tqdm integration
2. **progress_helper.py** - Helper module with utilities
3. **tqdm_examples.py** - 12 working examples
4. **IMPLEMENTATION.md** - Detailed guide
5. **QUICK_REFERENCE.md** - This file

## Run Examples

```bash
python tqdm_examples.py
```

## Resources

- GitHub: https://github.com/tqdm/tqdm
- Docs: https://tqdm.github.io/
- PyPI: https://pypi.org/project/tqdm/

## Next Steps

1. ✅ Install tqdm: `pip install tqdm`
2. ✅ Run examples: `python tqdm_examples.py`
3. ✅ Update your code: Use patterns from QUICK_REFERENCE
4. ✅ Test your app: `python main.py`
5. ✅ Customize colors and descriptions as needed

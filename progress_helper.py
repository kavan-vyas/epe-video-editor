"""
Progress Helper Module
Provides utility functions for progress tracking with tqdm
"""

from tqdm import tqdm
from contextlib import contextmanager
from typing import Optional, Generator


class ProgressTracker:
    """
    A helper class for managing progress bars throughout the application.
    Provides consistent styling and easy progress updates.
    """
    
    # Color scheme for different operations
    COLORS = {
        'loading': 'green',
        'processing': 'blue',
        'combining': 'yellow',
        'exporting': 'magenta',
        'cleanup': 'red',
        'default': 'cyan'
    }
    
    @staticmethod
    @contextmanager
    def progress_bar(
        total: int = 100,
        desc: str = "Processing",
        operation_type: str = "default",
        unit: str = "%"
    ) -> Generator:
        """
        Context manager for creating a progress bar with consistent styling.
        
        Args:
            total: Total number of iterations
            desc: Description of the operation
            operation_type: Type of operation (determines color)
            unit: Unit of measurement
            
        Yields:
            tqdm progress bar object
            
        Example:
            with ProgressTracker.progress_bar(100, "Loading video", "loading") as pbar:
                for i in range(10):
                    pbar.update(10)
        """
        colour = ProgressTracker.COLORS.get(operation_type, ProgressTracker.COLORS['default'])
        
        with tqdm(
            total=total,
            desc=desc,
            unit=unit,
            colour=colour,
            dynamic_ncols=True,
            leave=True
        ) as pbar:
            yield pbar
    
    @staticmethod
    def simple_progress(
        total: int = 100,
        desc: str = "Processing",
        operation_type: str = "default"
    ) -> tqdm:
        """
        Create a simple progress bar without context manager.
        Remember to call .close() when done!
        
        Args:
            total: Total number of iterations
            desc: Description of the operation
            operation_type: Type of operation (determines color)
            
        Returns:
            tqdm progress bar object
            
        Example:
            pbar = ProgressTracker.simple_progress(100, "Loading")
            pbar.update(50)
            pbar.close()
        """
        colour = ProgressTracker.COLORS.get(operation_type, ProgressTracker.COLORS['default'])
        
        return tqdm(
            total=total,
            desc=desc,
            unit="%",
            colour=colour,
            dynamic_ncols=True,
            leave=True
        )
    
    @staticmethod
    def update_progress(pbar: tqdm, amount: int = 1) -> None:
        """
        Update progress bar by a specific amount.
        
        Args:
            pbar: tqdm progress bar object
            amount: Amount to increment by
        """
        pbar.update(amount)
    
    @staticmethod
    def set_description(pbar: tqdm, desc: str) -> None:
        """
        Update the description of a progress bar.
        
        Args:
            pbar: tqdm progress bar object
            desc: New description
        """
        pbar.set_description(desc)


class StepTracker:
    """
    Tracks multiple steps in a process with overall progress.
    Useful for multi-step operations like video editing.
    """
    
    def __init__(self, total_steps: int, title: str = "Processing"):
        """
        Initialize step tracker.
        
        Args:
            total_steps: Total number of steps
            title: Title of the overall process
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.title = title
        self.pbar = tqdm(
            total=total_steps,
            desc=title,
            unit="step",
            colour="cyan",
            dynamic_ncols=True,
            leave=True
        )
    
    def next_step(self, step_name: str) -> None:
        """
        Move to the next step and update progress bar.
        
        Args:
            step_name: Name of the current step
        """
        self.current_step += 1
        self.pbar.set_description(f"{self.title} - {step_name}")
        self.pbar.update(1)
    
    def close(self) -> None:
        """Close the progress bar."""
        self.pbar.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def create_nested_progress(
    outer_total: int,
    outer_desc: str = "Main Task",
    inner_total: int = 100,
    inner_desc: str = "Sub-task"
) -> tuple:
    """
    Create nested progress bars for complex operations.
    
    Args:
        outer_total: Total iterations for outer loop
        outer_desc: Description for outer progress bar
        inner_total: Total iterations for inner loop
        inner_desc: Description for inner progress bar
        
    Returns:
        Tuple of (outer_pbar, inner_pbar)
        
    Example:
        outer, inner = create_nested_progress(5, "Main", 100, "Sub")
        for i in range(5):
            for j in range(100):
                inner.update(1)
            outer.update(1)
        outer.close()
        inner.close()
    """
    outer_pbar = tqdm(
        total=outer_total,
        desc=outer_desc,
        unit="item",
        colour="green",
        dynamic_ncols=True,
        position=0
    )
    
    inner_pbar = tqdm(
        total=inner_total,
        desc=inner_desc,
        unit="%",
        colour="blue",
        dynamic_ncols=True,
        position=1,
        leave=False
    )
    
    return outer_pbar, inner_pbar


# Example usage functions
def example_basic_progress():
    """Example: Basic progress bar usage"""
    print("Example 1: Basic Progress Bar")
    with ProgressTracker.progress_bar(100, "Loading data", "loading") as pbar:
        for i in range(10):
            pbar.update(10)
    print("Done!\n")


def example_step_tracking():
    """Example: Step tracking for multi-step process"""
    print("Example 2: Step Tracking")
    steps = ["Loading", "Processing", "Combining", "Exporting", "Cleanup"]
    
    with StepTracker(len(steps), "Video Editing") as tracker:
        for step in steps:
            tracker.next_step(step)
    print("Done!\n")


def example_custom_colors():
    """Example: Using different colors for different operations"""
    print("Example 3: Custom Colors")
    operations = [
        (100, "Loading video", "loading"),
        (100, "Processing", "processing"),
        (100, "Combining", "combining"),
        (100, "Exporting", "exporting"),
    ]
    
    for total, desc, op_type in operations:
        with ProgressTracker.progress_bar(total, desc, op_type) as pbar:
            for i in range(10):
                pbar.update(10)
    print("Done!\n")


if __name__ == "__main__":
    # Run examples
    example_basic_progress()
    example_step_tracking()
    example_custom_colors()

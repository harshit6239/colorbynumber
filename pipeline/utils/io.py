import cv2
import numpy as np
from pathlib import Path


def load_image(path: str) -> np.ndarray:
    """Load an image from disk as a BGR numpy array. Raises if not found."""
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Could not load image: {path}")
    return img


def save_image(path: str, img: np.ndarray) -> None:
    """Save a BGR numpy array to disk, creating parent directories as needed."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(path, img)

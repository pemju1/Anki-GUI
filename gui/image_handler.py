import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import Libary.image_search as image_search
import requests
from PIL import Image, ImageTk, ImageGrab
import io
import os

# Constants (can be adjusted or moved to config later if needed)
COUNT_PER_SOURCE = 5 # Number Images per source
MEANINGS_PER_SOURCE = 3

# --- Image Fetching and Handling Functions ---

def search_online_images(query):
    """Searches for online images using the library."""
    print(f"Searching online images for: {query}")
    try:
        # Use constants defined in this module
        image_results = image_search.search_images(query, count_per_source=COUNT_PER_SOURCE, num_meanings_per_source=MEANINGS_PER_SOURCE)
        return image_results # List of (thumb_url, full_url)
    except Exception as e:
        print(f"Error fetching online images: {e}")
        messagebox.showerror("Image Search Error", f"Could not fetch online images:\n{e}")
        return []

def download_image_data(url, timeout=10):
    """Downloads image data from a URL."""
    try:
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error downloading image {url}: {e}")
        return None

def create_thumbnail(image_data, height=100):
    """Creates a thumbnail PhotoImage from image data."""
    if not image_data:
        return None
    try:
        img = Image.open(io.BytesIO(image_data))
        # Handle potential division by zero if image height is 0
        if img.height == 0:
            return None # Skip this image
        ratio = height / img.height
        thumb_width = int(img.width * ratio)
        img_resized = img.resize((thumb_width, height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img_resized)
        return photo
    except Exception as e:
        print(f"Error creating thumbnail: {e}")
        return None

def browse_local_image():
    """Opens file dialog to select a local image.
    Returns the selected filepath or None if cancelled.
    """
    filepath = filedialog.askopenfilename(
        title="Select an Image File",
        filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif"), ("All Files", "*.*")]
    )
    if not filepath:
        return None # User cancelled

    # Basic validation (can be expanded)
    try:
        img = Image.open(filepath)
        img.verify() # Check if it's a valid image file without loading full data
        print(f"Selected local file: {filepath}")
        return filepath
    except (FileNotFoundError, IOError, SyntaxError) as e:
        messagebox.showerror("Image Error", f"Could not open or read image file:\n{filepath}\n\nError: {e}")
        return None
    except Exception as e:
         messagebox.showerror("Image Error", f"An unexpected error occurred opening the image:\n{e}")
         return None

def get_image_from_clipboard():
    """
    Attempts to get an image from the clipboard.
    Returns a PIL Image object if successful, None otherwise.
    """
    try:
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            print("Pasted image from clipboard.")
            return img.copy() # Return a copy
        else:
            # print("No image found on clipboard.")
            # messagebox.showinfo("Clipboard", "No image found on the clipboard.") # UI feedback should be in main_window
            return None
    except Exception as e:
        # tkinter TclError can sometimes happen
        if "CLIPBOARD" in str(e).upper():
             # messagebox.showinfo("Clipboard", "Could not access clipboard or no image found.") # UI feedback in main_window
             print("Could not access clipboard or no image found.")
        else:
            # messagebox.showerror("Clipboard Error", f"Error pasting image: {e}") # UI feedback in main_window
            print(f"Error pasting from clipboard: {e}")
        return None

def create_preview_thumbnail(img_object: Image.Image, height=100):
    """Creates a thumbnail PhotoImage directly from a PIL Image object."""
    if not img_object:
        return None
    try:
        # Resize for preview
        ratio = height / img_object.height
        thumb_width = int(img_object.width * ratio)
        img_resized = img_object.resize((thumb_width, height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img_resized)
        return photo
    except Exception as e:
        print(f"Error creating preview thumbnail: {e}")
        return None

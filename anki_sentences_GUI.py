import re
import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import Libary.get_anki_data as get_anki_data
import Libary.sentance_ai as sentence
import Libary.generate_audio as TTS
import Libary.image_search as image_search
import pykakasi
import requests
from PIL import Image, ImageTk, ImageGrab # Added ImageGrab
import io
import base64
import os
import threading
import time
import json # Import json for config file

# Configuration
ANKI_CONNECT_URL = "http://localhost:8765"
OLLAMA_API_URL = "http://localhost:11434" # Base URL for Ollama API checks
CONFIG_FILE = "anki_gui_config.json"
COUNT_PER_SOURCE = 5 # Number Images per source
MEANINGS_PER_SOURCE = 3
STATUS_CHECK_INTERVAL = 10000 # Milliseconds (10 seconds) for connection checks

def generate_furigana_html(sentence_str: str) -> str:
    kks = pykakasi.kakasi()
    result = kks.convert(sentence_str)
    output = ""
    for token in result:
        orig = token["orig"]
        hira = token["hira"]
        # If there are Kanji characters and the reading differs, add ruby markup.
        if any('\u4e00' <= c <= '\u9fff' for c in orig) and orig != hira:
            output += f"<ruby>{orig}<rt>{hira}</rt></ruby>"
        else:
            output += orig
    return output

def generate_furigana_string(sentence_str: str) -> str:
    kks = pykakasi.kakasi()
    result = kks.convert(sentence_str)
    output = ""
    for token in result:
        orig = token["orig"]
        hira = token["hira"]
        # If there are Kanji characters and the reading differs, add ruby markup.
        if any('\u4e00' <= c <= '\u9fff' for c in orig) and orig != hira:
            output += f"{orig}({hira}) "
        else:
            output += orig
    return output

class AnkiGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anki Sentence & TTS Generator")
        # Load configuration first
        config = self.load_config()
        default_deck = config.get("deck", "") # Get saved deck or empty string
        default_model = config.get("ollama_model", "") # Get saved model or empty string

        self.selected_deck = tk.StringVar(value=default_deck)
        self.notes = []
        self.current_index = 0

        # Variables for dynamic lists
        self.available_decks = []
        self.available_models = []

        # Model selection variable
        self.selected_model = tk.StringVar(value=default_model)

        # Dictionary to store generated sentences for each note (by note id).
        # Format: { note_id: (jp1, en1, jp2, en2) }
        self.generated_sentences = {}

        # Variables for the current note's word and meaning.
        self.current_word = ""
        self.current_meaning = ""

        # Variables for the current displayed sentences.
        self.sentence1_jp = ""
        self.sentence1_en = ""
        self.sentence2_jp = ""
        self.sentence2_en = ""

        # Variables for the keep checkboxes.
        self.keep_var1 = tk.BooleanVar(value=False)
        self.keep_var2 = tk.BooleanVar(value=False)

        # Variables/widgets for image display and selection
        self.image_results = [] # Stores (thumb_url, full_url)
        self.image_widgets = [] # Stores (label_widget, source_info) - source_info can be full_url, file_path, or None for clipboard
        self.selected_image_label = None # Stores the label widget of the selected image
        # Image source tracking
        self.image_source = None # Can be 'online', 'local', 'clipboard', or None
        self.selected_image_url = None # Stores the full_url if source is 'online'
        self.selected_local_image_path = None # Stores file path if source is 'local'
        self.pasted_image_object = None # Stores PIL Image object if source is 'clipboard'

        # Lock for thread-safe Anki updates if needed (optional for now)
        # self.anki_update_lock = threading.Lock()

        self.create_widgets()
        self.update_deck_list() # Populate decks initially
        self.update_model_list() # Populate models initially

        # Set initial selection after lists are populated
        if default_deck and default_deck in self.available_decks:
            self.selected_deck.set(default_deck)
        elif self.available_decks:
             self.selected_deck.set(self.available_decks[0]) # Fallback to first deck

        if default_model and default_model in self.available_models:
            self.selected_model.set(default_model)
        elif self.available_models:
            self.selected_model.set(self.available_models[0]) # Fallback to first model

        # Start periodic connection checks
        self.check_anki_connection()
        self.check_ollama_connection()


    def create_widgets(self):
        # --- Top Bar Frame (Container for Rows) ---
        top_bar_frame = tk.Frame(self)
        top_bar_frame.pack(pady=5, padx=10, fill=tk.X)

        # --- Row 1: Anki Status and Deck Selection ---
        anki_row_frame = tk.Frame(top_bar_frame)
        anki_row_frame.pack(fill=tk.X, pady=(0, 5)) # Add padding below this row

        # Anki Status Indicator
        self.anki_status_label = tk.Label(anki_row_frame, text="Anki: Checking...", fg="orange", width=18, anchor="w")
        self.anki_status_label.pack(side=tk.LEFT, padx=(0, 10))

        # Deck selection frame
        deck_frame = tk.Frame(anki_row_frame)
        deck_frame.pack(side=tk.LEFT, padx=5)
        tk.Label(deck_frame, text="Deck:").pack(side=tk.LEFT)
        self.deck_menu = ttk.Combobox(deck_frame, textvariable=self.selected_deck,
                                      values=[], state="readonly", width=30) # Start empty
        self.deck_menu.pack(side=tk.LEFT, padx=5)
        tk.Button(deck_frame, text="🔄", command=self.update_deck_list).pack(side=tk.LEFT, padx=(0, 5)) # Refresh Deck List
        tk.Button(deck_frame, text="Load Deck", command=self.load_deck).pack(side=tk.LEFT)

        # --- Row 2: Ollama Status and Model Selection ---
        ollama_row_frame = tk.Frame(top_bar_frame)
        ollama_row_frame.pack(fill=tk.X)

        # Ollama Status Indicator
        self.ollama_status_label = tk.Label(ollama_row_frame, text="Ollama: Checking...", fg="orange", width=18, anchor="w")
        # Align Ollama status label with Anki status label using padding/empty label if needed, or just pack left
        self.ollama_status_label.pack(side=tk.LEFT, padx=(0, 10)) # Same padding as Anki status

        # Model selection frame
        model_frame = tk.Frame(ollama_row_frame)
        model_frame.pack(side=tk.LEFT, padx=5) # Same padding as deck frame
        tk.Label(model_frame, text="Model:").pack(side=tk.LEFT)
        self.model_menu = ttk.Combobox(model_frame, textvariable=self.selected_model,
                                       values=[], state="readonly", width=30) # Start empty
        self.model_menu.pack(side=tk.LEFT, padx=5)
        tk.Button(model_frame, text="🔄", command=self.update_model_list).pack(side=tk.LEFT) # Refresh Model List


        # Main frame for note details and sentence generation.
        self.note_display_frame = tk.Frame(self)
        self.note_display_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Image display area (using a scrolled text for potential overflow)
        image_area_frame = tk.LabelFrame(self, text="Image Selection", padx=5, pady=5)
        image_area_frame.pack(pady=10, padx=10, fill=tk.X, expand=False) # Fill horizontally, don't expand vertically

        # This frame will contain the actual image labels in a grid
        self.image_display_inner_frame = tk.Frame(image_area_frame)
        # Pack the inner frame directly into the LabelFrame
        self.image_display_inner_frame.pack(fill=tk.BOTH, expand=True)

        # Add buttons for local file and clipboard
        image_button_frame = tk.Frame(image_area_frame)
        image_button_frame.pack(pady=5)
        tk.Button(image_button_frame, text="Images from Web", command=self.display_images).pack(side=tk.LEFT, padx=10)
        tk.Button(image_button_frame, text="Browse Local File...", command=self.browse_for_image).pack(side=tk.LEFT, padx=10)
        tk.Button(image_button_frame, text="Paste from Clipboard", command=self.paste_image_from_clipboard).pack(side=tk.LEFT, padx=10)

        # Navigation frame.
        nav_frame = tk.Frame(self)
        nav_frame.pack(pady=10)
        tk.Button(nav_frame, text="Previous", command=self.show_prev_note).pack(side=tk.LEFT, padx=5)
        tk.Button(nav_frame, text="Next", command=self.show_next_note).pack(side=tk.LEFT, padx=5)
        tk.Button(nav_frame, text="Skip", command=self.skip_to_next_note).pack(side=tk.LEFT, padx=5)

        # Jump to note widgets
        tk.Label(nav_frame, text="Go to:").pack(side=tk.LEFT, padx=(15, 2)) # Add some left padding
        self.jump_entry = tk.Entry(nav_frame, width=5)
        self.jump_entry.pack(side=tk.LEFT)
        tk.Button(nav_frame, text="Go", command=self.jump_to_note).pack(side=tk.LEFT, padx=2)


        # Progress frame.
        progress_frame = tk.Frame(self)
        progress_frame.pack(pady=5, fill=tk.X, padx=10)
        self.progress_label = tk.Label(progress_frame, text="Note 0 of 0")
        self.progress_label.pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, padx=10)

    def load_deck(self):
        deck_name = self.selected_deck.get()
        if not deck_name:
            messagebox.showwarning("Warning", "Please select a deck first.")
            return
        try:
            deck_info = get_anki_data.get_deck_info(deck_name)
            self.notes = deck_info.get("allNotes", [])
            self.current_index = 0
            self.generated_sentences = {}  # Clear previously generated sentences.
            if not self.notes:
                messagebox.showinfo("Info", f"No notes found in the deck '{deck_name}'.")
                self.update_progress() # Update progress even if empty
            else:
                self.update_progress()
                self.display_current_note()
                # Save config after successfully loading a deck
                self.save_config()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load deck '{deck_name}':\n{e}")
            self.notes = [] # Ensure notes list is empty on error
            self.current_index = 0
            self.update_progress() # Update progress to show 0/0
            self.display_current_note() # Clear display area

    def update_progress(self):
        """Update progress bar and label."""
        total = len(self.notes)
        current = self.current_index + 1 if total > 0 else 0
        self.progress_label.config(text=f"Note {current} of {total}")
        self.progress_bar['maximum'] = total
        self.progress_bar['value'] = current

    def display_current_note(self, update_images=True):
        # Clear existing widgets.
        for widget in self.note_display_frame.winfo_children():
            widget.destroy()

        if not self.notes:
            return

        note = self.notes[self.current_index]
        note_id = note['noteId']

        # Extract word and meaning.
        word = note['fields'].get('Japanese', {}).get('value', '').strip()
        try:
            meaning = note['fields']["Meaning"]["value"]
            processed_meaning = meaning.replace("<br>", "\n")
        except KeyError:
            tk.Label(self.note_display_frame, text="Meaning field not found for this note.").pack()
            return

        self.current_word = word
        self.current_meaning = meaning

        # Display the word and meaning.
        tk.Label(self.note_display_frame, text=f"Word: {word}", font=("Helvetica", 14, "bold")).pack(anchor="w")
        tk.Label(self.note_display_frame, text=f"Meaning: {processed_meaning}", font=("Helvetica", 12)).pack(anchor="w", pady=(0,10))

        # Auto-generate sentences if not already generated.
        if note_id not in self.generated_sentences:
            self.generate_sentences()
            return  # generate_sentences() calls display_current_note() upon completion.

        # Retrieve stored sentences.
        self.sentence1_jp, self.sentence1_en, self.sentence2_jp, self.sentence2_en = self.generated_sentences[note_id]

        # Reset keep checkboxes.
        self.keep_var1.set(False)
        self.keep_var2.set(False)

        # Sentence 1 section.
        frame1 = tk.Frame(self.note_display_frame, bd=2, relief=tk.GROOVE, padx=5, pady=5)
        frame1.pack(fill=tk.X, pady=5)
        tk.Label(frame1, text="Sentence 1:", font=("Helvetica", 12, "bold")).pack(anchor="w")
        tk.Label(frame1, text=generate_furigana_string(self.sentence1_jp), wraplength=750, font=("Helvetica", 16)).pack(anchor="w", padx=10)
        tk.Label(frame1, text=f"Meaning: {self.sentence1_en}", fg="gray", wraplength=750).pack(anchor="w", padx=10)
        tk.Checkbutton(frame1, text="Keep", variable=self.keep_var1).pack(anchor="e")

        # Sentence 2 section.
        frame2 = tk.Frame(self.note_display_frame, bd=2, relief=tk.GROOVE, padx=5, pady=5)
        frame2.pack(fill=tk.X, pady=5)
        tk.Label(frame2, text="Sentence 2:", font=("Helvetica", 12, "bold")).pack(anchor="w")
        tk.Label(frame2, text=generate_furigana_string(self.sentence2_jp), wraplength=750, font=("Helvetica", 16)).pack(anchor="w", padx=10)
        tk.Label(frame2, text=f"Meaning: {self.sentence2_en}", fg="gray", wraplength=750).pack(anchor="w", padx=10)
        tk.Checkbutton(frame2, text="Keep", variable=self.keep_var2).pack(anchor="e")

        # Regenerate button.
        tk.Button(self.note_display_frame, text="Regenerate Unkept Sentences", command=self.regenerate_sentences).pack(pady=5) # Reduced padding

        # --- Image Display Logic ---
        # Display previously selected image if navigating back/forward, otherwise fetch online
        if update_images:
            self.display_images()

        # Update progress display.
        self.update_progress()

    def generate_sentences(self):
        """
        Generate sentences for the current note and store them.
        """
        selected_model = self.selected_model.get()
        if not selected_model:
             messagebox.showwarning("Warning", "Please select an Ollama model first.")
             return # Don't proceed if no model selected

        try:
            # Use only the selected model from the dropdown
            jp1, en1, jp2, en2 = sentence.ollama_sentances(self.current_word, self.current_meaning, selected_model)

        except Exception as e:
            messagebox.showerror("Error", f"Error generating sentences: {e}")
            return

        # Process and convert sentences to plain text.
        if jp1:
            plain_text1 = jp1
        else:
            plain_text1 = ""
        if jp2:
            plain_text2 = jp2
        else:
            plain_text2 = ""

        # Save the generated sentences.
        note_id = self.notes[self.current_index]['noteId']
        self.generated_sentences[note_id] = (plain_text1, en1, plain_text2, en2)
        # Re-display the note (now with generated sentences).
        self.display_current_note()

    def regenerate_sentences(self):
        """
        Regenerate sentences for the current note that are not kept.
        """
        selected_model = self.selected_model.get()
        if not selected_model:
             messagebox.showwarning("Warning", "Please select an Ollama model first.")
             return # Don't proceed if no model selected

        note_id = self.notes[self.current_index]['noteId']
        # Capture the current state of the keep checkboxes BEFORE regeneration.
        keep1_state = self.keep_var1.get()
        keep2_state = self.keep_var2.get()

        # Retrieve current stored sentences.
        current_jp1 = self.sentence1_jp
        current_en1 = self.sentence1_en
        current_jp2 = self.sentence2_jp
        current_en2 = self.sentence2_en

        try:
            # Use only the selected model from the dropdown
            new_jp1, new_en1, new_jp2, new_en2 = sentence.ollama_sentances(self.current_word, self.current_meaning, selected_model)

        except Exception as e:
            messagebox.showerror("Error", f"Error regenerating sentences: {e}")
            return

        # Update sentence 1 if not kept (using the captured state).
        if not keep1_state:
            if new_jp1:
                current_jp1 = new_jp1
            else:
                current_jp1 = ""
            current_en1 = new_en1

        # Update sentence 2 if not kept (using the captured state).
        if not keep2_state:
            if new_jp2:
                current_jp2 = new_jp2
            else:
                current_jp2 = ""
            current_en2 = new_en2

        # Store the updated sentences.
        self.generated_sentences[note_id] = (current_jp1, current_en1, current_jp2, current_en2)
        # Re-display the note (this will visually reset checkboxes initially).
        self.display_current_note(update_images=False)
        # Restore the checkbox state AFTER display_current_note has run.
        self.keep_var1.set(keep1_state)
        self.keep_var2.set(keep2_state)

    def _clear_image_selection_area(self):
        """Clears the image display area and resets selection variables."""
        for widget in self.image_display_inner_frame.winfo_children():
            widget.destroy()
        self.image_widgets = []
        self.selected_image_label = None
        self.image_source = None
        self.selected_image_url = None
        self.selected_local_image_path = None
        self.pasted_image_object = None
        # No canvas/scroll region to reset/configure anymore

    def _display_single_image_preview(self, img_object: Image.Image, source_info):
        """Displays a single image thumbnail in the cleared area."""
        self._clear_image_selection_area() # Clear first

        try:
            # Resize for preview
            thumb_height = 100
            ratio = thumb_height / img_object.height
            thumb_width = int(img_object.width * ratio)
            img_resized = img_object.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img_resized)
            img_label = tk.Label(self.image_display_inner_frame, image=photo, bd=2, relief=tk.SUNKEN, bg="lightblue") # Pre-select it
            img_label.image = photo # Keep reference
            # Place in grid (row 0, col 0 for single preview)
            img_label.grid(row=0, column=0, padx=5, pady=5)

            # Store widget and select it
            self.image_widgets.append((img_label, source_info))
            self.selected_image_label = img_label

            # Update layout
            self.update_idletasks()

        except Exception as e:
            print(f"Error displaying single image preview: {e}")
            tk.Label(self.image_display_inner_frame, text="Error displaying image.").pack()


    def browse_for_image(self):
        """Opens file dialog to select a local image."""
        filepath = filedialog.askopenfilename(
            title="Select an Image File",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif"), ("All Files", "*.*")]
        )
        if not filepath:
            return # User cancelled

        try:
            img = Image.open(filepath)
            img.verify() # Check if it's a valid image file without loading full data
            img = Image.open(filepath) # Re-open after verify
            img.load() # Load image data

            self._display_single_image_preview(img, filepath)
            self.image_source = 'local'
            self.selected_local_image_path = filepath
            print(f"Selected local file: {filepath}")

        except (FileNotFoundError, IOError, SyntaxError) as e:
            messagebox.showerror("Image Error", f"Could not open or read image file:\n{filepath}\n\nError: {e}")
        except Exception as e:
             messagebox.showerror("Image Error", f"An unexpected error occurred opening the image:\n{e}")


    def paste_image_from_clipboard(self):
        """Pastes an image from the clipboard."""
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                self._display_single_image_preview(img.copy(), None) # Pass None as source_info for clipboard
                self.image_source = 'clipboard'
                self.pasted_image_object = img.copy() # Store a copy
                print("Pasted image from clipboard.")
            else:
                # print("No image found on clipboard.")
                messagebox.showinfo("Clipboard", "No image found on the clipboard.")
        except Exception as e:
            # tkinter TclError can sometimes happen if clipboard is empty or format is weird
            if "CLIPBOARD" in str(e).upper():
                 messagebox.showinfo("Clipboard", "Could not access clipboard or no image found.")
            else:
                messagebox.showerror("Clipboard Error", f"Error pasting image: {e}")
            print(f"Error pasting from clipboard: {e}")


    def display_images(self):
        """Fetches online images or displays existing local/pasted selection."""
        # # If a local or pasted image is already selected for this note, don't fetch online
        # if self.image_source == 'local' or self.image_source == 'clipboard':
        #     print("Skipping online image search as local/pasted image is selected.")
        #     # The preview should already be displayed by browse/paste methods
        #     return

        # Clear previous online images and selection (but keep local/pasted if they exist)
        self._clear_image_selection_area()

        if not self.current_word:
            return

        # Fetch online images
        print(f"Searching online images for: {self.current_word}")
        try:
            # TODO: Make count configurable?
            self.image_results = image_search.search_images(self.current_meaning, count_per_source = COUNT_PER_SOURCE, num_meanings_per_source=MEANINGS_PER_SOURCE)
        except Exception as e:
            print(f"Error fetching online images: {e}")
            tk.Label(self.image_display_inner_frame, text="Error fetching images.").pack()
            return

        if not self.image_results:
            tk.Label(self.image_display_inner_frame, text="No online images found.").pack()
            return

        # Display online thumbnails in a grid
        MAX_COLS = 5
        for index, (thumb_url, full_url) in enumerate(self.image_results):
            try:
                # Consider adding placeholder before download starts
                response = requests.get(thumb_url, stream=True, timeout=5)
                response.raise_for_status()
                image_data = response.content # Use content for BytesIO
                img = Image.open(io.BytesIO(image_data))
                # Resize to a consistent thumbnail height
                thumb_height = 100
                # Handle potential division by zero if image height is 0
                if img.height == 0:
                    continue # Skip this image
                ratio = thumb_height / img.height
                thumb_width = int(img.width * ratio)
                img_resized = img.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)

                photo = ImageTk.PhotoImage(img_resized)

                img_label = tk.Label(self.image_display_inner_frame, image=photo, bd=2, relief=tk.RAISED)
                img_label.image = photo # Keep a reference!
                # Calculate grid position
                row = index // MAX_COLS
                col = index % MAX_COLS
                img_label.grid(row=row, column=col, padx=5, pady=5)

                # Store the widget and full URL, bind click event
                self.image_widgets.append((img_label, full_url))
                # Use default arguments in lambda to capture current values
                img_label.bind("<Button-1>", lambda event, label=img_label, url=full_url: self.select_image(label, url))

            except requests.exceptions.RequestException as e:
                print(f"Error downloading online thumbnail {thumb_url}: {e}")
                # Optionally display a placeholder
            except Exception as e:
                print(f"Error processing online thumbnail {thumb_url}: {e}")
                # Optionally display a placeholder

        # Update layout after adding all images
        self.update_idletasks()


    def select_image(self, clicked_label, source_info):
        """Handles selecting an online image thumbnail."""
        # This function is now specifically for ONLINE images.
        # Local/Pasted images are handled directly in their respective functions.

        # Deselect previous (could be online, local, or pasted)
        if self.selected_image_label:
            self.selected_image_label.config(relief=tk.RAISED, bg=self.image_display_inner_frame.cget('bg'))

        # Clear other sources
        self.selected_local_image_path = None
        self.pasted_image_object = None

        # Select new online image
        self.image_source = 'online'
        self.selected_image_url = source_info # Here, source_info is the full_url
        self.selected_image_label = clicked_label
        self.selected_image_label.config(relief=tk.SUNKEN, bg="lightblue") # Highlight

        print(f"Selected online image: {self.selected_image_url}")


    def _prepare_anki_data(self, note_id, sentence1_jp, sentence2_jp, image_source, selected_image_url, selected_local_path, pasted_image_obj):
        """
        Prepares audio and image data in the background thread.
        Accepts necessary data as arguments instead of relying on self.
        Returns: (audio_filename1, audio_filename2, image_filename, image_data_b64)
        """
        audio_filename1 = None
        audio_filename2 = None
        image_filename = None
        image_data_b64 = None # Base64 encoded image data

        # --- Generate Audio ---
        if sentence1_jp:
            audio_filename1 = f"_audio_{note_id}_1.mp3"
            try:
                TTS.store_note_audio_in_anki(sentence1_jp, audio_filename1)
            except Exception as e:
                print(f"Background: Error generating audio 1: {e}")
                # Avoid messagebox in thread
                audio_filename1 = None

        if sentence2_jp:
            audio_filename2 = f"_audio_{note_id}_2.mp3"
            try:
                TTS.store_note_audio_in_anki(sentence2_jp, audio_filename2)
            except Exception as e:
                print(f"Background: Error generating audio 2: {e}")
                # Avoid messagebox in thread
                audio_filename2 = None

        # --- Prepare Image Data based on Source ---
        if image_source == 'online' and selected_image_url:
            try:
                print(f"Background: Downloading online image: {selected_image_url}")
                response = requests.get(selected_image_url, timeout=15)
                response.raise_for_status() # Check for HTTP errors
                image_data = response.content
                image_data_b64 = base64.b64encode(image_data).decode('utf-8')
                # Determine extension (using selected_image_url passed as argument)
                content_type = response.headers.get('content-type', '').lower()
                if 'jpeg' in content_type or 'jpg' in content_type: ext = '.jpg'
                elif 'png' in content_type: ext = '.png'
                elif 'gif' in content_type: ext = '.gif'
                else: ext = os.path.splitext(selected_image_url)[1] or '.jpg' # Guess from URL or default
                image_filename = f"_image_{note_id}{ext}"
                print(f"Background: Prepared online image: {image_filename}")
            except Exception as e:
                print(f"Background: Error processing online image {selected_image_url}: {e}")
                # Avoid messagebox in thread
                image_filename = None
                image_data_b64 = None

        elif image_source == 'local' and selected_local_path:
            try:
                print(f"Background: Reading local image: {selected_local_path}")
                with open(selected_local_path, 'rb') as f:
                    image_data = f.read()
                image_data_b64 = base64.b64encode(image_data).decode('utf-8')
                ext = os.path.splitext(selected_local_path)[1] or '.jpg' # Get ext from path or default
                image_filename = f"_image_{note_id}{ext}"
                print(f"Background: Prepared local image: {image_filename}")
            except Exception as e:
                print(f"Background: Error processing local image {selected_local_path}: {e}")
                # Avoid messagebox in thread
                image_filename = None
                image_data_b64 = None

        elif image_source == 'clipboard' and pasted_image_obj:
            try:
                print("Background: Processing pasted image...")
                # Use the passed PIL Image object (pasted_image_obj)
                buffer = io.BytesIO()
                save_format = 'PNG' # Default to PNG
                try:
                    # Use the passed object directly
                    pasted_image_obj.save(buffer, format=save_format)
                except OSError: # Handle modes like RGBA that JPEG doesn't support directly
                     print("Background: Pasted image has alpha channel, converting to RGB for JPEG.")
                     rgb_image = pasted_image_obj.convert('RGB')
                     save_format = 'JPEG'
                     buffer = io.BytesIO() # Reset buffer
                     rgb_image.save(buffer, format=save_format) # Save the converted image

                image_data = buffer.getvalue()
                image_data_b64 = base64.b64encode(image_data).decode('utf-8')
                ext = '.png' if save_format == 'PNG' else '.jpg'
                image_filename = f"_image_{note_id}{ext}"
                print(f"Background: Prepared pasted image: {image_filename}")
            except Exception as e:
                print(f"Background: Error processing pasted image: {e}")
                # Avoid messagebox in thread
                image_filename = None
                image_data_b64 = None

        return audio_filename1, audio_filename2, image_filename, image_data_b64

    def _process_and_update_anki_background(self, note_id, word, sentence1_jp, sentence1_en, sentence2_jp, sentence2_en, image_source, selected_image_url, selected_local_path, pasted_image_obj):
        """
        Runs in background thread: Prepares data and updates Anki note.
        """
        try:
            print(f"Background: Starting processing for note {note_id}")
            # 1. Prepare Audio and Image data
            audio1, audio2, img_filename, img_data_b64 = self._prepare_anki_data(
                note_id, sentence1_jp, sentence2_jp, image_source, selected_image_url, selected_local_path, pasted_image_obj
            )

            # 2. Prepare other fields (HTML, URL)
            sentence1_jp_html = generate_furigana_html(sentence1_jp)
            sentence2_jp_html = generate_furigana_html(sentence2_jp)
            url = f"https://jisho.org/search/{word}" # Use the passed word

            # 3. Update Anki Note
            get_anki_data.update_note_full(
                note_id=note_id,
                sentence1_jp_html=sentence1_jp_html,
                sentence1_en=sentence1_en,
                sentence2_jp_html=sentence2_jp_html,
                sentence2_en=sentence2_en,
                url=url,
                audio1_filename=audio1,
                audio2_filename=audio2,
                image_filename=img_filename,
                image_data_b64=img_data_b64,
            )
            print(f"Background: Successfully updated note {note_id}.")

        except Exception as e:
            # Log any error during preparation or update
            print(f"Background: FAILED processing/updating note {note_id}: {e}")
            # Optionally, implement a queue to show errors in the main thread's UI

    def show_next_note(self):
        if not self.notes:
            messagebox.showinfo("Info", "No deck loaded.")
            return

        # --- Capture data from the CURRENT note for the background thread ---
        # Make sure to capture before self attributes are updated by display_current_note
        prev_note_index = self.current_index
        prev_note_id = self.notes[prev_note_index]['noteId']
        prev_word = self.current_word
        prev_sentence1_jp = self.sentence1_jp
        prev_sentence1_en = self.sentence1_en
        prev_sentence2_jp = self.sentence2_jp
        prev_sentence2_en = self.sentence2_en
        # Capture image details needed for _prepare_anki_data
        prev_image_source = self.image_source
        prev_selected_image_url = self.selected_image_url
        prev_selected_local_path = self.selected_local_image_path
        # Handle pasted image object carefully - pass the object itself
        # Make a copy if it exists, otherwise pass None
        prev_pasted_image_obj = self.pasted_image_object.copy() if self.pasted_image_object else None


        # --- Move to the NEXT note and display it IMMEDIATELY ---
        if self.current_index < len(self.notes) - 1:
            self.current_index += 1
            self._clear_image_selection_area() # Clear images *before* displaying new note
            self.display_current_note() # Load and display the NEW current note

            # --- Start background processing & update for the PREVIOUS note ---
            update_thread = threading.Thread(
                target=self._process_and_update_anki_background,
                args=( # Pass all captured previous note data
                    prev_note_id,
                    prev_word,
                    prev_sentence1_jp, prev_sentence1_en,
                    prev_sentence2_jp, prev_sentence2_en,
                    prev_image_source,
                    prev_selected_image_url,
                    prev_selected_local_path,
                    prev_pasted_image_obj
                ),
                daemon=True # Allows the main program to exit even if this thread is running
            )
            update_thread.start()
            # Save config when moving to the next note (implies acceptance of current settings)
            self.save_config()

        else:
            # --- Reached the end: Process and update the LAST note ---
            print("Reached end of deck. Starting update for the last note...")
            # Start background thread for the last note using the captured data
            update_thread = threading.Thread(
                target=self._process_and_update_anki_background,
                 args=( # Pass all captured previous note data
                    prev_note_id,
                    prev_word,
                    prev_sentence1_jp, prev_sentence1_en,
                    prev_sentence2_jp, prev_sentence2_en,
                    prev_image_source,
                    prev_selected_image_url,
                    prev_selected_local_path,
                    prev_pasted_image_obj
                ),
                daemon=True
            )
            update_thread.start()
            # Inform user immediately, don't wait for thread
            messagebox.showinfo("Info", "Reached the end of the deck. Last note update started in background.")


    def skip_to_next_note(self):
        # Skipping doesn't involve saving, so it's simpler
        if self.notes and self.current_index < len(self.notes) - 1:
            self.current_index += 1
            # Clear all image selections for the new note
            self._clear_image_selection_area()
            self.display_current_note()
        else:
            messagebox.showinfo("Info", "Reached the end of the deck.")

    def show_prev_note(self):
        if self.notes and self.current_index > 0:
            self.current_index -= 1
            # Clear all image selections for the new note
            self._clear_image_selection_area()
            self.display_current_note()
        else:
            messagebox.showinfo("Info", "This is the first note.")

    def jump_to_note(self):
        """Jumps to the specified note number."""
        if not self.notes:
            messagebox.showwarning("Warning", "No deck loaded.")
            return

        try:
            target_num_str = self.jump_entry.get()
            target_num = int(target_num_str)
            total_notes = len(self.notes)

            if 1 <= target_num <= total_notes:
                self.current_index = target_num - 1 # Adjust to 0-based index
                self._clear_image_selection_area() # Clear image selection
                self.display_current_note()
                self.jump_entry.delete(0, tk.END) # Clear the entry field after successful jump
            else:
                messagebox.showerror("Invalid Number", f"Please enter a number between 1 and {total_notes}.")
                self.jump_entry.delete(0, tk.END) # Clear the entry field

        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number.")
            self.jump_entry.delete(0, tk.END) # Clear the entry field
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")
            print(f"Error in jump_to_note: {e}")
            self.jump_entry.delete(0, tk.END) # Clear the entry field

    # --- Configuration Methods ---
    def load_config(self):
        """Loads configuration from the JSON file."""
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"Loaded config: {config}")
                return config
        except FileNotFoundError:
            print("Config file not found, using defaults.")
            return {}
        except json.JSONDecodeError:
            print("Error decoding config file, using defaults.")
            return {}
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}

    def save_config(self):
        """Saves the current deck and model selection to the JSON file."""
        config_data = {
            "deck": self.selected_deck.get(),
            "ollama_model": self.selected_model.get()
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
                print(f"Saved config: {config_data}")
        except Exception as e:
            print(f"Error saving config: {e}")
            # Optionally show a warning to the user
            # messagebox.showwarning("Config Error", f"Could not save configuration:\n{e}")

    # --- Dynamic List Update Methods ---
    def update_deck_list(self):
        """Fetches deck names from Anki and updates the combobox."""
        print("Updating deck list...")
        try:
            self.available_decks = get_anki_data.get_deck_names()
            self.deck_menu['values'] = self.available_decks
            if not self.available_decks:
                self.selected_deck.set("") # Clear selection if no decks
                messagebox.showinfo("Anki Decks", "No decks found or AnkiConnect not running.")
            elif self.selected_deck.get() not in self.available_decks:
                # If current selection is invalid, select the first available deck
                self.selected_deck.set(self.available_decks[0])
            print(f"Decks updated: {self.available_decks}")
        except Exception as e:
            messagebox.showerror("Anki Error", f"Could not fetch deck names:\n{e}")
            self.available_decks = []
            self.deck_menu['values'] = []
            self.selected_deck.set("")

    def update_model_list(self):
        """Fetches Ollama model names and updates the combobox."""
        print("Updating Ollama model list...")
        try:
            # Assuming get_ollama_models is added to sentence_ai or similar
            # For now, let's placeholder this call. Need to implement get_ollama_models next.
            # self.available_models = sentence.get_ollama_models() # Placeholder
            # --- Temporary Placeholder ---
            try:
                response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
                response.raise_for_status()
                models_data = response.json()
                self.available_models = sorted([m['name'] for m in models_data.get('models', [])])
            except requests.exceptions.RequestException as e:
                 print(f"Error fetching Ollama models: {e}")
                 self.available_models = [] # Keep empty on error
            # --- End Temporary Placeholder ---

            self.model_menu['values'] = self.available_models
            if not self.available_models:
                self.selected_model.set("") # Clear selection if no models
                messagebox.showinfo("Ollama Models", "No models found or Ollama server not running.")
            elif self.selected_model.get() not in self.available_models:
                 # If current selection is invalid, select the first available model
                 if self.available_models: # Check if list is not empty after fetch attempt
                     self.selected_model.set(self.available_models[0])
                 else:
                     self.selected_model.set("") # Clear if still no models
            print(f"Models updated: {self.available_models}")
            # Save config whenever the model list is updated and a valid model is selected
            if self.selected_model.get():
                self.save_config()
        except Exception as e:
            messagebox.showerror("Ollama Error", f"Could not fetch Ollama models:\n{e}")
            self.available_models = []
            self.model_menu['values'] = []
            self.selected_model.set("")

    # --- Connection Status Check Methods ---
    def check_anki_connection(self):
        """Periodically checks connection to AnkiConnect."""
        try:
            # Use a lightweight request like 'version'
            get_anki_data.invoke('version')
            self.anki_status_label.config(text="Anki: Connected", fg="green")
        except Exception:
            self.anki_status_label.config(text="Anki: Disconnected", fg="red")
            # If disconnected, maybe clear deck list or disable load button?
            # self.deck_menu['values'] = []
            # self.selected_deck.set("")
        finally:
            # Schedule the next check
            self.after(STATUS_CHECK_INTERVAL, self.check_anki_connection)

    def check_ollama_connection(self):
        """Periodically checks connection to Ollama API."""
        try:
            # Check if the base Ollama API endpoint is reachable
            response = requests.get(OLLAMA_API_URL, timeout=2) # Short timeout
            response.raise_for_status() # Check for HTTP errors
            # Could add a more specific check like /api/tags if needed
            self.ollama_status_label.config(text="Ollama: Online", fg="green")
        except requests.exceptions.RequestException:
            self.ollama_status_label.config(text="Ollama: Offline", fg="red")
            # If disconnected, maybe clear model list or disable generation?
            # self.model_menu['values'] = []
            # self.selected_model.set("")
        except Exception as e:
             # Catch other potential errors
             print(f"Unexpected error checking Ollama connection: {e}")
             self.ollama_status_label.config(text="Ollama: Error", fg="red")
        finally:
            # Schedule the next check
            self.after(STATUS_CHECK_INTERVAL, self.check_ollama_connection)


if __name__ == "__main__":
    app = AnkiGUI()
    app.mainloop()

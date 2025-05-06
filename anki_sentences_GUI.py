import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from PIL import Image, ImageTk
import io # Still needed for Image.open(io.BytesIO(image_data)) in display_images

import gui.anki_handler as anki_handler
import gui.ollama_handler as ollama_handler
import gui.image_handler as image_handler
import gui.config_handler as config_handler
import gui.utils as utils

# Configuration
STATUS_CHECK_INTERVAL = 10000 # Milliseconds (10 seconds) for connection checks

class AnkiGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Anki Sentence & TTS Generator")
        # Load configuration first
        config = config_handler.load_config()
        default_deck = config.get("deck", "") # Get saved deck or empty string
        default_model = config.get("ollama_model", "") # Get saved model or empty string

        self.selected_deck = tk.StringVar(value=default_deck)
        self.selected_target_deck_to_move = tk.StringVar() # For the new move-to-deck combobox
        self.notes = []
        self.current_index = 0

        # Variables for dynamic lists
        self.available_decks = []
        self.available_models = []
        self.target_deck_options = [] # For the move-to-deck combobox

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
        # self.anki_update_lock = threading.Lock() # Threading is handled by anki_handler

        self.create_widgets()
        self.update_deck_list() # Populate decks initially
        self.update_target_deck_list() # Populate target decks for moving
        self.update_model_list() # Populate models initially

        # Set initial selection after lists are populated
        if default_deck and default_deck in self.available_decks: # self.available_decks is populated by update_deck_list
            self.selected_deck.set(default_deck)
        elif self.available_decks:
             self.selected_deck.set(self.available_decks[0]) # Fallback to first deck
        
        # Set initial selection for target deck to move (optional, can be empty)
        if self.target_deck_options:
            # self.selected_target_deck_to_move.set(self.target_deck_options[0]) # Or leave empty
            pass

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
        anki_row_frame.pack(fill=tk.X, pady=(0, 2)) # Reduced padding below this row

        # Anki Status Indicator
        self.anki_status_label = tk.Label(anki_row_frame, text="Anki: Checking...", fg="orange", width=18, anchor="w")
        self.anki_status_label.pack(side=tk.LEFT, padx=(0, 10))

        # Deck selection frame (for loading notes)
        deck_load_frame = tk.Frame(anki_row_frame)
        deck_load_frame.pack(side=tk.LEFT, padx=5)
        tk.Label(deck_load_frame, text="Deck:").pack(side=tk.LEFT)
        self.deck_menu = ttk.Combobox(deck_load_frame, textvariable=self.selected_deck,
                                      values=self.available_decks, state="readonly", width=30)
        self.deck_menu.pack(side=tk.LEFT, padx=5)
        tk.Button(deck_load_frame, text="🔄", command=self.update_deck_list).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(deck_load_frame, text="Load Deck", command=self.load_deck).pack(side=tk.LEFT)

        # --- Row 2: Move Card to Deck ---
        move_deck_row_frame = tk.Frame(top_bar_frame)
        move_deck_row_frame.pack(fill=tk.X, pady=(0, 5))

        # Empty label for alignment with Anki status (optional, adjust width as needed)
        tk.Label(move_deck_row_frame, text="", width=18, anchor="w").pack(side=tk.LEFT, padx=(0,10))


        move_deck_frame = tk.Frame(move_deck_row_frame)
        move_deck_frame.pack(side=tk.LEFT, padx=5)
        tk.Label(move_deck_frame, text="Move to:").pack(side=tk.LEFT)
        self.move_to_deck_menu = ttk.Combobox(move_deck_frame, textvariable=self.selected_target_deck_to_move,
                                              values=self.target_deck_options, state="readonly", width=30)
        self.move_to_deck_menu.pack(side=tk.LEFT, padx=5)
        tk.Button(move_deck_frame, text="🔄", command=self.update_target_deck_list).pack(side=tk.LEFT, padx=(0,5))

        # --- Row 3: Ollama Status and Model Selection --- (was Row 2)
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
            self.notes = anki_handler.get_deck_notes(deck_name)
            self.current_index = 0
            self.generated_sentences = {}  # Clear previously generated sentences.
            if not self.notes:
                messagebox.showinfo("Info", f"No notes found in the deck '{deck_name}'.")
                self.update_progress() # Update progress even if empty
            else:
                self.update_progress()
                self.display_current_note()
                # Save config after successfully loading a deck
                config_handler.save_config({
                    "deck": self.selected_deck.get(),
                    "ollama_model": self.selected_model.get()
                })
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
        tk.Label(frame1, text=utils.generate_furigana_string(self.sentence1_jp), wraplength=750, font=("Helvetica", 16)).pack(anchor="w", padx=10)
        tk.Label(frame1, text=f"Meaning: {self.sentence1_en}", fg="gray", wraplength=750).pack(anchor="w", padx=10)
        tk.Checkbutton(frame1, text="Keep", variable=self.keep_var1).pack(anchor="e")

        # Sentence 2 section.
        frame2 = tk.Frame(self.note_display_frame, bd=2, relief=tk.GROOVE, padx=5, pady=5)
        frame2.pack(fill=tk.X, pady=5)
        tk.Label(frame2, text="Sentence 2:", font=("Helvetica", 12, "bold")).pack(anchor="w")
        tk.Label(frame2, text=utils.generate_furigana_string(self.sentence2_jp), wraplength=750, font=("Helvetica", 16)).pack(anchor="w", padx=10)
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
            jp1, en1, jp2, en2 = ollama_handler.generate_sentences(self.current_word, self.current_meaning, selected_model)
        except ValueError as ve: # Catch specific error from handler for better feedback
            messagebox.showwarning("Sentence Generation Error", str(ve))
            return
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
            new_jp1, new_en1, new_jp2, new_en2 = ollama_handler.generate_sentences(self.current_word, self.current_meaning, selected_model)
        except ValueError as ve: # Catch specific error from handler
            messagebox.showwarning("Sentence Generation Error", str(ve))
            return
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

        photo = image_handler.create_preview_thumbnail(img_object)
        if photo:
            img_label = tk.Label(self.image_display_inner_frame, image=photo, bd=2, relief=tk.SUNKEN, bg="lightblue") # Pre-select it
            img_label.image = photo # Keep reference
            img_label.grid(row=0, column=0, padx=5, pady=5) # Place in grid

            self.image_widgets.append((img_label, source_info))
            self.selected_image_label = img_label
            self.update_idletasks()
        else:
            print(f"Error displaying single image preview (photo creation failed).")
            tk.Label(self.image_display_inner_frame, text="Error displaying image.").pack()


    def browse_for_image(self):
        """Opens file dialog to select a local image."""
        filepath = image_handler.browse_local_image()
        if not filepath:
            return # User cancelled or error handled by image_handler

        try:
            # Image.open needs to be here to get the PIL Image object for preview
            img = Image.open(filepath)
            # img.verify() # Verification is done in image_handler
            # img = Image.open(filepath) # Re-open after verify
            img.load() # Load image data

            self._display_single_image_preview(img, filepath)
            self.image_source = 'local'
            self.selected_local_image_path = filepath
            # print(f"Selected local file: {filepath}") # Already printed by handler

        except (FileNotFoundError, IOError, SyntaxError) as e: # Should be rare if handler validates
            messagebox.showerror("Image Error", f"Could not open or read image file after selection:\n{filepath}\n\nError: {e}")
        except Exception as e:
             messagebox.showerror("Image Error", f"An unexpected error occurred opening the image for preview:\n{e}")


    def paste_image_from_clipboard(self):
        """Pastes an image from the clipboard."""
        img = image_handler.get_image_from_clipboard() # Returns PIL Image or None
        if img:
            self._display_single_image_preview(img, None) # Pass None as source_info for clipboard
            self.image_source = 'clipboard'
            self.pasted_image_object = img # Store the original PIL Image object
            # print("Pasted image from clipboard.") # Printed by handler
        else:
            messagebox.showinfo("Clipboard", "No image found on the clipboard or error accessing.")


    def display_images(self):
        """Fetches online images or displays existing local/pasted selection."""
        self._clear_image_selection_area()

        if not self.current_word: # Or current_meaning, depending on search query preference
            return

        # Fetch online images
        # print(f"Searching online images for: {self.current_meaning}") # Printed by handler
        self.image_results = image_handler.search_online_images(self.current_meaning)

        if not self.image_results:
            tk.Label(self.image_display_inner_frame, text="No online images found.").pack()
            return

        # Display online thumbnails in a grid
        MAX_COLS = 5
        for index, (thumb_url, full_url) in enumerate(self.image_results):
            image_data = image_handler.download_image_data(thumb_url)
            if not image_data:
                print(f"Skipping thumbnail for {thumb_url} due to download error.")
                continue

            # Create PhotoImage from data (could be a helper in image_handler if complex)
            try:
                img_pil = Image.open(io.BytesIO(image_data)) # Use io.BytesIO
                thumb_height = 100
                if img_pil.height == 0: continue
                ratio = thumb_height / img_pil.height
                thumb_width = int(img_pil.width * ratio)
                img_resized = img_pil.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img_resized)
            except Exception as e:
                print(f"Error creating Tk PhotoImage for {thumb_url}: {e}")
                continue

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

            # except requests.exceptions.RequestException as e: # Handled by download_image_data
            #     print(f"Error downloading online thumbnail {thumb_url}: {e}")
            # except Exception as e: # Handled by create_thumbnail or PIL/ImageTk
            #     print(f"Error processing online thumbnail {thumb_url}: {e}")

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

    # Removed _prepare_anki_data and _process_and_update_anki_background
    # These are now handled by anki_handler.py

    def _get_target_deck_options_list(self) -> list:
        """Generates the sorted list of deck names for the 'Move to' combobox."""
        all_decks = anki_handler.get_deck_names()
        if not all_decks:
            return []

        target_decks_for_dialog = []
        japan_deck_name = "Japanisch Wörter"
        processed_decks = set() # To avoid duplicates and handle ordering

        # Add Japanisch Wörter subdecks first if they exist
        if japan_deck_name in all_decks:
            subdecks = anki_handler.get_subdecks(japan_deck_name)
            if subdecks:
                target_decks_for_dialog.append(f"-- {japan_deck_name} Subdecks --")
                processed_decks.add(f"-- {japan_deck_name} Subdecks --") # Mark separator as processed
                for sd in sorted(subdecks):
                    target_decks_for_dialog.append(sd)
                    processed_decks.add(sd)
                target_decks_for_dialog.append("--------------------")
                processed_decks.add("--------------------") # Mark separator

        # Add all other decks, ensuring no duplicates and proper sorting
        other_decks_to_add = []
        for deck in sorted(all_decks): # Iterate through all decks sorted alphabetically
            if deck not in processed_decks:
                other_decks_to_add.append(deck)
                processed_decks.add(deck)
        
        target_decks_for_dialog.extend(other_decks_to_add)
        
        # Remove any leading/trailing separators if no actual decks were added around them
        if target_decks_for_dialog and target_decks_for_dialog[0].startswith("--") and \
           (len(target_decks_for_dialog) == 1 or target_decks_for_dialog[1].startswith("--")):
            target_decks_for_dialog.pop(0)
        if target_decks_for_dialog and target_decks_for_dialog[-1].startswith("--") and \
           (len(target_decks_for_dialog) == 1 or target_decks_for_dialog[-2].startswith("--")):
            target_decks_for_dialog.pop(-1)

        return target_decks_for_dialog

    def update_target_deck_list(self):
        """Fetches and updates the list of target decks for moving cards."""
        print("Updating target deck list for moving...")
        self.target_deck_options = self._get_target_deck_options_list()
        self.move_to_deck_menu['values'] = self.target_deck_options
        if self.target_deck_options:
            # self.selected_target_deck_to_move.set(self.target_deck_options[0]) # Optionally set a default
            self.selected_target_deck_to_move.set("") # Or leave it blank
        else:
            self.selected_target_deck_to_move.set("")
            # messagebox.showinfo("Target Decks", "No target decks found for moving.") # Maybe too intrusive
        print(f"Target decks for moving updated: {self.target_deck_options}")


    def show_next_note(self):
        if not self.notes:
            messagebox.showinfo("Info", "No deck loaded.")
            return
        
        target_deck = self.selected_target_deck_to_move.get()
        if not target_deck or target_deck.startswith("--"):
            messagebox.showwarning("Warning", "Please select a valid target deck to move the card to.")
            return

        # Capture data from the CURRENT note for the background thread
        prev_note_id = self.notes[self.current_index]['noteId']
        prev_word = self.current_word
        prev_sentence1_jp = self.sentence1_jp
        prev_sentence1_en = self.sentence1_en
        prev_sentence2_jp = self.sentence2_jp
        prev_sentence2_en = self.sentence2_en
        prev_image_source = self.image_source
        prev_selected_image_url = self.selected_image_url
        prev_selected_local_path = self.selected_local_image_path
        prev_pasted_image_obj = self.pasted_image_object.copy() if self.pasted_image_object else None

        # Move to the NEXT note and display it IMMEDIATELY
        if self.current_index < len(self.notes) - 1:
            self.current_index += 1
            self._clear_image_selection_area()
            self.display_current_note()

            # Start background processing & update for the PREVIOUS note
            anki_handler.start_anki_update_thread(
                prev_note_id,
                prev_word,
                prev_sentence1_jp, prev_sentence1_en,
                prev_sentence2_jp, prev_sentence2_en,
                prev_image_source,
                prev_selected_image_url,
                prev_selected_local_path,
                prev_pasted_image_obj,
                target_deck
            )
            # Save config when moving to the next note
            config_handler.save_config({
                "deck": self.selected_deck.get(),
                "ollama_model": self.selected_model.get()
            })
        else:
            # Reached the end: Process and update the LAST note
            print("Reached end of deck. Starting update for the last note...")
            anki_handler.start_anki_update_thread(
                prev_note_id,
                prev_word,
                prev_sentence1_jp, prev_sentence1_en,
                prev_sentence2_jp, prev_sentence2_en,
                prev_image_source,
                prev_selected_image_url,
                prev_selected_local_path,
                prev_pasted_image_obj
            )
            messagebox.showinfo("Info", "Reached the end of the deck. Last note update started in background.")
            # Optionally, clear the display or disable "Next" further if desired
            # For now, it just shows the message and the last card remains displayed.

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
    # load_config and save_config are now in config_handler.py

        # --- Dynamic List Update Methods ---
    def update_deck_list(self):
        """Fetches deck names from Anki and updates the main deck combobox."""
        print("Updating main deck list...")
        try:
            self.available_decks = anki_handler.get_deck_names() # This is already a class attribute
            self.deck_menu['values'] = self.available_decks
            if not self.available_decks:
                self.selected_deck.set("")
                messagebox.showinfo("Anki Decks", "No decks found or AnkiConnect not running.")
            elif self.selected_deck.get() not in self.available_decks:
                if self.available_decks: # Check again if it's populated
                    self.selected_deck.set(self.available_decks[0])
                else:
                    self.selected_deck.set("") # Should be redundant if above handles it
            print(f"Main decks updated: {self.available_decks}")
            # Also refresh the target deck list as it depends on all_decks
            self.update_target_deck_list()
        except Exception as e:
            messagebox.showerror("Anki Error", f"Could not fetch deck names:\n{e}")
            self.available_decks = []
            self.deck_menu['values'] = []
            self.selected_deck.set("")
            self.update_target_deck_list() # Still try to update target list (will be empty)


    def update_model_list(self):
        """Fetches Ollama model names and updates the combobox."""
        print("Updating Ollama model list...")
        try:
            self.available_models = ollama_handler.get_ollama_models()
            self.model_menu['values'] = self.available_models
            if not self.available_models:
                self.selected_model.set("") # Clear selection if no models
                messagebox.showinfo("Ollama Models", "No models found or Ollama server not running.")
            elif self.selected_model.get() not in self.available_models:
                 if self.available_models:
                     self.selected_model.set(self.available_models[0])
                 else:
                     self.selected_model.set("")
            print(f"Models updated: {self.available_models}")
            if self.selected_model.get():
                config_handler.save_config({
                    "deck": self.selected_deck.get(),
                    "ollama_model": self.selected_model.get()
                })
        except Exception as e:
            messagebox.showerror("Ollama Error", f"Could not fetch Ollama models:\n{e}")
            self.available_models = []
            self.model_menu['values'] = []
            self.selected_model.set("")

    # --- Connection Status Check Methods ---
    def check_anki_connection(self):
        """Periodically checks connection to AnkiConnect."""
        status_text, status_color = anki_handler.check_anki_connection_status()
        self.anki_status_label.config(text=status_text, fg=status_color)
        # Schedule the next check
        self.after(STATUS_CHECK_INTERVAL, self.check_anki_connection)

    def check_ollama_connection(self):
        """Periodically checks connection to Ollama API."""
        status_text, status_color = ollama_handler.check_ollama_connection_status()
        self.ollama_status_label.config(text=status_text, fg=status_color)
        # Schedule the next check
        self.after(STATUS_CHECK_INTERVAL, self.check_ollama_connection)


if __name__ == "__main__":
    app = AnkiGUI()
    app.mainloop()

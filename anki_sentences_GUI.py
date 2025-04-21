import re
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import Libary.get_anki_data as get_anki_data
import Libary.sentance_ai as sentence
import Libary.generate_audio as TTS
import Libary.image_search as image_search # Added
import pykakasi
import requests # Added
from PIL import Image, ImageTk # Added
import io # Added
import base64 # Added for sending image data to Anki
import os # Added for filename manipulation

# List the two available decks.
DECKS = ["Wörter(aus Wörterbuch)", "Japanisch Wörter"]
ANKI_CONNECT_URL = "http://localhost:8765"

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
        self.geometry("800x800")
        self.selected_deck = tk.StringVar(value=DECKS[0])
        self.notes = []
        self.current_index = 0

        #Load Models
        self.model_names = ["gemma3:latest", "gemma3:12b", "llama3.1:8b", "deepseek-r1:14b", "deepseek-r1:8b"]
        self.selected_model = tk.StringVar(value=self.model_names[0])
        self.manual_model = tk.StringVar(value="")  # For manual input


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
        self.image_widgets = [] # Stores (label_widget, full_url)
        self.selected_image_url = None # Stores the full_url of the selected image
        self.selected_image_label = None # Stores the label widget of the selected image

        self.create_widgets()

    def create_widgets(self):
        # Deck selection frame.
        deck_frame = tk.Frame(self)
        deck_frame.pack(pady=10)
        tk.Label(deck_frame, text="Select Deck:").pack(side=tk.LEFT)
        deck_menu = ttk.Combobox(deck_frame, textvariable=self.selected_deck, 
                                 values=DECKS, state="readonly", width=30)
        deck_menu.pack(side=tk.LEFT, padx=5)
        tk.Button(deck_frame, text="Load Deck", command=self.load_deck).pack(side=tk.LEFT)

        #Model selection 
        model_frame = tk.Frame(self)
        model_frame.pack(pady=5)
        tk.Label(model_frame, text="Select Model:").pack(side=tk.LEFT)
        model_menu = ttk.Combobox(model_frame, textvariable=self.selected_model,
                                values=self.model_names, state="readonly", width=30)
        model_menu.pack(side=tk.LEFT, padx=5)

        # Manual model entry.
        manual_frame = tk.Frame(self)
        manual_frame.pack(pady=5)
        tk.Label(manual_frame, text="Or enter Model:").pack(side=tk.LEFT)
        model_entry = tk.Entry(manual_frame, textvariable=self.manual_model, width=30)
        model_entry.pack(side=tk.LEFT, padx=5)


        # Main frame for note details and sentence generation.
        self.note_display_frame = tk.Frame(self)
        self.note_display_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Navigation frame.
        nav_frame = tk.Frame(self)
        nav_frame.pack(pady=10)
        tk.Button(nav_frame, text="Previous", command=self.show_prev_note).pack(side=tk.LEFT, padx=5)
        tk.Button(nav_frame, text="Next", command=self.show_next_note).pack(side=tk.LEFT, padx=5)
        tk.Button(nav_frame, text="Skip", command=self.skip_to_next_note).pack(side=tk.LEFT, padx=5)

        # Progress frame.
        progress_frame = tk.Frame(self)
        progress_frame.pack(pady=5, fill=tk.X, padx=10)
        self.progress_label = tk.Label(progress_frame, text="Note 0 of 0")
        self.progress_label.pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, padx=10)

        # Image display area (using a scrolled text for potential overflow)
        image_area_frame = tk.LabelFrame(self, text="Image Selection", padx=5, pady=5)
        image_area_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=False) # Don't expand vertically too much

        # Use a Canvas inside a Frame to make it scrollable horizontally
        self.image_canvas_frame = tk.Frame(image_area_frame)
        self.image_canvas_frame.pack(fill=tk.X, expand=True)

        self.image_canvas = tk.Canvas(self.image_canvas_frame, height=120) # Fixed height for thumbnails
        self.image_scrollbar = tk.Scrollbar(self.image_canvas_frame, orient="horizontal", command=self.image_canvas.xview)
        self.image_canvas.configure(xscrollcommand=self.image_scrollbar.set)

        self.image_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.image_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # This frame will contain the actual image labels and will be scrolled by the canvas
        self.image_display_inner_frame = tk.Frame(self.image_canvas)
        self.image_canvas.create_window((0, 0), window=self.image_display_inner_frame, anchor="nw")

        # Update scrollregion when the inner frame size changes
        self.image_display_inner_frame.bind("<Configure>", lambda e: self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all")))

    def load_deck(self):
        deck_name = self.selected_deck.get()
        try:
            deck_info = get_anki_data.get_deck_info(deck_name)
            self.notes = deck_info.get("allNotes", [])
            self.current_index = 0
            self.generated_sentences = {}  # Clear previously generated sentences.
            if not self.notes:
                messagebox.showinfo("Info", "No notes found in the selected deck.")
            else:
                self.update_progress()
                self.display_current_note()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load deck: {e}")

    def update_progress(self):
        """Update progress bar and label."""
        total = len(self.notes)
        current = self.current_index + 1 if total > 0 else 0
        self.progress_label.config(text=f"Note {current} of {total}")
        self.progress_bar['maximum'] = total
        self.progress_bar['value'] = current

    def display_current_note(self):
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
        self.display_images() # Call function to fetch and show images

        # Update progress display.
        self.update_progress()

    def generate_sentences(self):
        """
        Generate sentences for the current note and store them.
        """
        try:
            selected_model = self.manual_model.get().strip() or self.selected_model.get()
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
        note_id = self.notes[self.current_index]['noteId']
        # Retrieve current stored sentences.
        current_jp1 = self.sentence1_jp
        current_en1 = self.sentence1_en
        current_jp2 = self.sentence2_jp
        current_en2 = self.sentence2_en

        try:
            selected_model = self.manual_model.get().strip() or self.selected_model.get()
            new_jp1, new_en1, new_jp2, new_en2 = sentence.ollama_sentances(self.current_word, self.current_meaning, selected_model)

        except Exception as e:
            messagebox.showerror("Error", f"Error regenerating sentences: {e}")
            return

        # Update sentence 1 if not kept.
        if not self.keep_var1.get():
            if new_jp1:
                current_jp1 = new_jp1
            else:
                current_jp1 = ""
            current_en1 = new_en1

        # Update sentence 2 if not kept.
        if not self.keep_var2.get():
            if new_jp2:
                current_jp2 = new_jp2
            else:
                current_jp2 = ""
            current_en2 = new_en2

        # Store the updated sentences.
        self.generated_sentences[note_id] = (current_jp1, current_en1, current_jp2, current_en2)
        # Re-display the note.
        self.display_current_note()

    def display_images(self):
        """Fetches images for the current word and displays thumbnails."""
        # Clear previous images and selection
        for widget in self.image_display_inner_frame.winfo_children():
            widget.destroy()
        self.image_widgets = []
        self.selected_image_url = None
        self.selected_image_label = None
        self.image_canvas.xview_moveto(0) # Reset scroll

        if not self.current_word:
            return

        # Fetch images (consider doing this in a separate thread for responsiveness later)
        try:
            # TODO: Make count configurable?
            self.image_results = image_search.search_images(self.current_meaning, count_per_source=3)
        except Exception as e:
            print(f"Error fetching images: {e}")
            # Optionally display an error message in the image frame
            tk.Label(self.image_display_inner_frame, text="Error fetching images.").pack()
            return

        if not self.image_results:
            tk.Label(self.image_display_inner_frame, text="No images found.").pack()
            return

        # Display thumbnails
        for thumb_url, full_url in self.image_results:
            try:
                response = requests.get(thumb_url, stream=True, timeout=5)
                response.raise_for_status()
                image_data = response.raw.read()
                img = Image.open(io.BytesIO(image_data))
                # Resize to a consistent thumbnail height
                thumb_height = 100
                ratio = thumb_height / img.height
                thumb_width = int(img.width * ratio)
                img = img.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)

                photo = ImageTk.PhotoImage(img)

                img_label = tk.Label(self.image_display_inner_frame, image=photo, bd=2, relief=tk.RAISED)
                img_label.image = photo # Keep a reference!
                img_label.pack(side=tk.LEFT, padx=5, pady=5)

                # Store the widget and full URL, bind click event
                self.image_widgets.append((img_label, full_url))
                img_label.bind("<Button-1>", lambda event, label=img_label, url=full_url: self.select_image(label, url))

            except requests.exceptions.RequestException as e:
                print(f"Error downloading thumbnail {thumb_url}: {e}")
            except Exception as e:
                print(f"Error processing thumbnail {thumb_url}: {e}")
                # Optionally display a placeholder if an image fails

        # Update the canvas scroll region after adding all images
        self.image_display_inner_frame.update_idletasks()
        self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all"))


    def select_image(self, clicked_label, full_url):
        """Handles image selection."""
        # Deselect previous
        if self.selected_image_label:
            self.selected_image_label.config(relief=tk.RAISED, bg=self.image_display_inner_frame.cget('bg')) # Reset background

        # Select new
        self.selected_image_url = full_url
        self.selected_image_label = clicked_label
        self.selected_image_label.config(relief=tk.SUNKEN, bg="lightblue") # Highlight selected

        print(f"Selected image: {full_url}") # For debugging


    def send_to_anki(self):
        """Prepares audio and selected image data for Anki update."""
        note_id = self.notes[self.current_index]['noteId']
        audio_filename1 = None
        audio_filename2 = None
        image_filename = None
        image_data_b64 = None # Base64 encoded image data

        # Generate Audio 1
        if self.sentence1_jp:
            audio_filename1 = f"_audio_{note_id}_1.mp3"
            try:
                TTS.store_note_audio_in_anki(self.sentence1_jp, audio_filename1)
            except Exception as e:
                print(f"Error generating audio 1: {e}")
                messagebox.showwarning("Audio Error", f"Failed to generate audio for sentence 1: {e}")
                audio_filename1 = None # Don't send filename if generation failed

        # Generate Audio 2
        if self.sentence2_jp:
            audio_filename2 = f"_audio_{note_id}_2.mp3"
            try:
                TTS.store_note_audio_in_anki(self.sentence2_jp, audio_filename2)
            except Exception as e:
                print(f"Error generating audio 2: {e}")
                messagebox.showwarning("Audio Error", f"Failed to generate audio for sentence 2: {e}")
                audio_filename2 = None

        # Prepare Image
        if self.selected_image_url:
            try:
                print(f"Downloading full image: {self.selected_image_url}")
                response = requests.get(self.selected_image_url, timeout=15)
                response.raise_for_status()
                image_data = response.content
                image_data_b64 = base64.b64encode(image_data).decode('utf-8')

                # Determine file extension (basic check)
                content_type = response.headers.get('content-type', '').lower()
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = '.jpg'
                elif 'png' in content_type:
                    ext = '.png'
                elif 'gif' in content_type:
                    ext = '.gif'
                else:
                    # Try to guess from URL, default to jpg
                    ext = os.path.splitext(self.selected_image_url)[1]
                    if not ext or len(ext) > 5: # Basic sanity check
                       ext = '.jpg'

                image_filename = f"_image_{note_id}{ext}"
                print(f"Prepared image: {image_filename}")

            except requests.exceptions.RequestException as e:
                print(f"Error downloading full image {self.selected_image_url}: {e}")
                messagebox.showerror("Image Error", f"Failed to download selected image: {e}")
            except Exception as e:
                print(f"Error processing image {self.selected_image_url}: {e}")
                messagebox.showerror("Image Error", f"Failed to process selected image: {e}")

        return audio_filename1, audio_filename2, image_filename, image_data_b64



    def show_next_note(self):
        note_id = self.notes[self.current_index]['noteId']
        url = f"https://jisho.org/search/{self.current_word}"

        # Prepare audio and image data
        audio1, audio2, img_filename, img_data_b64 = self.send_to_anki()

        # Update Anki note (needs modification in get_anki_data)
        try:
            get_anki_data.update_note_full(
                note_id=note_id,
                sentence1_jp_html=generate_furigana_html(self.sentence1_jp),
                sentence1_en=self.sentence1_en,
                sentence2_jp_html=generate_furigana_html(self.sentence2_jp),
                sentence2_en=self.sentence2_en,
                url=url,
                audio1_filename=audio1,
                audio2_filename=audio2,
                image_filename=img_filename,
                image_data_b64=img_data_b64, # Pass image data for storage
            )
            print(f"Successfully updated note {note_id}")
        except Exception as e:
            messagebox.showerror("Anki Update Error", f"Failed to update note {note_id}: {e}")
            # Decide if we should proceed to next note or not? For now, we do.
            print(f"Anki update failed for note {note_id}: {e}")


        # Move to the next note
        if self.notes and self.current_index < len(self.notes) - 1:
            self.current_index += 1
            # Clear selection for the new note
            self.selected_image_url = None
            self.selected_image_label = None
            self.display_current_note()
        else:
            messagebox.showinfo("Info", "Reached the end of the deck.")

    def skip_to_next_note(self):
        if self.notes and self.current_index < len(self.notes) - 1:
            self.current_index += 1
            # Clear selection for the new note
            self.selected_image_url = None
            self.selected_image_label = None
            self.display_current_note()
        else:
            messagebox.showinfo("Info", "Reached the end of the deck.")

    def show_prev_note(self):
        if self.notes and self.current_index > 0:
            self.current_index -= 1
            # Clear selection for the new note
            self.selected_image_url = None
            self.selected_image_label = None
            self.display_current_note()
        else:
            messagebox.showinfo("Info", "This is the first note.")

if __name__ == "__main__":
    app = AnkiGUI()
    app.mainloop()

import Libary.get_anki_data as get_anki_data
import Libary.generate_audio as TTS
import gui.utils as utils # Import from the new utils module
import threading
import base64
import os
import io
import requests
import time # Potentially needed if any delays are added later

ANKI_CONNECT_URL = "http://localhost:8765" # Keep Anki connect URL here

# --- Deck and Note Functions ---

def get_deck_names():
    """Fetches deck names from Anki."""
    return get_anki_data.get_deck_names()

def get_deck_notes(deck_name):
    """Fetches all notes for a given deck name."""
    deck_info = get_anki_data.get_deck_info(deck_name)
    return deck_info.get("allNotes", [])

def get_subdecks(parent_deck_name: str) -> list:
    """Fetches immediate subdecks for a given parent deck."""
    try:
        return get_anki_data.get_subdeck_names(parent_deck_name)
    except Exception as e:
        print(f"Error in anki_handler getting subdecks for '{parent_deck_name}': {e}")
        return [] # Return empty list on error to prevent GUI crash

def move_note_to_deck(note_id: int, target_deck_name: str):
    """Moves a note to the specified target deck."""
    try:
        get_anki_data.move_note_to_deck(note_id, target_deck_name)
        print(f"Successfully initiated move of note {note_id} to deck '{target_deck_name}'.")
        # Optionally, return a status or True/False if the GUI needs to confirm
    except Exception as e:
        print(f"Error in anki_handler moving note {note_id} to '{target_deck_name}': {e}")
        # Re-raise the exception so the GUI can catch it and display a message
        raise

# --- Background Processing for Anki Update ---

def _prepare_anki_data(note_id, sentence1_jp, sentence2_jp, image_source, selected_image_url, selected_local_path, pasted_image_obj):
    """
    Prepares audio and image data in the background thread.
    Accepts necessary data as arguments.
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
            print(f"Background: Generated audio: {audio_filename1}")
        except Exception as e:
            print(f"Background: Error generating audio 1: {e}")
            audio_filename1 = None

    if sentence2_jp:
        audio_filename2 = f"_audio_{note_id}_2.mp3"
        try:
            TTS.store_note_audio_in_anki(sentence2_jp, audio_filename2)
            print(f"Background: Generated audio: {audio_filename2}")
        except Exception as e:
            print(f"Background: Error generating audio 2: {e}")
            audio_filename2 = None

    # --- Prepare Image Data based on Source ---
    if image_source == 'online' and selected_image_url:
        try:
            print(f"Background: Downloading online image: {selected_image_url}")
            response = requests.get(selected_image_url, timeout=15)
            response.raise_for_status() # Check for HTTP errors
            image_data = response.content
            image_data_b64 = base64.b64encode(image_data).decode('utf-8')
            # Determine extension
            content_type = response.headers.get('content-type', '').lower()
            if 'jpeg' in content_type or 'jpg' in content_type: ext = '.jpg'
            elif 'png' in content_type: ext = '.png'
            elif 'gif' in content_type: ext = '.gif'
            else: ext = os.path.splitext(selected_image_url)[1] or '.jpg' # Guess from URL or default
            image_filename = f"_image_{note_id}{ext}"
            print(f"Background: Prepared online image: {image_filename}")
        except Exception as e:
            print(f"Background: Error processing online image {selected_image_url}: {e}")
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
            image_filename = None
            image_data_b64 = None

    elif image_source == 'clipboard' and pasted_image_obj:
        try:
            print("Background: Processing pasted image...")
            buffer = io.BytesIO()
            save_format = 'PNG' # Default to PNG
            try:
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
            image_filename = None
            image_data_b64 = None

    return audio_filename1, audio_filename2, image_filename, image_data_b64

def update_anki_note_background(note_id, word, sentence1_jp, sentence1_en, sentence2_jp, sentence2_en, image_source, selected_image_url, selected_local_path, pasted_image_obj, target_deck_name):
    """
    Runs in background thread: Prepares data and updates Anki note.
    """
    try:
        print(f"Background: Starting processing for note {note_id}")
        # 1. Prepare Audio and Image data
        audio1, audio2, img_filename, img_data_b64 = _prepare_anki_data(
            note_id, sentence1_jp, sentence2_jp, image_source, selected_image_url, selected_local_path, pasted_image_obj
        )

        # 2. Prepare other fields (HTML, URL) using utils
        sentence1_jp_html = utils.generate_furigana_html(sentence1_jp) if sentence1_jp else ""
        sentence2_jp_html = utils.generate_furigana_html(sentence2_jp) if sentence2_jp else ""
        url = f"https://jisho.org/search/{word}" if word else ""

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
        
        move_note_to_deck(note_id, target_deck_name)

    except Exception as e:
        # Log any error during preparation or update
        print(f"Background: FAILED processing/updating note {note_id}: {e}")
        # Optionally return failure status

def start_anki_update_thread(note_id, word, sentence1_jp, sentence1_en, sentence2_jp, sentence2_en, image_source, selected_image_url, selected_local_path, pasted_image_obj, target_deck_name):
    """Starts the background thread for updating Anki."""
    update_thread = threading.Thread(
        target=update_anki_note_background,
        args=(
            note_id, word,
            sentence1_jp, sentence1_en,
            sentence2_jp, sentence2_en,
            image_source, selected_image_url,
            selected_local_path, pasted_image_obj,
            target_deck_name
        ),
        daemon=True # Allows the main program to exit even if this thread is running
    )
    update_thread.start()
    print(f"Started background update thread for note {note_id}")

# --- Connection Status Check ---

def check_anki_connection_status():
    """
    Checks connection to AnkiConnect.
    Returns a tuple: (status_text, status_color)
    """
    try:
        # Use a lightweight request like 'version'
        get_anki_data.invoke('version')
        return ("Anki: Connected", "green")
    except Exception:
        return ("Anki: Disconnected", "red")

import requests

# Configuration
ANKI_CONNECT_URL = "http://localhost:8765"

def get_deck_info(deck_name):
    # Get all cards in the deck
    note_ids = invoke('findNotes', query=f'deck:"{deck_name}"')['result']
    
    # Count total cards
    total_notes = len(note_ids)

    #all Cards
    all_notes = invoke('notesInfo', notes=note_ids)['result']
    
    return {
        "total_notes": total_notes,
        "allNotes": all_notes
    }

def invoke(action, **params):
    response = requests.post(ANKI_CONNECT_URL, json={'action': action, 'version': 6, 'params': params})
    response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    result = response.json()
    if result.get('error') is not None:
        raise Exception(f"AnkiConnect Error: {result['error']}")
    return result

def store_media_file(filename: str, data_b64: str):
    """
    Stores a file (e.g., image or audio) in Anki's media collection.

    Args:
        filename: The desired filename for the media in Anki.
        data_b64: Base64 encoded string of the file content.

    Returns:
        The result from AnkiConnect.
    """
    print(f"Storing media file: {filename}")
    return invoke("storeMediaFile", filename=filename, data=data_b64)


def update_note_full(note_id: int, sentence1_jp_html: str, sentence1_en: str,
                     sentence2_jp_html: str, sentence2_en: str, url: str,
                     audio1_filename: str | None, audio2_filename: str | None,
                     image_filename: str | None, image_data_b64: str | None):
    """
    Updates multiple fields of an Anki note, including storing an image if provided.

    Args:
        note_id: The ID of the note to update.
        sentence1_jp_html: Sentence 1 Japanese HTML (with furigana).
        sentence1_en: Sentence 1 English translation.
        sentence2_jp_html: Sentence 2 Japanese HTML (with furigana).
        sentence2_en: Sentence 2 English translation.
        url: URL (e.g., Jisho link).
        audio1_filename: Filename for sentence 1 audio (or None).
        audio2_filename: Filename for sentence 2 audio (or None).
        image_filename: Filename for the image (or None).
        image_data_b64: Base64 encoded image data (or None).
    """
    # 1. Store the image file if data is provided
    image_stored_successfully = False # Flag to track storage success
    if image_filename and image_data_b64:
        try:
            store_media_file(filename=image_filename, data_b64=image_data_b64)
            print(f"Successfully stored image: {image_filename}")
            image_stored_successfully = True # Set flag on success
        except Exception as e:
            print(f"Error storing image {image_filename}: {e}")
            # Keep image_stored_successfully as False

    # 2. Prepare the fields dictionary for update
    image_html = f'<img src="{image_filename}">' if image_stored_successfully else "" # Construct tag only if stored

    fields_to_update = {
        "Sentence": sentence1_jp_html,
        "SentenceMeaning": sentence1_en,
        "Sentence2": sentence2_jp_html,
        "Sentence2Meaning": sentence2_en,
        "Link2": url,
        "Image": image_html # Use the conditionally constructed tag
    }

    # Add audio fields only if filenames are provided
    if audio1_filename:
        fields_to_update["SentenceAudio"] = f"[sound:{audio1_filename}]"
    else:
        # Optional: Clear the field if no audio, or leave it as is?
        # fields_to_update["SentenceAudio"] = ""
        pass # Leaving it as is for now

    if audio2_filename:
        fields_to_update["Sentence2Audio"] = f"[sound:{audio2_filename}]"
    else:
        # fields_to_update["Sentence2Audio"] = ""
        pass

    # 3. Update the note fields
    print(f"Updating note {note_id} fields...")
    update_result = invoke("updateNoteFields", note={"id": note_id, "fields": fields_to_update})
    print(f"Update result for note {note_id}: {update_result}")
    return update_result

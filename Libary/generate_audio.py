import requests
import re
import base64

# Configuration
ANKI_CONNECT_URL = "http://localhost:8765"
DECK_NAME = "Wörter(aus Wörterbuch)"
TTS_URL = "http://localhost:5050/v1/audio/speech"

def get_deck_info():
    # Get all cards in the deck
    note_ids = invoke('findNotes', query=f'deck:"{DECK_NAME}"')['result']
    
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
    return response.json()

def save_TTS(input_text, output_name):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your_api_key_here"
    }
    payload = {
        "model": "tts-1",
        "input": input_text,
        "voice": "ja-JP-KeitaNeural"
    }

    response = requests.post(TTS_URL, headers=headers, json=payload)

    if response.status_code == 200:
        with open("speech.mp3", "wb") as f:
            f.write(response.content)
        print("Audio saved as speech.mp3")
    else:
        print(f"Request failed with status {response.status_code}: {response.text}")

def create_TTS(input_text):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your_api_key_here"
    }
    payload = {
        "model": "tts-1",
        "input": input_text,
        "voice": "ja-JP-KeitaNeural",
        "speed": 0.8
    }
    response = requests.post(TTS_URL, headers=headers, json=payload)
    if response.status_code == 200:
        return response.content  # Return audio bytes directly
    else:
        print(f"TTS request failed with status {response.status_code}: {response.text}")
        return None

def remove_illegal_filename_chars(input_str, replace_with=""):
    """
    Removes characters that are illegal in filenames on Windows, Linux, and MacOS.
    
    :param input_str: The input string to clean.
    :param replace_with: The character(s) to replace illegal characters with (default is empty string).
    :return: A cleaned string with illegal characters removed.
    """
    # Define illegal characters for Windows, Linux, and MacOS
    illegal_chars_windows = r'<>:"/\|?*'  # Windows illegal characters
    illegal_chars_unix = r'/'             # Linux/Unix illegal character
    illegal_chars_mac = r':'              # MacOS illegal character
    
    # Combine all illegal characters into a regex pattern
    illegal_chars_pattern = f'[{re.escape(illegal_chars_windows + illegal_chars_unix + illegal_chars_mac)}]'
    
    # Remove illegal characters using regex
    cleaned_str = re.sub(illegal_chars_pattern, replace_with, input_str)
    
    # Remove control characters (ASCII 0-31)
    cleaned_str = re.sub(r'[\x00-\x1F\x7F]', replace_with, cleaned_str)
    
    return cleaned_str   

def update_note_audio(note_id, sentence_text, output_filename):
    """
    Generates TTS audio for a sentence (without saving to disk), encodes it,
    stores it in Anki via AnkiConnect, and updates the note's Audio field.
    """
    # Get audio data from TTS service
    audio_data = create_TTS(sentence_text)
    if audio_data is None:
        return

    # Base64-encode the audio data for AnkiConnect
    import base64
    b64_data = base64.b64encode(audio_data).decode('utf-8')

    # Store the media file in Anki's media collection
    media_result = invoke("storeMediaFile", filename="_"+output_filename, data=b64_data)
    #print(f"Media file store result for note {note_id}: {media_result}")

    # Update the note's "Audio" field with the sound reference (e.g., [sound:filename.mp3])
    update_result = invoke("updateNoteFields", note={"id": note_id, "fields": {"Audio": f"[sound:{output_filename}]"}})
    #print(f"Note update result for note {note_id}: {update_result}")

def stor_note_audio_in_anki(sentence_text, output_filename):
    """
    Generates TTS audio for a sentence (without saving to disk), encodes it,
    stores it in Anki via AnkiConnect, and updates the note's Audio field.
    """
    # Get audio data from TTS service
    audio_data = create_TTS(sentence_text)
    if audio_data is None:
        return

    # Base64-encode the audio data for AnkiConnect
    import base64
    b64_data = base64.b64encode(audio_data).decode('utf-8')

    # Store the media file in Anki's media collection
    media_result = invoke("storeMediaFile", filename=output_filename, data=b64_data)
    print(media_result)
    
    return output_filename

if __name__ == "__main__":
    info = get_deck_info()
    print(f"Deck: {DECK_NAME}")
    
    # (Optional) print a sample of the deck info
    print("\nSample Note:")
    for i, card in enumerate(info['allNotes'], 1):
        print(f"\nCard {i}:")
        print(card)
        if i > 4: break

    # Process each note: if it has a Sentence field, generate and attach audio.
    for card in info['allNotes']:
        # Retrieve the sentence text from the note (adjust field name if necessary)
        sentence_text = card['fields'].get('Sentence', {}).get('value', '').strip()
        if sentence_text:
            note_id = card['noteId']
            # Use a sanitized version of part of the sentence or note id for a unique filename.
            # Here we simply use the note id.
            output_filename = f"audio_{note_id}.mp3"
            update_note_audio(note_id, sentence_text, output_filename)
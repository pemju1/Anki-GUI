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
    return response.json()

def update_note_sentence_tts(note_id, jp1, eng1, jp2, eng2, jisho_url, output_filename, output_filename2):
    # Update the note's "Audio" field with the sound reference (e.g., [sound:filename.mp3])
    update_result = invoke("updateNoteFields", note={"id": note_id, "fields": {"SentenceAudio": f"[sound:{output_filename}]", "Sentence2Audio": f"[sound:{output_filename2}]", "Sentence": jp1, "SentenceMeaning": eng1,"Sentence2": jp2, "Sentence2Meaning": eng2, "Link2":jisho_url}})
    # print(update_result)
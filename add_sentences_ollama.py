import Libary.sentance_ai as sentence
import Libary.generate_audio as TTS
import Libary.get_anki_data

import requests
from tqdm import tqdm  # Import tqdm for the progress bar
import pykakasi

# Configuration
ANKI_CONNECT_URL = "http://localhost:8765"
# DECK_NAME = "Japanisch Wörter"
DECK_NAME = "Wörter(aus Wörterbuch)"

def write_to_txt(path,liste):
    with open(path, 'w', encoding='utf-8') as file:
        if type(liste)==list:
            for i in range(len(liste)):
                element = liste[i]
                if i != 0: file.write("\n")
                if element!=None: file.write(", ".join(map(str, element))) 
        else: file.write(str(liste))

def update_note_sentence_tts(note_id, jp1, eng1, jp2, eng2, jisho_url, output_filename, output_filename2):
    # Update the note's "Audio" field with the sound reference (e.g., [sound:filename.mp3])
    update_result = get_anki_data.invoke("updateNoteFields", note={"id": note_id, "fields": {"SentenceAudio": f"[sound:{output_filename}]", "Sentence2Audio": f"[sound:{output_filename2}]", "Sentence": jp1, "SentenceMeaning": eng1,"Sentence2": jp2, "Sentence2Meaning": eng2, "Link2":jisho_url}})
    # print(update_result)

def generate_furigana_html(sentence: str) -> str:
    kks = pykakasi.kakasi()
    result = kks.convert(sentence)
    output = ""
    for token in result:
        orig = token["orig"]
        hira = token["hira"]
        # Check if the token contains any Kanji and if the reading differs.
        if any('\u4e00' <= c <= '\u9fff' for c in orig) and orig != hira:
            output += f"<ruby>{orig}<rt>{hira}</rt></ruby>"
        else:
            output += orig
    return output

if __name__ == "__main__":
    info = get_anki_data.get_deck_info(DECK_NAME)
    print(f"Deck: {DECK_NAME}")

    # (Optional) print a sample of the deck info
    print("\nSample Note:")
    for i, card in enumerate(info['allNotes'], 1):
        print(f"\nCard {i}:")
        print(card)
        if i > 4: break
    
    total_notes = info['total_notes']
    # Process each note: if it has a Sentence field, generate and attach audio.
    progress_bar = tqdm(total=total_notes, desc="Adding Sentences", unit="note", smoothing=0)  # Initialize progress bar
    with open("fehler.txt", "r", encoding="utf-8") as id_file:
        fehler = [line.strip().split(", ") for line in id_file.readlines()]
    print(fehler)
    notes = info['allNotes']
    i = 0-1 #ceep the -1
    progress_bar.update(i+1)
    while i<=len(notes)-2:
        i+=1
        note = notes[i]
        write_to_txt("fehler.txt", fehler)
        write_to_txt("index.txt", i)

        # Retrieve the sentence text from the note (adjust field name if necessary)
        word = note['fields'].get('Japanese', {}).get('value', '').strip()
        url = f"https://jisho.org/search/{word}"
        note_id = note['noteId']
        try: meaning = note['fields']["Meaning"]["value"]
        except: 
            fehler.append([note_id, word])
            progress_bar.update(1)
            continue
        try:japanese1, english1, japanese2, english2 = sentence.ollama_sentances(word, meaning, "deepseek-r1:8b")
        except: 
            fehler.append([note_id, word])
            progress_bar.update(1)
            print("Fehler AI")
            continue
        if all(x is None for x in (japanese1, english1, japanese2, english2)):
            fehler.append([note_id, word])
            progress_bar.update(1)
            print("Keine 2 Sätze")
            continue

        print(note_id) 
        output_filename1 = f"_audio_{note_id}_1.mp3"
        TTS.stor_note_audio_in_anki(japanese1, output_filename1)

        if japanese2 != None and japanese2!="":
            output_filename2 = f"_audio_{note_id}_2.mp3"
            TTS.stor_note_audio_in_anki(japanese2, output_filename2)
        else:
            output_filename2 = ""

        japanese1 = generate_furigana_html(japanese1)
        if japanese2 != None and japanese2!="":
            japanese2 = generate_furigana_html(japanese2)
        update_note_sentence_tts(note_id, japanese1, english1, japanese2, english2, url, output_filename1, output_filename2)

        progress_bar.update(1)  # Update progress bar for each note 
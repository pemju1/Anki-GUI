import requests
import subprocess
import sys
import time
import os
import base64
from gui.utils import remove_brackets  

# Configuration
ANKI_CONNECT_URL        = "http://localhost:8765"
TTS_URL                 = "http://localhost:5050/v1/audio/speech"
SERVER_SCRIPT_PATH      = r"C:\Users\samue\Desktop\Pogramierung\Python Projekte\Anki\TTS\openai-edge-tts\app\server.py"
SERVER_STARTUP_WAIT_TIME = 5  # seconds

def start_tts_server():
    """
    Launches the TTS server script in the background, waits for it to spin up.
    """
    # Make sure the script exists
    if not os.path.isfile(SERVER_SCRIPT_PATH):
        raise FileNotFoundError(f"TTS server script not found at {SERVER_SCRIPT_PATH}")
    # Use the same Python interpreter that’s running this script
    cmd = [sys.executable, SERVER_SCRIPT_PATH]
    kwargs = {
        "cwd": os.path.dirname(SERVER_SCRIPT_PATH),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }

    if os.name == "nt":
        # Only DETACHED_PROCESS, so we truly detach without creating a new console.
        DETACHED_PROCESS = 0x00000008
        kwargs["creationflags"] = DETACHED_PROCESS

    subprocess.Popen(cmd, **kwargs)
    # Give it a moment to start up
    print(f"Starting TTS server, waiting {SERVER_STARTUP_WAIT_TIME}s...")
    time.sleep(SERVER_STARTUP_WAIT_TIME)

def create_TTS(input_text):
    """
    Sends text to the TTS server and returns raw audio bytes.
    If the server isn't reachable, starts it and retries once.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your_api_key_here"
    }
    payload = {
        "model": "tts-1",
        "input": remove_brackets(input_text),
        "voice": "ja-JP-KeitaNeural",
        "speed": 0.8
    }

    try:
        response = requests.post(TTS_URL, headers=headers, json=payload)
    except requests.exceptions.ConnectionError:
        # Try to start the server and retry once
        start_tts_server()
        response = requests.post(TTS_URL, headers=headers, json=payload)

    if response.status_code == 200:
        return response.content  # audio bytes
    else:
        print(f"TTS request failed: {response.status_code} — {response.text}")
        return None

def invoke(action, **params):
    response = requests.post(
        ANKI_CONNECT_URL,
        json={'action': action, 'version': 6, 'params': params}
    )
    return response.json()

def store_note_audio_in_anki(sentence_text, output_filename):
    """
    Generates TTS audio for a sentence (without saving to disk), encodes it,
    stores it in Anki via AnkiConnect.
    """
    audio_data = create_TTS(sentence_text)
    if not audio_data:
        print("❌ TTS failed — skipping this note.")
        return None

    # Base64-encode for AnkiConnect
    b64_data = base64.b64encode(audio_data).decode('utf-8')
    result = invoke("storeMediaFile", filename=output_filename, data=b64_data)
    print("Anki media store result:", result)
    return output_filename

if __name__ == "__main__":
    input_string = "今日(きょう)はここに朝ご飯(あさごはん)を食べる(たべる)。"
    clean_string = remove_brackets(input_string)

    print(f"Input:  {input_string}")
    print(f"Clean Sentance {clean_string}")
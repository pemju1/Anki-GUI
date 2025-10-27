import requests
import Libary.sentance_ai as sentence_ai
from Libary.sentance_ai import query_ollama, read_txt # For deck recommendation
import re # For parsing deck recommendation
import os # For constructing prompt path

OLLAMA_API_URL = "http://localhost:11434" # Base URL for Ollama API checks

def get_ollama_models():
    """Fetches the list of available Ollama models."""
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
        response.raise_for_status()
        models_data = response.json()
        available_models = sorted([m['name'] for m in models_data.get('models', [])])
        print(f"Fetched Ollama models: {available_models}")
        return available_models
    except requests.exceptions.RequestException as e:
         print(f"Error fetching Ollama models: {e}")
         return [] # Return empty list on error
    except Exception as e:
        print(f"Unexpected error fetching Ollama models: {e}")
        return []

def check_ollama_connection_status():
    """
    Checks connection to the Ollama API.
    Returns a tuple: (status_text, status_color)
    """
    try:
        # Check if the base Ollama API endpoint is reachable
        response = requests.get(OLLAMA_API_URL, timeout=2) # Short timeout
        response.raise_for_status() # Check for HTTP errors
        # Could add a more specific check like /api/tags if needed
        return ("Ollama: Online", "green")
    except requests.exceptions.RequestException:
        return ("Ollama: Offline", "red")
    except Exception as e:
         # Catch other potential errors
         print(f"Unexpected error checking Ollama connection: {e}")
         return ("Ollama: Error", "red")

def generate_sentences(word, meaning, model_name, reading):
    """
    Generates two Japanese sentences and their English translations using Ollama.
    Returns a tuple: (jp1, en1, jp2, en2) or raises an exception on error.
    """
    if not model_name:
        raise ValueError("Ollama model name cannot be empty.")
    if not word:
        raise ValueError("Word cannot be empty for sentence generation.")

    word = word.replace("ꜜ", "").replace("ꜛ", "")
    try:
        # Call the function from the library module
        jp1, en1, jp2, en2 = sentence_ai.ollama_sentances(word, meaning, model_name, reading)
        # Process and convert sentences to plain text (handle potential None).
        plain_jp1 = jp1 if jp1 else ""
        plain_jp2 = jp2 if jp2 else ""
        plain_en1 = en1 if en1 else ""
        plain_en2 = en2 if en2 else ""
        print(f"Generated sentences for '{word}' using model '{model_name}'")
        print(f"Japanese1: {plain_jp1} \n Japanese2: {plain_jp2}")

        return plain_jp1, plain_en1, plain_jp2, plain_en2
    except Exception as e:
        print(f"Error during sentence generation with Ollama: {e}")
        raise # Re-raise the exception to be handled by the caller (UI)

def get_recommended_deck(vocabulary: str, dictionary_meaning: str, deck_list: list, model_name: str):
    """
    Recommends a deck from the provided list based on vocabulary and meaning using Ollama.
    Returns the recommended deck name (str) or None if an error occurs or parsing fails.
    """
    if not model_name:
        raise ValueError("Ollama model name cannot be empty for deck recommendation.")
    if not vocabulary:
        raise ValueError("Vocabulary cannot be empty for deck recommendation.")
    if not deck_list:
        raise ValueError("Deck list cannot be empty for deck recommendation.")

    try:
        # Construct the path to the prompt file relative to the current script or a known base
        # Assuming this script (ollama_handler.py) is in the 'gui' directory,
        # and Prompts is a sibling to 'gui'.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(current_dir) # Go up one level to the project root
        prompt_file_path = os.path.join(base_dir, "Prompts", "target_deck_prompt.txt")

        deck_prompt_template = read_txt(prompt_file_path)

        # Format the deck list into a string
        formatted_deck_list = ", ".join(deck_list)

        user_prompt_content = deck_prompt_template.format(
            vocabulary=vocabulary,
            dictionary=dictionary_meaning,
            deck_list=formatted_deck_list
        )

        # Using an empty system prompt as the target_deck_prompt is self-contained
        raw_response = query_ollama(system_prompt="", user_input=user_prompt_content, model=model_name)

        if raw_response:
            match = re.search(r"<deck>(.*?)</deck>", raw_response, re.DOTALL | re.IGNORECASE)
            if match:
                recommended_deck = match.group(1).strip()
                print(f"Ollama recommended deck: '{recommended_deck}' for vocabulary '{vocabulary}'")
                return recommended_deck
            else:
                print(f"Could not parse deck name from Ollama response: {raw_response}")
                return None
        else:
            print("Ollama returned an empty response for deck recommendation.")
            return None

    except FileNotFoundError:
        print(f"Error: Deck recommendation prompt file not found at {prompt_file_path}")
        raise # Re-raise so UI can be aware
    except Exception as e:
        print(f"Error during Ollama deck recommendation: {e}")
        # Optionally, could return a specific error or None
        # For now, re-raising to see how the UI handles it or if specific handling is needed.
        raise

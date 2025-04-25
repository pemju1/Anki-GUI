import requests
import Libary.sentance_ai as sentence_ai

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

def generate_sentences(word, meaning, model_name):
    """
    Generates two Japanese sentences and their English translations using Ollama.
    Returns a tuple: (jp1, en1, jp2, en2) or raises an exception on error.
    """
    if not model_name:
        raise ValueError("Ollama model name cannot be empty.")
    if not word:
        raise ValueError("Word cannot be empty for sentence generation.")

    try:
        # Call the function from the library module
        jp1, en1, jp2, en2 = sentence_ai.ollama_sentances(word, meaning, model_name)
        # Process and convert sentences to plain text (handle potential None).
        plain_jp1 = jp1 if jp1 else ""
        plain_jp2 = jp2 if jp2 else ""
        plain_en1 = en1 if en1 else ""
        plain_en2 = en2 if en2 else ""
        print(f"Generated sentences for '{word}' using model '{model_name}'")
        return plain_jp1, plain_en1, plain_jp2, plain_en2
    except Exception as e:
        print(f"Error during sentence generation with Ollama: {e}")
        raise # Re-raise the exception to be handled by the caller (UI)

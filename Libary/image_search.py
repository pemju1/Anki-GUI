import requests
import json
import os

# --- Configuration ---
# TODO: Replace with your actual API keys.
# You can get keys from:
# Unsplash: https://unsplash.com/developers
# Pexels: https://www.pexels.com/api/
UNSPLASH_ACCESS_KEY = "nknvLNDVGHzHCzfIduWfAtUz0P6_q1DW9UgXBkntBIo"
PEXELS_API_KEY = "jWTTHq2Q4aAbWuJJtXc3NHKtzv1p6sq0iCwtQiRJqF4V1UoyCicwcbj0"

# --- Unsplash Search ---
def search_unsplash(query: str, count: int = 5) -> list[tuple[str, str]]:
    """
    Searches Unsplash for images based on a query.

    Args:
        query: The search term.
        count: The maximum number of results to return.

    Returns:
        A list of tuples, where each tuple contains (thumbnail_url, full_url).
        Returns an empty list if the API key is missing or an error occurs.
    """
    if not UNSPLASH_ACCESS_KEY or UNSPLASH_ACCESS_KEY == "YOUR_UNSPLASH_ACCESS_KEY":
        print("Warning: Unsplash Access Key is missing in image_search.py")
        return []

    url = "https://api.unsplash.com/search/photos"
    headers = {
        "Accept-Version": "v1",
        "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"
    }
    params = {
        "query": query,
        "per_page": count,
        "orientation": "landscape" # Prefer landscape images
    }

    results = []
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()

        for item in data.get("results", []):
            urls = item.get("urls", {})
            thumb_url = urls.get("thumb")
            full_url = urls.get("regular") # Use 'regular' for decent quality without being huge
            if thumb_url and full_url:
                results.append((thumb_url, full_url))

    except requests.exceptions.RequestException as e:
        print(f"Error searching Unsplash: {e}")
    except json.JSONDecodeError:
        print("Error decoding Unsplash JSON response.")
    except Exception as e:
        print(f"An unexpected error occurred during Unsplash search: {e}")

    return results

# --- Pexels Search ---
def search_pexels(query: str, count: int = 5) -> list[tuple[str, str]]:
    """
    Searches Pexels for images based on a query.

    Args:
        query: The search term.
        count: The maximum number of results to return.

    Returns:
        A list of tuples, where each tuple contains (thumbnail_url, full_url).
        Returns an empty list if the API key is missing or an error occurs.
    """
    if not PEXELS_API_KEY or PEXELS_API_KEY == "YOUR_PEXELS_API_KEY":
        print("Warning: Pexels API Key is missing in image_search.py")
        return []

    url = "https://api.pexels.com/v1/search"
    headers = {
        "Authorization": PEXELS_API_KEY
    }
    params = {
        "query": query,
        "per_page": count,
        "orientation": "landscape"
    }

    results = []
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        for photo in data.get("photos", []):
            src = photo.get("src", {})
            # Pexels provides various sizes, let's pick 'tiny' for thumb and 'large' for full
            thumb_url = src.get("tiny")
            full_url = src.get("large")
            if thumb_url and full_url:
                results.append((thumb_url, full_url))

    except requests.exceptions.RequestException as e:
        print(f"Error searching Pexels: {e}")
    except json.JSONDecodeError:
        print("Error decoding Pexels JSON response.")
    except Exception as e:
        print(f"An unexpected error occurred during Pexels search: {e}")

    return results

# --- Combined Search ---
def search_images(query: str, count_per_source: int = 3) -> list[tuple[str, str]]:
    """
    Searches multiple sources for images.

    Args:
        query: The search term.
        count_per_source: Max results from each source.

    Returns:
        A combined list of (thumbnail_url, full_url) tuples from all sources.
    """
    all_results = []
    all_results.extend(search_unsplash(query, count_per_source))
    all_results.extend(search_pexels(query, count_per_source))

    # Optional: Add more sources here if needed
    # all_results.extend(search_pixabay(query, count_per_source))

    # Optional: Shuffle or limit total results if desired
    # random.shuffle(all_results)
    # return all_results[:max_total_results]

    return all_results

if __name__ == '__main__':
    # Example usage (for testing)
    search_term = "猫" # Japanese for cat
    print(f"Searching for '{search_term}'...")

    unsplash_results = search_unsplash(search_term, 3)
    print("\n--- Unsplash Results ---")
    if unsplash_results:
        for i, (thumb, full) in enumerate(unsplash_results):
            print(f"{i+1}. Thumb: {thumb}\n   Full:  {full}")
    else:
        print("No results or API key missing.")

    pexels_results = search_pexels(search_term, 3)
    print("\n--- Pexels Results ---")
    if pexels_results:
        for i, (thumb, full) in enumerate(pexels_results):
            print(f"{i+1}. Thumb: {thumb}\n   Full:  {full}")
    else:
        print("No results or API key missing.")

    combined = search_images(search_term, 3)
    print("\n--- Combined Results ---")
    if combined:
        for i, (thumb, full) in enumerate(combined):
            print(f"{i+1}. Thumb: {thumb}") # Just print thumb for brevity
    else:
        print("No results found from any source or API keys missing.")

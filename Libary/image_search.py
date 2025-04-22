import requests
import json
import os
import re
import math

# --- Configuration ---
# TODO: Replace with your actual API keys.
# You can get keys from:
# Unsplash: https://unsplash.com/developers
# Pexels: https://www.pexels.com/api/
UNSPLASH_ACCESS_KEY = "nknvLNDVGHzHCzfIduWfAtUz0P6_q1DW9UgXBkntBIo"
PEXELS_API_KEY = "jWTTHq2Q4aAbWuJJtXc3NHKtzv1p6sq0iCwtQiRJqF4V1UoyCicwcbj0"

def extract_meanings(input_str : str):
    diffren_meanings = input_str.split("<br>", -1)

    meanings = []
    for meaning in diffren_meanings:
        meaning = re.sub(r'^\d+\.\s*', '', meaning)# Split the input string after the first occurrence of "1."
        meaning_s = meaning.split(",", 1)
        if len(meaning_s) < 2:
            meanings.append(meaning.strip())
        else:
            meanings.append(meaning_s[0].strip())

    return meanings

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
        #"orientation": "landscape" # Prefer landscape images
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
def search_images(query: str, count_per_source: int = 3, num_meanings_per_source: int = 1) -> list[tuple[str, str]]:
    """
    Searches multiple sources for images based on extracted meanings, limiting total results per source.

    Args:
        query: The raw input string containing meanings (e.g., from Anki notes).
        count_per_source: Max total unique results desired *per source*.
        num_meanings_per_source: How many meanings to extract and search for (default is 1).

    Returns:
        A combined list of unique (thumbnail_url, full_url) tuples.
    """
    
    # 1. Extract meanings
    try:
        # Assuming with_brackets=False is appropriate based on the function's current state
        meanings = extract_meanings(query) 
    except Exception as e:
        print(f"Error extracting meanings: {e}")
        meanings = [query] # Fallback to using the original query if extraction fails

    # 2. Select meanings to search
    if not meanings:
        print("Warning: No meanings extracted or provided.")
        return []
        
    meanings_to_search = meanings[:num_meanings_per_source]
    print(f"Searching for meanings: {meanings_to_search}")

    # 3. Calculate request count per meaning
    num_meanings = len(meanings_to_search)
    request_count_per_meaning = 0
    if num_meanings > 0:
        # Ensure request_count_per_meaning is at least 1 if count_per_source > 0
        request_count_per_meaning = max(1, math.ceil(count_per_source / num_meanings)) if count_per_source > 0 else 0
        print(f"Requesting up to {request_count_per_meaning} images per meaning for each source.")
    else:
         print("No meanings to search.")
         return [] # Return early if no meanings

    # 4. Gather results per source
    raw_unsplash_results = []
    raw_pexels_results = []
    
    if request_count_per_meaning > 0: # Only search if we need results
        for meaning in meanings_to_search:
            print(f"  Searching Unsplash for: '{meaning}'")
            raw_unsplash_results.extend(search_unsplash(meaning, request_count_per_meaning))
            
            print(f"  Searching Pexels for: '{meaning}'")
            raw_pexels_results.extend(search_pexels(meaning, request_count_per_meaning))
            # Add other sources similarly

    # 5. De-duplicate and truncate per source
    final_unsplash = []
    seen_unsplash_urls = set()
    for thumb, full in raw_unsplash_results:
        if full not in seen_unsplash_urls:
            final_unsplash.append((thumb, full))
            seen_unsplash_urls.add(full)
            if len(final_unsplash) >= count_per_source:
                break # Stop once we reach the limit for this source
                
    final_pexels = []
    seen_pexels_urls = set()
    for thumb, full in raw_pexels_results:
        if full not in seen_pexels_urls:
            final_pexels.append((thumb, full))
            seen_pexels_urls.add(full)
            if len(final_pexels) >= count_per_source:
                break

    # 6. Combine
    all_results = final_unsplash + final_pexels
    # Optionally shuffle combined results?
    # import random
    # random.shuffle(all_results) 

    print(f"Returning {len(all_results)} total unique image results ({len(final_unsplash)} Unsplash, {len(final_pexels)} Pexels).")
    return all_results


if __name__ == '__main__':
    # Example usage (for testing)
    # Test case 1: Single meaning implicitly
    search_term_1 = "猫" # Japanese for cat
    print(f"\nSearching for '{search_term_1}' (default meanings=1)...")
    combined_1 = search_images(search_term_1, count_per_source=4)
    if combined_1:
        for i, (thumb, full) in enumerate(combined_1):
            print(f"{i+1}. Thumb: {thumb}") 
    else:
        print("No results found.")

    # Test case 2: Multiple meanings string
    search_term_2 = "1. change, transform<br>2. move<br>3. be different"
    print(f"\nSearching for '{search_term_2}' (meanings=1)...")
    combined_2 = search_images(search_term_2, count_per_source=3, num_meanings_per_source=1)
    if combined_2:
        for i, (thumb, full) in enumerate(combined_2):
            print(f"{i+1}. Thumb: {thumb}")
    else:
        print("No results found.")
        
    print(f"\nSearching for '{search_term_2}' (meanings=2)...")
    combined_3 = search_images(search_term_2, count_per_source=4, num_meanings_per_source=2)
    if combined_3:
        for i, (thumb, full) in enumerate(combined_3):
            print(f"{i+1}. Thumb: {thumb}")
    else:
        print("No results found.")

    print(f"\nSearching for '{search_term_2}' (meanings=3, count=2)...")
    combined_4 = search_images(search_term_2, count_per_source=2, num_meanings_per_source=3)
    if combined_4:
        for i, (thumb, full) in enumerate(combined_4):
            print(f"{i+1}. Thumb: {thumb}")
    else:
        print("No results found.")
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

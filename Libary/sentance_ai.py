import requests
import json, re


model_names = ["gemma3:latest", "gemma3:12b", "llama3.1:8b", "deepseek-r1:14b", "deepseek-r1:8b"]

def read_txt(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def query_ollama(system_prompt, user_input, model="gemma3:latest"):
    url = "http://localhost:11434/api/chat"  # Replace with your Ollama model API endpoint
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": user_input
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)

        full_response = ""
        for line in response.iter_lines():
            if line:  # filter out keep-alive new lines
                chunk = line.decode('utf-8')
                try:
                    json_chunk = json.loads(chunk)
                    content = json_chunk.get("message", {}).get("content", "")
                    full_response += content
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}")
        
        return full_response.strip()
    
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.text}")
    except Exception as err:
        print(f"An error occurred: {err}")

def ollama_sentances(word, dictionary, model_name, user_input=None):    
    system_prompt = read_txt(r"example_sentances\system_prompt.txt")
    if user_input is None:
        user_input = read_txt(r"example_sentances\user_prompt.txt").format(vocabulary=word,dictionary=dictionary)

    while True:
        example_sentances_list = []
        translations_list = []

        result = query_ollama(system_prompt, user_input, model_name)
        example_sentences = re.findall(r'<answer>(.*?)</answer>', result, re.DOTALL)
        translations = re.findall(r'<translation>(.*?)</translation>', result, re.DOTALL)

        if example_sentences:
            for sentence in example_sentences:
                example_sentances_list.append(sentence)
        if translations:
            for translation in translations:
                translations_list.append(translation)
        
        if len(example_sentances_list) == len(translations_list) == 2:
            return example_sentances_list[0], translations_list[0], example_sentances_list[1], translations_list[1]



if __name__ == "__main__":
    # Example usage
    system_prompt = read_txt(r"example_sentances\system_prompt.txt")
    vocabulary = "回る"
    dictionary = "1. to turn, to rotate, to revolve, to spin 2. to go around, to circle, to revolve around, to orbit 3. to make the rounds (of), to go around (several places), to travel around, to make a tour of, to patrol 4. to go by way of, to go via, to stop by (on the way), to take a roundabout route, to make a detour \n Now Provide an example sentence for 回る. form: <answer>(japanese example sentence)</answer>"
    user_input = read_txt(r"example_sentances\user_prompt.txt").format(vocabulary=vocabulary,dictionary=dictionary)

    result = query_ollama(system_prompt, user_input, model_names[4])
    print(result)
    example_sentences = re.findall(r'<answer>(.*?)</answer>', result, re.DOTALL)
    translations = re.findall(r'<translation>(.*?)</translation>', result, re.DOTALL)
    # reading = re.search(r'<furigana>(.*?)</furigana>', result, re.DOTALL)
    if example_sentences:
        for sentence in example_sentences:
            print("Sentence:", sentence)
    else:
        print("No example sentences found in the response.")

    if translations:
        for translation in translations:
            print("Translation:", translation)
    else:
        print("No translations found in the response.")

    

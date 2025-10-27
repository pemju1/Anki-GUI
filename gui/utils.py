import re
import pykakasi

def generate_furigana_html(sentence_str: str, reading = "pykakasi") -> str:
    """
    Parses a string with furigana in parentheses (e.g., "今日(きょう)")
    and converts it into HTML ruby tags.
    """
    # This improved pattern requires that the annotated text starts with a Kanji.
    # This prevents the regex from greedily capturing preceding hiragana-only
    # particles and words like 「はここに」 or 「を」.
    # - ([\u4e00-\u9fff]...): The first captured group (the base text).
    # - [\u4e00-\u9fff]: Must start with a Kanji.
    # - [\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]*: Followed by any combination of Kanji, Hiragana, or Katakana.
    # - \(([\u3040-\u309f]+)\): The second captured group (the furigana).
    if(not("pykakasi")):
        pattern = r'([\u4e00-\u9fff][\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]*)\(([\u3040-\u309f]+)\)'

        replacement = r'<ruby>\1<rt>\2</rt></ruby>'
        
        return re.sub(pattern, replacement, sentence_str)
    else: 
        kks = pykakasi.kakasi()
        result = kks.convert(sentence_str)
        output = ""
        for token in result:
            orig = token["orig"]
            hira = token["hira"]
            # If there are Kanji characters and the reading differs, add ruby markup.
            if any('\u4e00' <= c <= '\u9fff' for c in orig) and orig != hira:
                output += f"<ruby>{orig}<rt>{hira}</rt></ruby>"
            else:
                output += orig
        return output

def generate_furigana_string(sentence_str: str, reading) -> str:
    """Generates a string with furigana in parentheses."""
    if reading != "pykakasi": return sentence_str
    else:
        print(sentence_str)
        kks = pykakasi.kakasi()
        result = kks.convert(sentence_str)
        output = ""
        for token in result:
            orig = token["orig"]
            hira = token["hira"]
            # If there are Kanji characters and the reading differs, add parentheses markup.
            if any('\u4e00' <= c <= '\u9fff' for c in orig) and orig != hira:
                output += f"{orig}({hira}) "
            else:
                output += orig
        return output.strip() # Added strip to remove potential trailing space

def remove_brackets(sentence_str: str) -> str:
    """Removes brackets from the input string."""
    pattern = r"\(.*?\)"
    return re.sub(pattern, "", sentence_str)

if __name__ == "__main__":
    input_string = "今日(きょう)はここに朝ご飯(あさごはん)を食べる(たべる)。"
    html_output = generate_furigana_html(input_string)
    clean_string = remove_brackets(input_string)

    print(f"Input:  {input_string}")
    print(f"Output: {html_output}")
    print(f"Clean Sentance {clean_string}")
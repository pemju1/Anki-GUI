import pykakasi

def generate_furigana_html(sentence_str: str) -> str:
    """Generates HTML ruby tags for furigana."""
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

def generate_furigana_string(sentence_str: str) -> str:
    """Generates a string with furigana in parentheses."""
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

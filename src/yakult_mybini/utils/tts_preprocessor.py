import re
import unicodedata
from loguru import logger
from ..translate.translate_interface import TranslateInterface


def tts_filter(
    text: str,
    remove_special_char: bool,
    ignore_brackets: bool,
    ignore_parentheses: bool,
    ignore_asterisks: bool,
    ignore_angle_brackets: bool,
    translator: TranslateInterface | None = None,
) -> str:
    """
    Filter or do anything to the text before TTS generates the audio.
    Changes here do not affect subtitles or LLM's memory. The generated audio is
    the only affected thing.

    Args:
        text (str): The text to filter.
        remove_special_char (bool): Whether to remove special characters.
        ignore_brackets (bool): Whether to ignore text within brackets.
        ignore_parentheses (bool): Whether to ignore text within parentheses.
        ignore_asterisks (bool): Whether to ignore text within asterisks.
        translator (TranslateInterface, optional):
            The translator to use. If None, we'll skip the translation. Defaults to None.

    Returns:
        str: The filtered text.
    """
    try:
        text = filter_code_blocks(text)
    except Exception as e:
        logger.warning(f"Error filtering code blocks: {e}")

    try:
        text = normalize_decimal_numbers(text)
    except Exception as e:
        logger.warning(f"Error normalizing decimal numbers: {e}")

    try:
        text = filter_word_asterisk(text)
    except Exception as e:
        logger.warning(f"Error filtering word asterisk: {e}")

    if ignore_asterisks:
        try:
            text = filter_asterisks(text)
        except Exception as e:
            logger.warning(f"Error ignoring asterisks: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")

    if ignore_brackets:
        try:
            text = filter_brackets(text)
        except Exception as e:
            logger.warning(f"Error ignoring brackets: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")
    if ignore_parentheses:
        try:
            text = filter_parentheses(text)
        except Exception as e:
            logger.warning(f"Error ignoring parentheses: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")
    if ignore_angle_brackets:
        try:
            text = filter_angle_brackets(text)
        except Exception as e:
            logger.warning(f"Error ignoring angle brackets: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")
    if remove_special_char:
        try:
            text = remove_special_characters(text)
        except Exception as e:
            logger.warning(f"Error removing special characters: {e}")
            logger.warning(f"Text: {text}")
            logger.warning("Skipping...")
    if translator:
        try:
            logger.info("Translating...")
            text = translator.translate(text)
            logger.info(f"Translated: {text}")
        except Exception as e:
            logger.critical(f"Error translating: {e}")
            logger.critical(f"Text: {text}")
            logger.warning("Skipping...")

    logger.debug(f"Filtered text: {text}")
    return text


def remove_special_characters(text: str) -> str:
    """
    Filter text to remove all non-letter, non-number, and non-punctuation characters.

    Args:
        text (str): The text to filter.

    Returns:
        str: The filtered text.
    """
    normalized_text = unicodedata.normalize("NFKC", text)

    def is_valid_char(char: str) -> bool:
        category = unicodedata.category(char)
        return (
            category.startswith("L")
            or category.startswith("N")
            or category.startswith("P")
            or char.isspace()
        )

    filtered_text = "".join(char for char in normalized_text if is_valid_char(char))
    return filtered_text


_DIGIT_WORDS_ID = {
    "0": "nol",
    "1": "satu",
    "2": "dua",
    "3": "tiga",
    "4": "empat",
    "5": "lima",
    "6": "enam",
    "7": "tujuh",
    "8": "delapan",
    "9": "sembilan",
}


def normalize_decimal_numbers(text: str) -> str:
    """Replace decimal numbers with spoken Indonesian form.

    - True decimals (e.g. '9.5'): → 'sembilan koma lima'
    - Time format after jam/pukul (e.g. 'Jam 9.30'): → 'jam sembilan tiga puluh'
      Special time rules: 01-09 menit → 'lebih X', 15 menit → 'seperempat'
    """

    def _words(n: str) -> str:
        n = n.lstrip("0") or "0"
        if n == "0":
            return "nol"
        ones_map = {
            "1": "satu",
            "2": "dua",
            "3": "tiga",
            "4": "empat",
            "5": "lima",
            "6": "enam",
            "7": "tujuh",
            "8": "delapan",
            "9": "sembilan",
        }
        tens_map = {
            "10": "sepuluh",
            "11": "sebelas",
            "12": "dua belas",
            "13": "tiga belas",
            "14": "empat belas",
            "15": "lima belas",
            "16": "enam belas",
            "17": "tujuh belas",
            "18": "delapan belas",
            "19": "sembilan belas",
        }
        if n in tens_map:
            return tens_map[n]
        if len(n) == 1:
            return ones_map.get(n, n)
        if len(n) == 2:
            d, o = n[0], n[1]
            prefix = ones_map.get(d, d) + " puluh"
            if o == "0":
                return prefix
            return prefix + " " + ones_map.get(o, o)
        return " ".join(ones_map.get(d, d) for d in n)

    def time_minutes(frac: str) -> str:
        """Convert minutes in time context to spoken Indonesian."""
        val = int(frac.lstrip("0") or "0")
        if 1 <= val <= 9:
            return "lebih " + _words(frac)
        if val == 15:
            return "seperempat"
        return _words(frac)

    def decimal_replacer(m: re.Match) -> str:
        whole = m.group(1)
        frac = m.group(2)
        before = text[max(0, m.start() - 12) : m.start()].lower()
        is_time = bool(re.search(r"(?:jam|pukul)\s*$", before))
        if is_time:
            return _words(whole) + " " + time_minutes(frac)
        whole_words = " ".join(_DIGIT_WORDS_ID.get(d, d) for d in whole if d.isdigit())
        frac_digits = " ".join(_DIGIT_WORDS_ID.get(d, d) for d in frac if d.isdigit())
        return f"{whole_words} koma {frac_digits}"

    result = []
    last_end = 0
    for m in re.finditer(r"(\d+)[.](\d+)", text):
        result.append(text[last_end : m.start()])
        result.append(decimal_replacer(m))
        last_end = m.end()
    result.append(text[last_end:])
    return "".join(result)


def _filter_nested(text: str, left: str, right: str) -> str:
    """
    Generic function to handle nested symbols.

    Args:
        text (str): The text to filter.
        left (str): The left symbol (e.g. '[' or '(').
        right (str): The right symbol (e.g. ']' or ')').

    Returns:
        str: The filtered text.
    """
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    if not text:
        return text

    result = []
    depth = 0
    for char in text:
        if char == left:
            depth += 1
        elif char == right:
            if depth > 0:
                depth -= 1
        else:
            if depth == 0:
                result.append(char)
    filtered_text = "".join(result)
    filtered_text = re.sub(r"\s+", " ", filtered_text).strip()
    return filtered_text


def filter_brackets(text: str) -> str:
    """
    Filter text to remove all text within brackets, handling nested cases.

    Args:
        text (str): The text to filter.

    Returns:
        str: The filtered text.
    """
    return _filter_nested(text, "[", "]")


def filter_parentheses(text: str) -> str:
    """
    Filter text to remove all text within parentheses, handling nested cases.

    Args:
        text (str): The text to filter.

    Returns:
        str: The filtered text.
    """
    return _filter_nested(text, "(", ")")


def filter_angle_brackets(text: str) -> str:
    """
    Filter text to remove all text within angle brackets, handling nested cases.

    Args:
        text (str): The text to filter.

    Returns:
        str: The filtered text.
    """
    return _filter_nested(text, "<", ">")


def filter_code_blocks(text: str) -> str:
    """
    Removes code blocks enclosed within triple backticks (```) from a string.

    Args:
        text: The input string.

    Returns:
        The string with code block content removed.
    """
    filtered_text = re.sub(r"```[\s\S]*?```", "", text)
    filtered_text = re.sub(r"\s+", " ", filtered_text).strip()
    return filtered_text


def filter_word_asterisk(text: str) -> str:
    """
    Removes the word 'asterisk' (case-insensitive) from a string.

    Args:
        text: The input string.

    Returns:
        The string with 'asterisk' removed.
    """
    return re.sub(r"(?i)\basterisk\b", "", text).strip()


def filter_asterisks(text: str) -> str:
    """
    Removes text enclosed within asterisks of any length (*, **, ***, etc.) from a string.

    Args:
        text: The input string.

    Returns:
        The string with asterisk-enclosed text removed.
    """
    # Handle asterisks of any length (*, **, ***, etc.)
    filtered_text = re.sub(r"\*{1,}((?!\*).)*?\*{1,}", "", text)

    # Clean up any extra spaces
    filtered_text = re.sub(r"\s+", " ", filtered_text).strip()

    return filtered_text

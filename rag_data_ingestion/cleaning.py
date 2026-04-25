"""
Text cleaning and normalization module for RAG preprocessing.

This module provides functions to clean, normalize, and prepare text
for downstream RAG processing (chunking, embedding, indexing).
"""

import re
import unicodedata
from typing import List, Optional


SMART_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00a0": " ",
        "\u200b": "",
        "\ufeff": "",
    }
)


def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode characters to NFC form.
    
    Args:
        text: Input text with potential Unicode variations.
        
    Returns:
        Normalized text in NFC form.
    """
    return unicodedata.normalize('NFC', text)


def normalize_text_boundaries(text: str) -> str:
    """
    Normalize line endings, smart punctuation, and invisible characters.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.translate(SMART_PUNCTUATION_TRANSLATION)


def remove_control_characters(text: str) -> str:
    """
    Remove control characters while preserving newlines and tabs.
    """
    return ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')


def remove_extra_whitespace(text: str) -> str:
    """
    Remove extra whitespace while preserving paragraph structure.
    
    Collapses multiple spaces to single space and removes leading/trailing
    whitespace from each line. Also collapses multiple consecutive newlines.
    
    Args:
        text: Input text with potential extra whitespace.
        
    Returns:
        Text with normalized whitespace.
    """
    # Replace repeated horizontal whitespace with a single space.
    text = re.sub(r'[^\S\n]+', ' ', text)
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    # Remove empty lines at the start and end
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    # Remove consecutive empty lines (more than one)
    cleaned_lines = []
    prev_empty = False
    for line in lines:
        if line:
            cleaned_lines.append(line)
            prev_empty = False
        elif not prev_empty:
            cleaned_lines.append('')
            prev_empty = True
    return '\n'.join(cleaned_lines)


def remove_special_characters(text: str, keep_punctuation: bool = True) -> str:
    """
    Remove unwanted special characters.
    
    Args:
        text: Input text.
        keep_punctuation: If True, keep standard punctuation. If False, remove all.
        
    Returns:
        Text with special characters removed.
    """
    if keep_punctuation:
        # Keep common prose punctuation plus technical syntax used in paths,
        # network configs, JSON paths, formulas, and table-like text.
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\'\"\-\n\(\)\[\]\{\}<>/@#%&\+=_\*\|\\$]', '', text)
    else:
        # Keep only alphanumeric, whitespace, and newlines
        text = re.sub(r'[^\w\s\n]', '', text)
    return text


def convert_to_lowercase(text: str) -> str:
    """
    Convert text to lowercase.
    
    Args:
        text: Input text.
        
    Returns:
        Lowercase text.
    """
    return text.lower()


def expand_contractions(text: str) -> str:
    """
    Expand common English contractions.
    
    Args:
        text: Input text with contractions.
        
    Returns:
        Text with contractions expanded.
    """
    contractions_dict = {
        r"can't": "cannot",
        r"won't": "will not",
        r"n't": " not",
        r"'re": " are",
        r"'ve": " have",
        r"'ll": " will",
        r"'d": " would",
        r"'m": " am",
    }
    
    for contraction, expansion in contractions_dict.items():
        text = re.sub(contraction, expansion, text, flags=re.IGNORECASE)
    
    return text


def remove_urls(text: str) -> str:
    """
    Remove URLs from text.
    
    Args:
        text: Input text with potential URLs.
        
    Returns:
        Text with URLs removed.
    """
    url_pattern = r'https?://\S+|www\.\S+'
    return re.sub(url_pattern, '', text)


def remove_emails(text: str) -> str:
    """
    Remove email addresses from text.
    
    Args:
        text: Input text with potential email addresses.
        
    Returns:
        Text with emails removed.
    """
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return re.sub(email_pattern, '', text)


def repair_ocr_substitutions(text: str) -> str:
    """
    Repair conservative OCR substitutions in prose tokens.

    This intentionally avoids tokens with technical delimiters so values like
    Gi1/0/24, 10.10.0.0/24, JSON paths, and model numbers remain intact.
    """
    split_word_repairs = {
        r"\bshee\s+t\b": "sheet",
        r"\bhea\s+der\b": "header",
        r"\bfoo\s+ter\b": "footer",
    }
    for pattern, replacement in split_word_repairs.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    known_word_repairs = {
        r"\bfin1sh\b": "finish",
    }
    for pattern, replacement in known_word_repairs.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    def repair_token(match: re.Match) -> str:
        token = match.group(0)
        if not any(char.isalpha() for char in token):
            return token
        if not any(char in token for char in ("0", "1")):
            return token
        if any(char in token for char in "./:-_[]{}#@"):
            return token
        if len(token) < 4:
            return token
        return token.translate(str.maketrans({"0": "o", "1": "l"}))

    return re.sub(r"\b[A-Za-zÀ-ÿ0-9]+\b", repair_token, text)


def remove_repeated_noise_lines(text: str, max_repetitions: int = 4) -> str:
    """
    Limit boilerplate lines that repeat excessively across extracted pages.
    """
    lines = text.split("\n")
    counts = {}
    for line in lines:
        normalized = line.strip().casefold()
        if len(normalized) < 4:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1

    cleaned_lines = []
    kept_counts = {}
    for line in lines:
        normalized = line.strip().casefold()
        if normalized.startswith("ocr_extract"):
            continue
        kept_counts[normalized] = kept_counts.get(normalized, 0) + 1
        if counts.get(normalized, 0) > max_repetitions and kept_counts[normalized] > 1:
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


class TextCleaner:
    """
    Composable text cleaner for RAG preprocessing pipeline.
    
    This class allows chaining of cleaning operations with customizable
    options for different use cases.
    
    Example:
        >>> cleaner = TextCleaner()
        >>> cleaned = cleaner.clean(text)
    """
    
    def __init__(
        self,
        normalize_unicode_chars: bool = True,
        remove_extra_spaces: bool = True,
        lowercase: bool = False,
        expand_contracs: bool = True,
        expand_contractions_flag: Optional[bool] = None,
        remove_urls_flag: bool = True,
        remove_emails_flag: bool = True,
        keep_punctuation: bool = True,
        remove_repeated_lines: bool = False,
        repair_ocr: bool = False,
    ):
        """
        Initialize TextCleaner with desired preprocessing steps.
        
        Args:
            normalize_unicode_chars: Normalize Unicode to NFC form.
            remove_extra_spaces: Collapse multiple spaces to single space.
            lowercase: Convert text to lowercase.
            expand_contracs: Expand English contractions. Kept for backwards compatibility.
            expand_contractions_flag: Preferred spelling for expand_contracs.
            remove_urls_flag: Remove URLs.
            remove_emails_flag: Remove email addresses.
            keep_punctuation: Keep punctuation during special char removal.
            remove_repeated_lines: Remove repeated boilerplate/header/footer lines.
            repair_ocr: Repair conservative OCR digit/letter substitutions in prose.
        """
        self.normalize_unicode_chars = normalize_unicode_chars
        self.remove_extra_spaces = remove_extra_spaces
        self.lowercase = lowercase
        self.expand_contracs = expand_contracs if expand_contractions_flag is None else expand_contractions_flag
        self.remove_urls_flag = remove_urls_flag
        self.remove_emails_flag = remove_emails_flag
        self.keep_punctuation = keep_punctuation
        self.remove_repeated_lines = remove_repeated_lines
        self.repair_ocr = repair_ocr

    @classmethod
    def for_prose(cls) -> "TextCleaner":
        return cls(repair_ocr=False, remove_repeated_lines=False)

    @classmethod
    def for_ocr_prose(cls) -> "TextCleaner":
        return cls(repair_ocr=True, remove_repeated_lines=True)

    @classmethod
    def for_structured_data(cls) -> "TextCleaner":
        return cls(repair_ocr=False, remove_repeated_lines=False)

    @classmethod
    def for_network_config(cls) -> "TextCleaner":
        return cls(repair_ocr=False, remove_repeated_lines=False)
    
    def clean(self, text: str) -> str:
        """
        Apply all configured cleaning operations in sequence.
        
        Args:
            text: Input text to clean.
            
        Returns:
            Cleaned text ready for RAG preprocessing.
        """
        if not isinstance(text, str):
            return text

        text = normalize_text_boundaries(text)
        text = remove_control_characters(text)
        
        if self.normalize_unicode_chars:
            text = normalize_unicode(text)
        
        if self.remove_urls_flag:
            text = remove_urls(text)
        
        if self.remove_emails_flag:
            text = remove_emails(text)
        
        if self.expand_contracs:
            text = expand_contractions(text)

        if self.repair_ocr:
            text = repair_ocr_substitutions(text)
        
        if self.lowercase:
            text = convert_to_lowercase(text)
        
        text = remove_special_characters(text, keep_punctuation=self.keep_punctuation)

        if self.remove_repeated_lines:
            text = remove_repeated_noise_lines(text)
        
        if self.remove_extra_spaces:
            text = remove_extra_whitespace(text)
        
        return text.strip()

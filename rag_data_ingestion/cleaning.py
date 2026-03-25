"""
Text cleaning and normalization module for RAG preprocessing.

This module provides functions to clean, normalize, and prepare text
for downstream RAG processing (chunking, embedding, indexing).
"""

import re
import unicodedata
from typing import List, Optional


def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode characters to NFC form.
    
    Args:
        text: Input text with potential Unicode variations.
        
    Returns:
        Normalized text in NFC form.
    """
    return unicodedata.normalize('NFC', text)


def remove_extra_whitespace(text: str) -> str:
    """
    Remove extra whitespace while preserving paragraph structure.
    
    Collapses multiple spaces to single space and removes leading/trailing
    whitespace from each line.
    
    Args:
        text: Input text with potential extra whitespace.
        
    Returns:
        Text with normalized whitespace.
    """
    # Replace multiple spaces with single space
    text = re.sub(r' {2,}', ' ', text)
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    # Remove empty lines at the start and end
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


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
        # Keep alphanumeric, standard punctuation, whitespace, and newlines
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\'\"\-\n]', '', text)
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
        remove_urls_flag: bool = True,
        remove_emails_flag: bool = True,
        keep_punctuation: bool = True,
    ):
        """
        Initialize TextCleaner with desired preprocessing steps.
        
        Args:
            normalize_unicode_chars: Normalize Unicode to NFC form.
            remove_extra_spaces: Collapse multiple spaces to single space.
            lowercase: Convert text to lowercase.
            expand_contracs: Expand English contractions.
            remove_urls_flag: Remove URLs.
            remove_emails_flag: Remove email addresses.
            keep_punctuation: Keep punctuation during special char removal.
        """
        self.normalize_unicode_chars = normalize_unicode_chars
        self.remove_extra_spaces = remove_extra_spaces
        self.lowercase = lowercase
        self.expand_contracs = expand_contracs
        self.remove_urls_flag = remove_urls_flag
        self.remove_emails_flag = remove_emails_flag
        self.keep_punctuation = keep_punctuation
    
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
        
        if self.normalize_unicode_chars:
            text = normalize_unicode(text)
        
        if self.remove_urls_flag:
            text = remove_urls(text)
        
        if self.remove_emails_flag:
            text = remove_emails(text)
        
        if self.expand_contracs:
            text = expand_contractions(text)
        
        if self.lowercase:
            text = convert_to_lowercase(text)
        
        text = remove_special_characters(text, keep_punctuation=self.keep_punctuation)
        
        if self.remove_extra_spaces:
            text = remove_extra_whitespace(text)
        
        return text.strip()

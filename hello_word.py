print("Hello, World!")

from rag_data_ingestion import TextFileLoader, TextCleaner


def example_custom_text_cleaning():
    """Text loading with custom cleaning configuration."""
    # Create a custom cleaner that keeps structure
    cleaner = TextCleaner(
        normalize_unicode_chars=True,
        remove_extra_spaces=True,
        lowercase=False,  # Keep original case
        expand_contracs=True,
        remove_urls_flag=True,
        remove_emails_flag=True,
        keep_punctuation=True,
    )
    
    loader = TextFileLoader(cleaner=cleaner)
    
    data = loader.load('/workspaces/nw_copilot_codespace/testing_files/huracan.txt', encoding='utf-8')
    print(f"Cleaned content:\n{data.content}")
    print("Example: Custom text cleaning")
    print("Uncomment code above with actual file path to run")




if __name__ == "__main__":
    example_custom_text_cleaning()


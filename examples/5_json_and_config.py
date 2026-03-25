"""
Example 5: Loading JSON and Configuration Files

Demonstrates loading JSON files and Cisco network configurations
for RAG preprocessing.
"""

from rag_data_ingestion import JSONLoader, CiscoConfigLoader


def example_json_basic_loading():
    """Load and flatten JSON files."""
    loader = JSONLoader()
    
    # Assumes 'data.json' exists
    # data = loader.load('data.json', flatten=True)
    # print(f"Content preview:\n{data.content[:300]}")
    print("Example: Basic JSON loading")
    print("Uncomment code above with actual JSON path to run")


def example_json_nested_structure():
    """Handle nested JSON structures."""
    loader = JSONLoader()
    
    # JSON with nested objects/arrays
    # data = loader.load('nested_data.json', flatten=True)
    # Flattened output uses dot notation and array indices
    # Example: "user.name: John", "items[0]: value"
    # print(f"Flattened structure:\n{data.content}")
    print("Example: Nested JSON handling")
    print("Uncomment code above with actual nested JSON to run")


def example_json_no_flattening():
    """Load JSON without flattening."""
    loader = JSONLoader()
    
    # Load without flattening (keeps some structure)
    # data = loader.load('data.json', flatten=False)
    # print(f"Non-flattened JSON:\n{data.content[:300]}")
    print("Example: JSON without flattening")
    print("Uncomment code above with actual JSON path to run")


def example_cisco_config_basic():
    """Load basic Cisco configuration files."""
    loader = CiscoConfigLoader()
    
    # Assumes 'router_config.txt' exists
    # data = loader.load('router_config.txt')
    # print(f"Configuration content:\n{data.content[:400]}")
    # print(f"Sections: {data.source.metadata.get('sections', [])}")
    print("Example: Basic Cisco config loading")
    print("Uncomment code above with actual config file to run")


def example_cisco_config_organized():
    """Load Cisco config with section organization."""
    loader = CiscoConfigLoader()
    
    # Organize by configuration sections (default)
    # data = loader.load(
    #     'router_config.txt',
    #     organize_sections=True,
    #     redact_sensitive=True
    # )
    # Config will be organized like:
    # === general ===
    # ...
    # === interface GigabitEthernet0/0/0 ===
    # ...
    # === router bgp 65000 ===
    # ...
    print("Example: Cisco config with section organization")
    print("Uncomment code above with actual config to run")


def example_cisco_config_redaction():
    """Demonstrate sensitive data redaction in Cisco configs."""
    loader = CiscoConfigLoader()
    
    # Passwords and secrets are redacted by default
    # data = loader.load(
    #     'router_config.txt',
    #     redact_sensitive=True
    # )
    # Passwords will appear as:
    # enable password [REDACTED]
    # snmp-server community [REDACTED]
    # print("Configuration with redacted sensitive data")
    # print(data.content)
    print("Example: Cisco config with sensitive data redaction")
    print("Uncomment code above with actual config to run")


def example_cisco_config_raw():
    """Load raw Cisco config without organization."""
    loader = CiscoConfigLoader()
    
    # Load without section organization
    # data = loader.load(
    #     'router_config.txt',
    #     organize_sections=False,
    #     redact_sensitive=False
    # )
    # print("Raw configuration content")
    print("Example: Raw Cisco config loading")
    print("Uncomment code above with actual config to run")


if __name__ == "__main__":
    print("=" * 60)
    print("RAG Data Ingestion - Example 5: JSON & Config Files")
    print("=" * 60)
    
    example_json_basic_loading()
    print()
    example_json_nested_structure()
    print()
    example_json_no_flattening()
    print()
    example_cisco_config_basic()
    print()
    example_cisco_config_organized()
    print()
    example_cisco_config_redaction()
    print()
    example_cisco_config_raw()

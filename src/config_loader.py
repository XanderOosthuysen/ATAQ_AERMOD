import yaml
import sys
from pathlib import Path

def load_config(config_path="config.yaml"):
    """
    Loads the YAML configuration and returns a dictionary.
    Ensures that relative paths are converted to absolute Path objects.
    """
    # 1. Resolve the path to the config file
    # (Assuming run_pipeline.py is the entry point in the root)
    root_dir = Path.cwd()
    full_config_path = root_dir / config_path
    
    if not full_config_path.exists():
        print(f"[ERROR] Configuration file not found at: {full_config_path}")
        print("Please create a 'config.yaml' file in the project root.")
        sys.exit(1)

    # 2. Parse YAML
    try:
        with open(full_config_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"[ERROR] Invalid YAML format: {e}")
        sys.exit(1)

    # 3. Path Normalization (Optional but recommended)
    # Converts strings like "./data/raw" into real Path objects
    if 'paths' in config:
        for key, path_str in config['paths'].items():
            if path_str: # If not empty
                # Resolve relative to root
                config['paths'][key] = (root_dir / path_str).resolve()
    
    return config

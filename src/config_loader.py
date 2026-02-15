import yaml
import sys
from pathlib import Path

def load_config(config_name="default.yaml"):
    """
    Loads YAML configuration. 
    1. Searches in 'project_configs/' first.
    2. Anchors all paths relative to the Project Root (ATAQ_AERMOD/).
    """
    # Define Anchors
    # Root is two levels up from this script (src/config_loader.py -> src -> Root)
    project_root = Path(__file__).parent.parent.resolve()
    config_dir = project_root / "project_configs"
    
    # Check if user passed a full path or just a filename
    if Path(config_name).exists():
        target_path = Path(config_name)
    else:
        # Check inside project_configs
        target_path = config_dir / config_name
        # Auto-append .yaml if missing
        if not target_path.exists() and not target_path.suffix:
            target_path = target_path.with_suffix('.yaml')

    if not target_path.exists():
        print(f"[ERROR] Config file not found: {target_path}")
        print(f"        Searched in: {config_dir}")
        sys.exit(1)

    # Load YAML
    try:
        with open(target_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"[ERROR] Invalid YAML format: {e}")
        sys.exit(1)

    # --- PATH NORMALIZATION ---
    # This ensures that "data/met/raw" in the yaml becomes "/home/user/.../data/met/raw"
    
    def resolve_path(p_str):
        if not p_str: return ""
        p = Path(p_str)
        if p.is_absolute(): return p
        return (project_root / p).resolve()

    if 'paths' in config:
        for key, val in config['paths'].items():
            config['paths'][key] = resolve_path(val)

    if 'inventory' in config:
        for key, val in config['inventory'].items():
            config['inventory'][key] = resolve_path(val)

    # Handle User Met Files
    if 'project' in config:
        if config['project'].get('user_sfc'):
            config['project']['user_sfc'] = resolve_path(config['project']['user_sfc'])
        if config['project'].get('user_pfl'):
            config['project']['user_pfl'] = resolve_path(config['project']['user_pfl'])

    return config

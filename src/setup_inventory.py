import os
import csv
from pathlib import Path

def setup_inventory(config):
    """
    Creates inventory directory structure and 3 empty CSV templates
    based on the project name in config.
    """
    project_name = config['project']['name']
    print(f"\n[SETUP] Generating Inventory for project: {project_name}...")
    
    # Determine project root
    project_root = Path(__file__).parent.parent
    
    # Create Path: data/inventory/{ProjectName}
    inv_dir = project_root / "data" / "inventory" / project_name
    inv_dir.mkdir(parents=True, exist_ok=True)
    print(f"    -> Created directory: {inv_dir}")

    # Template Definitions with Correct AERMOD Headers
    templates = {
        "point_sources.csv": [
            "source_id", "x_coord", "y_coord", "elevation", "emission_rate", 
            "stack_height", "stack_temp_k", "stack_velocity", "stack_diameter", "description"
        ],
        "area_sources.csv": [
            "source_id", "x_coord", "y_coord", "elevation", "emission_rate", 
            "release_height", "x_len", "y_len", "angle", "szinit", "description"
        ],
        "volume_sources.csv": [
            "source_id", "x_coord", "y_coord", "elevation", "emission_rate", 
            "release_height", "syinit", "szinit", "description"
        ]
    }

    for filename, headers in templates.items():
        file_path = inv_dir / filename
        
        # Only create if it doesn't exist to prevent overwriting user data
        if not file_path.exists():
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            print(f"    -> Created template: {filename}")
        else:
            print(f"    -> Skipped {filename} (Already exists)")
            
    print("\n[INFO] Please populate these CSV files before running 'aermod'.")

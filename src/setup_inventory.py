import os
from pathlib import Path

def setup_inventory(config):
    """
    Initializes blank CSV templates for emissions inventory if they do not exist.
    Configures them with GIS-ready WKT geometries and multi-pollutant emission columns.
    """
    project_root = Path(__file__).parent.parent.resolve()
    
    # Get project name to create a dedicated inventory folder
    project_name = config.get('project', {}).get('name', 'MyProject')
    inv_dir = project_root / "data" / "inventory" / project_name
    inv_dir.mkdir(parents=True, exist_ok=True)
    
    # Standard Pollutants to append to every source type
    pollutants = "SO2,NO2,PM10,PM2.5,CO,Pb,OTHER"
    default_rates = "0.0,0.0,0.0,0.0,0.0,0.0,0.0"

    # Fetch Site Coordinates for realistic default dummy geometries
    lat = float(config.get('location', {}).get('latitude', -26.2041))
    lon = float(config.get('location', {}).get('longitude', 28.0473))

    templates = {
        "point_sources.csv": (
            f"source_id,WKT,elevation,stack_height,stack_temp_k,stack_velocity,stack_diameter,description,{pollutants}\n"
            f"1,\"POINT ({lon} {lat})\",1600.0,10.0,300.0,4.0,0.5,Example Stack,{default_rates}\n"
        ),
        "area_sources.csv": (
            f"source_id,WKT,elevation,release_height,x_len,y_len,angle,szinit,description,{pollutants}\n"
            f"1,\"POLYGON (({lon} {lat}, {lon+0.001} {lat}, {lon+0.001} {lat+0.001}, {lon} {lat+0.001}, {lon} {lat}))\",1600.0,2.0,50.0,50.0,0.0,1.0,Example Area,{default_rates}\n"
        ),
        "line_sources.csv": (
            f"source_id,WKT,elevation,release_height,width_m,szinit,description,{pollutants}\n"
            f"1,\"LINESTRING ({lon} {lat}, {lon+0.005} {lat})\",1600.0,1.0,10.0,2.0,Example Road,{default_rates}\n"
        )
    }

    print(f"--- Initializing Inventory Templates for '{project_name}' ---")
    
    for filename, content in templates.items():
        file_path = inv_dir / filename
        if not file_path.exists():
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"  [CREATED] {filename}")
        else:
            print(f"  [EXISTS]  {filename} (Skipped to prevent overwriting)")
            
    print(f"Templates are located in: {inv_dir}")

if __name__ == "__main__":
    setup_inventory({'project': {'name': 'Test_Project'}})

# **ATAQ_AERMOD**

**Version:** v0.1.0-alpha

Overview:
An open-source Python interface designed to simplify and automate the execution of the USEPA's AERMOD dispersion model. 

Developed with a focus on usability outside of the US, this tool prioritizes alternative meteorological data sources (like ERA5), multi-year automation, and GIS integration.

QGIS plugin for source definitions underway.


## ✨ Key Features
* **GUI:** Manage projects, coordinates, and execution phases from a unified Tkinter interface.
* **GIS-Ready Inventories (WKT):** Define complex Area, Line, and Point sources using standard Well-Known Text (WKT). Easily copy-paste geometries directly from QGIS or ArcGIS.
* **Automated GeoTIFF Export:** AERMOD `.PLT` output files are automatically converted into georeferenced high-resolution `.tif` rasters for instant drag-and-drop visualization in your GIS software.
* **Multi-Year Automation:** Loops through multiple years (e.g., 2020-2024) of meteorological data and modeling runs automatically.
* **ERA5 Met Processing Pipeline:** Fetches and processes surface and upper-air data from the ECMWF Climate Data Store.
* **Error Handling:** Auto-fixes "North Wind" vector issues and strict Fortran formatting requirements.

---

##  Prerequisites
### 1. Python Environment
Ensure you have Python 3.10+ installed.

    # Create and activate a virtual environment
    python3 -m venv aermod_env
    source aermod_env/bin/activate  
    # On Windows use:     python3 -m venv aermod_env
    # On Windows use: aermod_env\Scripts\activate
    
    # Install dependencies
    pip install -r requirements.txt
(Required packages include: pandas, numpy, pyproj, shapely, rasterio, matplotlib, scipy, pyyaml)


### 2. AERMOD Executables
You must have the compiled Fortran binaries for AERMET and AERMOD. **This is preferably set-up as per Section 4 using the GUI workflow** , or manually as below:

The script automatically downloads the source code for AERMET and AERMOD, and compiles it (Windows or Linux auto-detect).

    python3 setup_env.py
    
Alternativly:
1. Create a folder named bin/ in the project root.
2. Place your executables there:
    - bin/aermet (or aermet.exe on Windows)
    - bin/aermod (or aermod.exe on Windows)

### 3. Launch the Controller
The easiest way to use ATAQ AERMOD  and to set up the binaries is via the graphical interface. However all scripts and the run_pipeline function can be used as well.
 
    python3 run_pipeline.py --gui 
    #On windows: python run_pipeline.py --gui

### 4. Workflow
1. Setup Env: Click the "Setup Env" button in the GUI to automatically download and compile the required AERMET and AERMOD Fortran binaries for your OS.

2. Project Setup: Define your project name, years to run, and the precise Lat/Lon of your site.

3. Meteorology: Choose between the automated ERA5 pipeline (requires CDS API keys) or provide your own .SFC and .PFL files.

4. Inventory: Click "Init Templates" to generate your point_sources.csv, area_sources.csv, etc. Populate these using WKT geometries. (See the generated InventoryInstructions.txt for details).

5. Run AERMOD: Execute the model. Final Plot files (.PLT) and georeferenced Rasters (.tif) will be exported to the data/model_output/{Project} folder.
    


### 5. CDS API Key (for Met Data)
To download ERA5 data, you need an API key from the Copernicus Climate Data Store.

Register at CDS: https://cds.climate.copernicus.eu/

Create a file in your User Home Directory (not the project folder) named .cdsapirc:
Linux: ~/.cdsapirc
Windows: C:\Users\Username\.cdsapirc
Add your credentials:
    url: [https://cds.climate.copernicus.eu/api/v2]
    key: YOUR-UID:YOUR-API-KEY

## MORE ON HOW TO USE: 

All settings are managed in the project config.yaml. Named "PROJECT".yaml. 

All actions are run through the run_pipeline.py script or the GUI. 

## 💻 Command-Line Interface (CLI) Reference

While the GUI is the recommended way to use ATAQ AERMOD, the pipeline can be fully automated or scripted via the command line using the `--action` argument.

**Usage:** `python3 run_pipeline.py --action [ACTION_NAME] --config [CONFIG_FILE.yaml]`

### Initialization & Setup
* **`--gui`** Launches the graphical user interface. (Does not require an `--action` argument).
* **`--action setup_aermod`**
  Downloads the official EPA Fortran source code for AERMOD and AERMET and compiles the binaries for your specific operating system. (Only needs to be run once per machine).
* **`--action setup_inventory`**
  Generates the blank, WKT-ready CSV templates (`point_sources.csv`, `area_sources.csv`, `line_sources.csv`) and the `InventoryInstructions.txt` guide for the active project.

### Meteorological Pipeline (ERA5)
* **`--action download`**
  Connects to the ECMWF Climate Data Store (CDS) to download raw ERA5 surface and upper-air NetCDF/GRIB files for the coordinates and years specified in your config.
* **`--action met_process`**
  Extracts and converts the raw ERA5 data into the intermediate formats required by AERMET (e.g., extracting specific wind vectors, cloud cover, and formatting upper-air soundings).
* **`--action aermet`**
  Executes the AERMET meteorological pre-processor to generate the final `.SFC` (Surface) and `.PFL` (Profile) files required by AERMOD.

### Dispersion Modeling & Post-Processing
* **`--action run_model`**
  Executes the AERMOD dispersion model. It parses your WKT inventory, dynamically generates the `aermod.inp` file for each active pollutant, runs the model in an isolated sandbox, and automatically exports GeoTIFFs (`.tif`) of the resulting `.PLT` files.
* **`--action visualize`**
  Generates a quick 2D Matplotlib contour plot (`.png`) of a specific `.PLT` file for rapid quality assurance without needing to open GIS software.

## ⚠️ Disclaimer ##
The end-user is ultimately responsible for ensuring the validity of the meteorological data, inventory inputs, and compliance with local regulatory modeling guidelines.

## Directory structure ##
```text
ATAQ_AERMOD
 ┣ 📂 bin                 # Executables (aermet, aermod)
 ┣ 📂 src                 # Source code (processors, runners)
 ┣ 📂 project_configs     # Saved YAML configuration files per project
 ┣ 📜 run_pipeline.py     # Entry point
 ┗ 📂 data                # Data storage (Ignored by Git)
    ┣ 📂 met
    ┃  ┣ 📂 raw           # Downloaded NetCDF/Zip files
    ┃  ┣ 📂 interim       # Intermediate CSV/IGRA files
    ┃  ┣ 📂 processed     # Final .SFC and .PFL files
    ┃  ┗ 📂 aermet_logs   # Debug logs from AERMET
    ┣ 📂 inventory        # Source inventories (CSVs with WKT inputs)
    ┣ 📂 model            # AERMOD Sandbox for active runs (and troubleshooting)
    ┗ 📂 model_output     # Final .PLT  .OUT files and .tif GeoTIFFs

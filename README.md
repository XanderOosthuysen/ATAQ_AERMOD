# **ATAQ_AERMOD**

Overview:
This is an open-source project providing helper functions/interfaces to simplify the use of the USEPA's AERMOD.
It is developed outside of the US, and therefor, alternatives sources of meteorological data is considered a priority. The end user is ultimatley responsible to ensure the validty of the data used.

## Features
* **Automated Download:** Fetches surface and upper air data from ECMWF Climate Data Store (ERA5).
* **Met Processing:** Converts raw NetCDF/GRIB data into AERMOD-ready `.SFC` and `.PFL` files.
* **Multi-Year Support:** Loops through multiple years (e.g., 2020-2024) automatically.
* **Robust Error Handling:** Auto-fixes "North Wind" vector issues and floating-point formatting.
* **Project Isolation:** Keeps raw data, interim calculations, and final outputs in separate, organized folders.
* **GIS Friendly** CSV are QGIS "friendly" for viewing or creating by using "WKT"-formatting.

---

##  Prerequisites
### 1. Python Environment
Ensure you have Python 3.10+ installed.

    # Create a virtual environment
    python3 -m venv aermod_env
    source aermod_env/bin/activate
    
    # Install dependencies
    pip install -r requirements.txt

### 2. AERMOD Executables
You must have the compiled Fortran binaries for AERMET and AERMOD.

This can be set up by running the setup_env.py script. 

The script automatically downloads the source code for AERMET and AERMOD, and compiles it (Windows or Linux auto-detect).

    python3 setup_env.py script
    
Alternativly:
1. Create a folder named bin/ in the project root.
2. Place your executables there:
    - bin/aermet (or aermet.exe on Windows)
    - bin/aermod (or aermod.exe on Windows)

### 3. CDS API Key (for Met Data)
To download ERA5 data, you need an API key from the Copernicus Climate Data Store.

Register at CDS: https://cds.climate.copernicus.eu/

Create a file in your User Home Directory (not the project folder) named .cdsapirc:
Linux: ~/.cdsapirc
Windows: C:\Users\Username\.cdsapirc
Add your credentials:
    url: [https://cds.climate.copernicus.eu/api/v2]
    key: YOUR-UID:YOUR-API-KEY

## HOW TO USE: 


**Configuration**
All settings are managed in config.yaml.
All actions are run through the run_pipeline.py script. 
However there is a GUI that can assist to set up config.yaml and run the various options.
To get Access to the GUI
    python3 run_pipeline.py -- guiequirements.txt

Altenrative: use console and manually update config.yaml via Text editor.


**Step 1: Download Meteorology**
Downloads raw ERA5 data to data/met/raw/{StationName}.

    python3 run_pipeline.py --action download
Alternative: User can supply pre-processed AERMET output files to use and skip this Step 1 and Step 2.

**Step 2: Process Meteorology**
Converts raw data to AERMET-ready CSVs and IGRA files in data/met/interim.


    python3 run_pipeline.py --action process
**Step 3: Run AERMET**
Generates .SFC and .PFL files. Results are saved to data/met/processed.


    python3 run_pipeline.py --action aermet
**Step 4: Configure AERMOD**
GUI or config.yaml AERMOD Params: Define your model parameters and Receptor Grid size.
Inventory: Either use GUI or run the following: 

    python3 run_pipeline.py --action build_inventory
Define line, area and point sources in the respective CSV's. WKT is used for shape formatting. Use the provided templates.

**Step 5: Run AERMOD**
Executes the dispersion model.

Inputs: Reads met data from data/met/processed.

Sandbox: Runs inside data/model/run/{Project}/{Year} to prevent file conflicts. Automatically cleans up the sandbox-post succesful excecution.
Outputs: Final Plot files (.PLT) and Logs (.out) are moved to data/model_output/{Project}.

    python3 run_pipeline.py --action aermod
    (Optional) Run All Steps
    Bash
    python3 run_pipeline.py --action all


## Directory structure ##
```text
ATAQ_AERMOD
 ┣ 📂 bin                 # Executables (aermet, aermod)
 ┣ 📂 src                 # Source code (processors, runners)
 ┣ 📜 config.yaml         # Main configuration
 ┣ 📜 run_pipeline.py     # Entry point
 ┗ 📂 data                # Data storage (Ignored by Git)
    ┣ 📂 met
    ┃  ┣ 📂 raw           # Downloaded NetCDF/Zip files
    ┃  ┣ 📂 interim       # Intermediate CSV/IGRA files
    ┃  ┣ 📂 processed     # Final .SFC and .PFL files
    ┃  ┗ 📂 aermet_logs   # Debug logs from AERMET
    ┣ 📂 inventory        # Source inventories
    ┣ 📂 model            # AERMOD Sandbox
    ┗ 📂 model_output     # Final .PLT and .OUT files

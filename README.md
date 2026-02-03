###################ATAQ_AERMOD#############################

Overview:
This is an open-source project providing helper functions/interfaces to simplify the use of the USEPA's AERMOD.
It is developed outside of the US, and therefor, alternatives sources of meteorological data is considered a priority. The end user is ultimatley responsible to ensure the validty of the data used.

Met download and processor:

Current functionality
- Download ERA5  surface and upper air re-analysis data (simulated) provided the year(s) and location (User must register on ECWMF website and obtain API key - free)
- Process the downloaded data into required formats for AERMET as ONSITE and UPPER AIR data (IGRA format used, FML to be added)
- Alternative: User can supply pre-processed AERMET output files to use.

AERMOD: 
- CSV based input for:
    - Line sources
    - Point sources
    - Area sources
- CSV are QGIS "friendly" for viewing or creating by using "WKT"-formatting.
 

How to use:
Either GUI or terminal via the run_pipeline.py script

GUI assist to set up config.yaml.


Download met data: python3 run_pipeline.py --action download

Result: If files exist, it pauses and asks: Use existing data? [Y/n].

Hit Enter: It skips downloading and just checks for missing files.

Type 'n': It deletes everything and downloads fresh.

Overnight/Batch Mode: python3 run_pipeline.py --action download --overwrite

Result: Never asks. Deletes everything and downloads fresh automatically.

###################ATAQ_AERMOD#############################

Overview:
This is an open-source project providing helper functions/interfaces to simplify the use of the USEPA's AERMOD.
It is developed outside of the US, and therefor aims to assist where the required data is not readily available.


Met download and processor:
Idea: Download publically met-data and format so that aermet can process the data.

Current functionality
- Download ERA5  surface and upper air re-analysis data (simulated) provided the year(s) and location(User must register on ECWMF website and obtain API key - free)
- Process data into required formats for AERMET as ONSITE and UPPER AIR data (IGRA format used, FML to be added) 

AERMOD: 
- CSV based input for:
    - Line sources
    - Point sources
    - Area sources
- CSV are QGIS "friendly" for viewing.

 

Met download:
How to use it
Normal Mode: python3 run_pipeline.py --action download

Result: If files exist, it pauses and asks: Use existing data? [Y/n].

Hit Enter: It skips downloading and just checks for missing files.

Type 'n': It deletes everything and downloads fresh.

Overnight/Batch Mode: python3 run_pipeline.py --action download --overwrite

Result: Never asks. Deletes everything and downloads fresh automatically.

"""
ATAQ AERMOD Pipeline
Copyright (C) 2026 ATAQ

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import argparse
import sys
import subprocess
from pathlib import Path

# --- CORE IMPORTS ---
from src.config_loader import load_config
from src.met_downloads import ERA5Downloader
from src.met_processor import SurfaceProcessor, UpperAirProcessor
from src.setup_inventory import setup_inventory

# --- RUNNER IMPORTS (Standardized) ---
# If these fail, we want the script to crash immediately so we know why.
try:
    from src.aermet_runner import AermetRunner
    from src.aermod_runner import AermodRunner
    from src.plotter import AermodPlotter
except ImportError as e:
    print(f"[WARNING] Could not import one of the runners: {e}")
    # We continue, because maybe the user is only running --action download

# --- GUI IMPORT (Optional) ---
try:
    from src.gui_helper import launch_gui
except ImportError:
    pass

def main():
    parser = argparse.ArgumentParser(description="ATAQ AERMOD: Multi-Year Pipeline")
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to configuration file')
    
    actions = ['download', 'met_process', 'aermet', 'setup_aermod', 'run_model', 'visualize','setup_inventory']
    parser.add_argument('--action', choices=actions, required=False, help="Pipeline stage to execute")
    
    parser.add_argument('--overwrite', action='store_true', help='Force re-download/re-process of existing data')
    parser.add_argument('--gui', action='store_true', help='Launch the Configuration GUI Helper')
    
    args = parser.parse_args()

    # GUI CHECK
    if args.gui:
        print(">>> Launching GUI Helper...")
        if 'launch_gui' in globals():
            launch_gui()
        else:
            print("[ERROR] GUI module not found (src/gui_helper.py).")
        return 

    if not args.action:
        parser.error("the following arguments are required: --action (unless using --gui)")

    # 1. LOAD CONFIGURATION
    print(f"--- Loading Configuration: {args.config} ---")
    cfg = load_config(args.config)
    
    # DETECT MULTI-YEAR
    if 'years' in cfg['project']:
        years = cfg['project']['years']
    else:
        years = [cfg['project']['year']]

    lat = cfg['location']['latitude']
    lon = cfg['location']['longitude']
    buffer = cfg['location'].get('area_buffer', 0.25)

    print(f"Project: {cfg['project']['name']}")
    print(f"Years to Process: {years}")

    # ==========================================
    # PHASE 0: BUILD MODEL (Run Once)
    # ==========================================
    if args.action == 'setup_aermod':
        print(f"\n[PHASE 0] Setting up AERMOD System...")
        try:
            from src.setup_env import setup_environment
            setup_environment()
        except ImportError as e:
            print(f"[ERROR] Could not import setup module. Ensure setup_env.py is in the src/ folder: {e}")
        return
    
	# ==========================================
    # BUILD INVENTORIES (Run Once)
    # =========================================
    if args.action == 'setup_inventory':
        print(f"\n Building Inventory Templates via setup_inventories.py...")
        setup_inventory(cfg)
    # ==========================================
    # LOOP THROUGH YEARS
    # ==========================================
    for year in years:
        cfg['project']['year'] = year

        #   DOWNLOAD
        if args.action == 'download':
            print(f"[PHASE 1] Downloading {year}...")
            st_name = cfg['project'].get('station_name', 'Station')
            downloader = ERA5Downloader(overwrite=args.overwrite)
            downloader.download_surface(year, st_name, lat, lon, buffer)
            downloader.download_upper_air(year, st_name, lat, lon, buffer)

        #  PROCESS
        elif args.action == 'met_process':
            print(f"[PHASE 2] Processing {year}...")
            sfc_proc = SurfaceProcessor(cfg)
            sfc_proc.process(year, lat, lon)
            ua_proc = UpperAirProcessor(cfg)
            ua_proc.process(year, lat, lon)

        #  AERMET
        elif args.action == 'aermet':
            print(f"[PHASE 3] Running AERMET for {year}...")
            if 'AermetRunner' not in globals():
                print("[ERROR] AermetRunner class not found. Check src/aermet_runner.py")
                return
            runner = AermetRunner(cfg)
            runner.run()

        # RUN AERMOD
        elif args.action == 'run_model':
            print(f"[PHASE 4] Running AERMOD for {year}...")
            if 'AermodRunner' not in globals():
                print("[ERROR] AermodRunner class not found. Check src/aermod_runner.py")
                return
            model_runner = AermodRunner(cfg)
            model_runner.run()

        # VISUALIZE
        elif args.action == 'visualize':
            print(f"[PHASE 5] Visualizing {year}...")
            if 'AermodPlotter' not in globals():
                print("[ERROR] AermodPlotter class not found. Check src/plotter.py")
                return
            plotter = AermodPlotter(cfg)
            plotter.run()

if __name__ == "__main__":
    main()

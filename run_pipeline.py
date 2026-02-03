import argparse
import sys
import subprocess
from pathlib import Path

# --- CORE IMPORTS ---
from src.config_loader import load_config
from src.met_downloads import ERA5Downloader
from src.met_processor import SurfaceProcessor, UpperAirProcessor

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
    
    actions = ['download', 'process', 'aermet', 'build_model', 'run_model', 'visualize']
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
    if args.action == 'build_model':
        print(f"\n[PHASE 0] Building AERMOD System via setup_env.py...")
        setup_script = Path("setup_env.py").resolve()
        
        if not setup_script.exists():
            print(f"[ERROR] Could not find {setup_script}")
            return

        try:
            subprocess.run([sys.executable, str(setup_script)], check=True)
            print("\n[SUCCESS] Build Complete. Binaries should be in /bin folder.")
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Build failed with exit code {e.returncode}")
        return 

    # ==========================================
    # LOOP THROUGH YEARS
    # ==========================================
    for year in years:
        print(f"\n>>> PROCESSING YEAR: {year} <<<")
        cfg['project']['year'] = year

        # PHASE 1: DOWNLOAD
        if args.action == 'download':
            print(f"[PHASE 1] Downloading {year}...")
            st_name = cfg['project'].get('station_name', 'Station')
            downloader = ERA5Downloader(overwrite=args.overwrite)
            downloader.download_surface(year, st_name, lat, lon, buffer)
            downloader.download_upper_air(year, st_name, lat, lon, buffer)

        # PHASE 2: PROCESS
        elif args.action == 'process':
            print(f"[PHASE 2] Processing {year}...")
            sfc_proc = SurfaceProcessor(cfg)
            sfc_proc.process(year, lat, lon)
            ua_proc = UpperAirProcessor(cfg)
            ua_proc.process(year, lat, lon)

        # PHASE 3: AERMET
        elif args.action == 'aermet':
            print(f"[PHASE 3] Running AERMET for {year}...")
            if 'AermetRunner' not in globals():
                print("[ERROR] AermetRunner class not found. Check src/aermet_runner.py")
                return
            runner = AermetRunner(cfg)
            runner.run()

        # PHASE 4: RUN AERMOD
        elif args.action == 'run_model':
            print(f"[PHASE 4] Running AERMOD for {year}...")
            if 'AermodRunner' not in globals():
                print("[ERROR] AermodRunner class not found. Check src/aermod_runner.py")
                return
            model_runner = AermodRunner(cfg)
            model_runner.run()

        # PHASE 5: VISUALIZE
        elif args.action == 'visualize':
            print(f"[PHASE 5] Visualizing {year}...")
            if 'AermodPlotter' not in globals():
                print("[ERROR] AermodPlotter class not found. Check src/plotter.py")
                return
            plotter = AermodPlotter(cfg)
            plotter.run()

if __name__ == "__main__":
    main()

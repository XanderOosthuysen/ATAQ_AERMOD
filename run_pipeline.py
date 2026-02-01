import argparse
import sys
from src.met_downloads import ERA5Downloader
from src.met_processor import SurfaceProcessor, UpperAirProcessor
from src.config_loader import load_config

# Import Runners/Builders (Wrap in try/except to avoid crashes if files are missing during setup)
try:
    from src.aermet_runner import AermetRunner
    from src.aermod_builder import AermodBuilder
    from src.aermod_runner import AermodRunner
    from src.plotter import AermodPlotter
except ImportError:
    pass

def main():
    parser = argparse.ArgumentParser(description="ATAQ AERMOD: ERA5 to AERMOD Pipeline")
    parser.add_argument('--config', type=str, default='config.yaml', help='Path to configuration file')
    
    # All available actions
    actions = [
        'download',      # Phase 1: Fetch ERA5
        'process',       # Phase 2: Convert to ONSITE/IGRA
        'aermet',        # Phase 3: Run AERMET (Met Preprocessor)
        'build_model',   # Phase 0: Compile AERMOD executable
        'run_model',     # Phase 4: Run AERMOD (Dispersion)
        'visualize'      # Phase 5: Plot Results
    ]
    
    parser.add_argument('--action', choices=actions, required=True, help="Pipeline stage to execute")
    args = parser.parse_args()

    # 1. LOAD CONFIGURATION
    print(f"--- Loading Configuration: {args.config} ---")
    cfg = load_config(args.config)
    
    # Extract variables for easier reading
    year = cfg['project']['year']
    lat = cfg['location']['latitude']
    lon = cfg['location']['longitude']
    buffer = cfg['location'].get('area_buffer', 0.25)

    print(f"Project: {cfg['project']['name']}")
    print(f"Site: {lat}, {lon} (Year: {year})")

    # ==========================================
    # PHASE 1: DOWNLOAD
    # ==========================================
    if args.action == 'download':
        print(f"\n[PHASE 1] Downloading Data...")
        downloader = ERA5Downloader()
        downloader.download_surface(year, lat, lon, buffer)
        downloader.download_upper_air(year, lat, lon, buffer)

    # ==========================================
    # PHASE 2: PROCESS
    # ==========================================
    elif args.action == 'process':
        print(f"\n[PHASE 2] Processing Data...")
        sfc_proc = SurfaceProcessor(cfg)
        sfc_proc.process(year, lat, lon)
        
        ua_proc = UpperAirProcessor(cfg)
        ua_proc.process(year, lat, lon)

    # ==========================================
    # PHASE 3: AERMET
    # ==========================================
    elif args.action == 'aermet':
        print(f"\n[PHASE 3] Running AERMET...")
        if 'AermetRunner' not in globals():
            from src.aermet_runner import AermetRunner
        runner = AermetRunner(cfg)
        runner.run()

    # ==========================================
    # PHASE 0: BUILD MODEL
    # ==========================================
    elif args.action == 'build_model':
        print(f"\n[PHASE 0] Building AERMOD System...")
        if 'AermodBuilder' not in globals():
            from src.aermod_builder import AermodBuilder
        builder = AermodBuilder(cfg)
        builder.build()

    # ==========================================
    # PHASE 4: RUN AERMOD
    # ==========================================
    elif args.action == 'run_model':
        print(f"\n[PHASE 4] Running AERMOD Model...")
        if 'AermodRunner' not in globals():
            from src.aermod_runner import AermodRunner
        model_runner = AermodRunner(cfg)
        model_runner.run()

    # ==========================================
    # PHASE 5: VISUALIZE
    # ==========================================
    elif args.action == 'visualize':
        print(f"\n[PHASE 5] Visualization...")
        if 'AermodPlotter' not in globals():
            from src.plotter import AermodPlotter
        plotter = AermodPlotter(cfg)
        plotter.run()

if __name__ == "__main__":
    main()

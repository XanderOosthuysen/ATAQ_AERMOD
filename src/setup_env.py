"""
ATAQ AERMOD
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
import os
import sys
import zipfile
import urllib.request
import subprocess
import shutil
import platform
from pathlib import Path

# --- CONFIGURATION ---
# AERMET (Met Processor)
AERMET_SRC_URL = "https://gaftp.epa.gov/Air/aqmg/SCRAM/models/met/aermet/aermet_source.zip"

# AERMOD (Dispersion Model) - Version 24142
AERMOD_SRC_URL = "https://gaftp.epa.gov/Air/aqmg/SCRAM/models/preferred/aermod/aermod_source.zip"

def check_gfortran():
    """Checks if gfortran is installed and available in PATH."""
    return shutil.which('gfortran') is not None

def compile_linux(bin_dir, src_dir, exe_name):
    """
    Iterative builder for Fortran projects with dependencies.
    Compiles all source files in src_dir and links them into exe_name.
    """
    # 1. Find ALL source files (Case Sensitive on Linux!)
    extensions = ['*.f90', '*.F90', '*.f', '*.F', '*.for', '*.FOR']
    src_files = []
    for ext in extensions:
        src_files.extend(list(src_dir.rglob(ext)))

    if not src_files:
        print(f"[ERROR] No source files found in {src_dir}")
        return False

    print(f"   Found {len(src_files)} source files for {exe_name}.")
    
    # 2. Compile loop (The "Dependency Solver")
    queue = src_files[:]
    obj_files = []
    max_retries = len(src_files) * 3
    retries = 0
    
    while queue and retries < max_retries:
        current_file = queue.pop(0)
        obj_file = current_file.with_suffix('.o')
        
        cmd = [
            "gfortran", 
            "-c", str(current_file), 
            "-J", str(src_dir), 
            "-I", str(src_dir), 
            "-o", str(obj_file)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            obj_files.append(obj_file)
        except subprocess.CalledProcessError:
            # If it fails, push to back of queue to try again later
            queue.append(current_file)
            
        retries += 1
        
    if queue:
        print(f"[ERROR] Could not compile the following files after {max_retries} attempts:")
        for f in queue:
            print(f"  - {f.name}")
        return False
        
    # 3. Link it all together
    print(f"   Linking {exe_name}...")
    final_exe = bin_dir / exe_name
    link_cmd = ["gfortran"] + [str(o) for o in obj_files] + ["-o", str(final_exe)]
    
    try:
        subprocess.run(link_cmd, check=True, capture_output=True)
        print(f"   [SUCCESS] Compiled {exe_name} successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Linking failed for {exe_name}: {e}")
        return False

def setup_environment(config=None):
    """
    Sets up the AERMOD/AERMET executables.
    On Windows: Prompts and downloads pre-compiled binaries from the EPA.
    On Linux/macOS: Downloads source code and compiles it.
    """
    print("--- STARTING AERMOD ENVIRONMENT SETUP ---")
    
    project_root = Path(__file__).parent.parent.resolve()
    bin_dir = project_root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    
    system = platform.system()
    
    if system == "Windows":
        print("[INFO] Windows OS detected.")
        
        urls = {
            "AERMOD": "https://gaftp.epa.gov/Air/aqmg/SCRAM/models/preferred/aermod/aermod_exe.zip",
            "AERMET": "https://gaftp.epa.gov/Air/aqmg/SCRAM/models/met/aermet/aermet_exe.zip"
        }
        
        # Display Information
        print("\nThe following official EPA binaries will be downloaded:")
        for name, url in urls.items():
            print(f"  - {name}: {url}")
        print(f"\nDestination folder: {bin_dir}\n")
        
        # If run directly in a terminal, ask for confirmation.
        # If run via the GUI, bypass this (the GUI messagebox handles consent).
        if sys.stdin.isatty():
            ans = input("Do you want to proceed with the download? (y/n): ")
            if ans.lower() not in ['y', 'yes']:
                print("[ABORTED] User cancelled setup.")
                return
        
        for name, url in urls.items():
            zip_path = bin_dir / f"{name.lower()}.zip"
            exe_path = bin_dir / f"{name.lower()}.exe"
            
            if exe_path.exists():
                print(f"  -> {name} executable already exists. Skipping.")
                continue
                
            print(f"  -> Downloading {name} from EPA SCRAM...")
            try:
                urllib.request.urlretrieve(url, zip_path)
                
                print(f"  -> Extracting {name}...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(bin_dir)
                
                if zip_path.exists():
                    os.remove(zip_path)
                    
                print(f"  [SUCCESS] {name} installed successfully!")
                
            except Exception as e:
                print(f"  [ERROR] Failed to download/extract {name}: {e}")
                
        print("--- WINDOWS SETUP COMPLETE ---")
        
    else:
        print("[INFO] Linux/macOS detected.")
        if not check_gfortran():
            print("[ERROR] gfortran not found. Please install it first (e.g., sudo apt install gfortran).")
            return

        print("[INFO] Starting source compilation process...")
        
        # =========================================================================
        # BUILD AERMET
        # =========================================================================
        print("\n[1/2] Building AERMET...")
        aermet_src_dir = bin_dir / 'aermet_source'
        
        if aermet_src_dir.exists(): shutil.rmtree(aermet_src_dir)
        aermet_src_dir.mkdir(exist_ok=True)
        
        try:
            print(f"   Fetching: {AERMET_SRC_URL}")
            zip_path = aermet_src_dir / "aermet_src.zip"
            urllib.request.urlretrieve(AERMET_SRC_URL, zip_path)
            
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(aermet_src_dir)
            os.remove(zip_path)

            # Handle nested zips (common in AERMET packages)
            nested_zips = list(aermet_src_dir.rglob("*.zip"))
            if nested_zips:
                for nz in nested_zips:
                    with zipfile.ZipFile(nz, 'r') as z:
                        z.extractall(aermet_src_dir)
                    os.remove(nz)
            
            compile_linux(bin_dir, aermet_src_dir, "aermet")

        except Exception as e:
            print(f"[ERROR] AERMET Build Failed: {e}")

        # =========================================================================
        # BUILD AERMOD
        # =========================================================================
        print("\n[2/2] Building AERMOD...")
        aermod_src_dir = bin_dir / 'aermod_source'
        
        if aermod_src_dir.exists(): shutil.rmtree(aermod_src_dir)
        aermod_src_dir.mkdir(exist_ok=True)
        
        try:
            print(f"   Fetching: {AERMOD_SRC_URL}")
            zip_path = aermod_src_dir / "aermod_src.zip"
            urllib.request.urlretrieve(AERMOD_SRC_URL, zip_path)
            
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(aermod_src_dir)
            os.remove(zip_path)
            
            compile_linux(bin_dir, aermod_src_dir, "aermod")
            
        except Exception as e:
            print(f"[ERROR] AERMOD Build Failed: {e}")
            
        print("[SUCCESS] Linux compilation completed.")

if __name__ == "__main__":
    setup_environment()

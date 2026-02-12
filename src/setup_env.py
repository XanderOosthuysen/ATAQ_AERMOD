import os
import sys
import zipfile
import urllib.request
import subprocess
import shutil
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
    # We try to compile files. If one fails (likely due to missing module), 
    # we push it to the back of the queue.
    queue = src_files[:]
    obj_files = []
    max_retries = len(src_files) * 3  # Allow for complex dependency chains
    loops = 0
    
    # Clean up old object files/modules in the source dir to prevent conflicts
    for junk in src_dir.glob("*.o"): os.remove(junk)
    for junk in src_dir.glob("*.mod"): os.remove(junk)

    print("   Starting iterative compilation...")
    
    while queue and loops < max_retries:
        loops += 1
        current_file = queue.pop(0)
        
        # Object file name: source.f90 -> source.o
        obj_file = current_file.with_suffix('.o')
        
        # Compile command: gfortran -c -O2 source.f90 -o source.o
        # -J defines where to put/read .mod files (keep them in src_dir)
        cmd = [
            "gfortran", "-c", "-O2", "-static",
            "-J", str(src_dir), 
            str(current_file), "-o", str(obj_file)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            obj_files.append(obj_file)
            # print(f"      Compiled: {current_file.name}")
        except subprocess.CalledProcessError:
            # If it fails, push to back of queue to try again later
            queue.append(current_file)
            # print(f"      Deferred: {current_file.name} (dependency missing?)")

    if queue:
        print(f"[ERROR] Could not compile the following files after {max_retries} attempts:")
        for f in queue:
            print(f"  - {f.name}")
        return False

    # 3. Link it all together
    print(f"   Linking {len(obj_files)} object files into {exe_name}...")
    target_exe = bin_dir / exe_name
    
    # Link command
    link_cmd = ["gfortran", "-static", "-o", str(target_exe)] + [str(o) for o in obj_files]
    
    try:
        subprocess.run(link_cmd, check=True)
        print(f"   [SUCCESS] Executable created: {target_exe}")
        
        # Make executable
        os.chmod(target_exe, 0o755)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Linking failed: {e}")
        return False

def setup_aermod():
    base_dir = Path(__file__).parent.resolve()
    bin_dir = base_dir / "bin"
    bin_dir.mkdir(exist_ok=True)
    
    print("--- AERMOD/AERMET SETUP (LINUX) ---")
    
    if not sys.platform.startswith('linux'):
        print("[ERROR] This script is optimized for Linux. For Windows, simply download the executables.")
        return

    if not check_gfortran():
        print("[ERROR] 'gfortran' compiler not found.")
        print("   Please run: sudo apt update && sudo apt install gfortran")
        return

    # =========================================================================
    # BUILD AERMET
    # =========================================================================
    print("\n[1/2] Building AERMET...")
    aermet_src_dir = bin_dir / 'aermet_source'
    
    # Wipe and Re-create source dir
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
        
        # AERMOD often extracts into a subfolder, move files up if needed
        # (Though compile_linux uses rglob so it finds them anywhere)
        
        compile_linux(bin_dir, aermod_src_dir, "aermod")

    except Exception as e:
        print(f"[ERROR] AERMOD Build Failed: {e}")

if __name__ == "__main__":
    main()

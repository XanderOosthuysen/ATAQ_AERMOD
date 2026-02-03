import subprocess
import shutil
import os
import math
from pathlib import Path
from src.inventory_manager import InventoryManager

class AermodRunner:
    def __init__(self, config):
        self.cfg = config
        self.year = config['project']['year']
        self.project_name = config['project']['name']
        self.station = config['project'].get('station_name', 'Station')
        
        self.project_root = Path(__file__).parent.parent
        
        # 1. SOURCE: Met Data (Processed)
        # Looks in: data/met/processed/{station_name}
        self.met_dir = self.project_root / "data" / "met" / "processed" / self.station
        
        # 2. DESTINATION: Final Output
        # Goes to: data/model_output/{Project_Name}
        self.output_dir = self.project_root / "data" / "model_output" / self.project_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. SANDBOX: Execution Directory
        # Runs in: data/model/run/{Project}/{Year}
        self.run_dir = self.project_root / "data" / "model" / "run" / self.project_name / str(self.year)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        # 4. EXECUTABLE
        self.exe_path = Path(config['paths']['aermod_exe']).resolve()
        if not self.exe_path.exists():
            bin_path = self.project_root / "bin" / "aermod"
            if os.name == 'nt': bin_path = bin_path.with_suffix('.exe')
            self.exe_path = bin_path

        self.params = config['aermod_params']

    def _generate_receptors(self):
        """Generates the GRIDCART block using strict float formatting."""
        print("    -> Generating Receptor Grid...")
        
        # Defaults if missing in config
        grid = self.params.get('receptor_grid', {'range_m': 5000, 'spacing_m': 500})
        rng = float(grid.get('range_m', 5000))
        spc = float(grid.get('spacing_m', 500))
        
        # Calculate Number of Points
        # Formula: (Range * 2) / Spacing + 1
        num_pts = int((rng * 2) / spc) + 1
        
        # Format as strict strings to avoid E105 error
        start_val = f"-{rng:.1f}"
        delta = f"{spc:.1f}"
        
        # Block Construction
        re_block = [
            "RE STARTING",
            "   ELEVUNIT METERS",
            "   GRIDCART NET1 STA",
            f"   GRIDCART XYINC    {start_val} {num_pts} {delta} {start_val} {num_pts} {delta}",
            "   GRIDCART NET1 END",
            "RE FINISHED"
        ]
        
        return re_block

    def _write_input_file(self):
        print("    -> Generating AERMOD.INP...")
        
        # 1. CONTROL PATHWAY (CO)
        co_block = [
            "CO STARTING",
            f"   TITLEONE  {self.project_name} - Year {self.year}",
            f"   MODELOPT  CONC FLAT", 
            f"   AVERTIME  1 24", 
            f"   POLLUTID  {self.params.get('pollutant', 'SO2')}",
            "   RUNORNOT  RUN",
            "   ERRORFIL  aermod.err",
            "CO FINISHED"
        ]

        # 2. SOURCE PATHWAY (SO)
        inv_man = InventoryManager(self.cfg)
        so_block = inv_man.generate_all_sources()
        
        # Fallback if inventory is empty
        if len(so_block) <= 3:
            print("[WARNING] Inventory empty. Adding dummy source to prevent crash.")
            so_block = [
                "SO STARTING",
                "   LOCATION STACK1 POINT 0.0 0.0 0.0",
                "   SRCPARAM STACK1 1.0 10.0 300.0 10.0 1.0",
                "   SRCGROUP ALL",
                "SO FINISHED"
            ]

        # 3. RECEPTOR PATHWAY (RE)
        re_block = self._generate_receptors()

        # 4. METEOROLOGY PATHWAY (ME)
        sfc_file = f"AM_{self.year}.SFC"
        pfl_file = f"AM_{self.year}.PFL"
        
        # PROFBASE Fix: Ensure it is a float string (e.g. "1600.0")
        prof_elev = float(self.cfg['location'].get('elevation', 0.0))
        
        me_block = [
            "ME STARTING",
            f"   SURFFILE  {sfc_file}",
            f"   PROFFILE  {pfl_file}",
            f"   SURFDATA  99999 {self.year}",
            f"   UAIRDATA  99999 {self.year}",
            f"   SITEDATA  99999 {self.year}",
            f"   PROFBASE  {prof_elev:.1f} METERS", 
            "ME FINISHED"
        ]

        # 5. OUTPUT PATHWAY (OU)
        ou_block = [
            "OU STARTING",
            "   RECTABLE ALLAVE FIRST-SECOND",
            f"   PLOTFILE 1 ALL 1ST {self.project_name}_{self.year}_01H.PLT",
            f"   PLOTFILE 24 ALL 1ST {self.project_name}_{self.year}_24H.PLT",
            "OU FINISHED"
        ]
        
        full_inp = "\n".join(co_block + [""] + so_block + [""] + re_block + [""] + me_block + [""] + ou_block)
        
        inp_path = self.run_dir / "aermod.inp"
        with open(inp_path, "w") as f:
            f.write(full_inp)
        
        return "aermod.inp"

    def run(self):
        print(f"\n[PHASE 4] Running AERMOD Model for {self.year}...")
        
        # 1. Stage Met Data (Copy to Sandbox)
        src_sfc = self.met_dir / f"AM_{self.year}.SFC"
        src_pfl = self.met_dir / f"AM_{self.year}.PFL"
        
        if not src_sfc.exists() or not src_pfl.exists():
            print(f"[ERROR] Met data missing for {self.year} in {self.met_dir}")
            return

        shutil.copy(src_sfc, self.run_dir / src_sfc.name)
        shutil.copy(src_pfl, self.run_dir / src_pfl.name)
        
        # 2. Write INP
        inp_name = self._write_input_file()
        
        # 3. Execute
        if not self.exe_path.exists():
             print(f"[ERROR] AERMOD Executable not found at {self.exe_path}")
             return

        try:
            print(f"    -> Executing AERMOD in {self.run_dir.name}...")
            # Run with log capture
            with open(self.run_dir / "aermod.log", "w") as log_file:
                subprocess.run([str(self.exe_path), inp_name], 
                               cwd=self.run_dir,
                               stdout=log_file,
                               stderr=subprocess.STDOUT)
            
            # 4. Check & Move Outputs
            out_file = self.run_dir / "aermod.out"
            err_file = self.run_dir / "aermod.err"
            
            if out_file.exists():
                print("    -> AERMOD Completed.")
                
                # Move Main Output
                shutil.move(out_file, self.output_dir / f"AERMOD_{self.year}.out")
                
                if err_file.exists():
                     shutil.move(err_file, self.output_dir / f"AERMOD_{self.year}.err")

                # Move PLT files
                count = 0
                for plt in self.run_dir.glob("*.PLT"):
                    dest = self.output_dir / plt.name
                    if dest.exists(): os.remove(dest)
                    shutil.move(plt, dest)
                    count += 1
                    
                if count > 0:
                    print(f"    -> Success! {count} Plot files moved to: {self.output_dir}")
                else:
                    print("[WARNING] No .PLT files generated. Check .out or .err file.")
                
                # Cleanup Sandbox (Commented out for debugging)
                # os.remove(self.run_dir / src_sfc.name)
                # os.remove(self.run_dir / src_pfl.name)
                # os.remove(self.run_dir / "aermod.inp")
                
            else:
                print("[CRITICAL] AERMOD failed to run. No output file created.")
                print(f"           Check logs in {self.run_dir}")

        except Exception as e:
            print(f"[ERROR] Model execution failed: {e}")

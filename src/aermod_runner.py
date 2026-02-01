import subprocess
import shutil
import os
from pathlib import Path

class AermodRunner:
    def __init__(self, config):
        self.cfg = config
        self.year = config['project']['year']
        
        # Paths
        self.interim_dir = Path(config['paths']['interim_dir']).resolve()
        self.proc_dir = Path(config['paths']['processed_dir']).resolve()
        self.output_dir = Path(config['paths']['output_dir']).resolve()
        self.exe_path = Path(config['paths']['aermod_exe']).resolve()
        
        # Parameters
        self.params = config['aermod_params']
        self.run_dir = self.interim_dir

    def _write_input_file(self):
        print("    -> Generating AERMOD.INP...")
        
        # 1. CONTROL PATHWAY (CO)
        # Removed PERIOD to suppress multi-year warnings
        co_block = [
            "CO STARTING",
            f"   TITLEONE  {self.params['title']}",
            f"   MODELOPT  CONC FLAT", 
            f"   AVERTIME  1 24", 
            f"   POLLUTID  {self.params['pollutant']}",
            "   RUNORNOT  RUN",
            "CO FINISHED"
        ]

        # 2. SOURCE PATHWAY (SO)
        src = self.params['source']
        so_block = [
            "SO STARTING",
            f"   LOCATION  {src['id']} POINT {src['x_coord']} {src['y_coord']} {src['elevation']}",
            f"   SRCPARAM  {src['id']} {src['emission_rate']} {src['height']} {src['temp_k']} {src['velocity']} {src['diameter']}",
            "   SRCGROUP  ALL",
            "SO FINISHED"
        ]

        # 3. RECEPTOR PATHWAY (RE)
        # STRICT FORMATTING FIX: Ensure Coordinates are Floats (e.g., -2000.0)
        rng = float(self.params['receptor_grid']['range_m'])
        spc = float(self.params['receptor_grid']['spacing_m'])
        num_pts = int((rng * 2) / spc) + 1
        
        start_val = f"-{rng:.1f}"
        delta = f"{spc:.1f}"
        
        re_block = [
            "RE STARTING",
            "   GRIDCART NET1 STA",
            f"   XYINC    {start_val} {num_pts} {delta} {start_val} {num_pts} {delta}",
            "   END",
            "RE FINISHED"
        ]

        # 4. METEOROLOGY PATHWAY (ME)
        sfc_file = self.proc_dir / f"AM_{self.year}.SFC"
        pfl_file = self.proc_dir / f"AM_{self.year}.PFL"
        
        # PROFBASE FIX: Default to 1600.0 if missing, ensures float formatting
        prof_elev = float(self.cfg['location'].get('elevation', 1600.0))

        me_block = [
            "ME STARTING",
            f"   SURFFILE  {sfc_file}",
            f"   PROFFILE  {pfl_file}",
            f"   SURFDATA  99999 {self.year}",
            f"   UAIRDATA  99999 {self.year}",
            f"   PROFBASE  {prof_elev:.1f} METERS",
            "ME FINISHED"
        ]

        # 5. OUTPUT PATHWAY (OU)
        ou_block = [
            "OU STARTING",
            "   RECTABLE  ALLAVE  FIRST",
            f"   PLOTFILE  1  ALL  FIRST  {self.year}_1HR_CONC.PLT",
            f"   PLOTFILE  24 ALL  FIRST  {self.year}_24HR_CONC.PLT",
            "OU FINISHED"
        ]

        full_inp = "\n".join(co_block + [""] + so_block + [""] + re_block + [""] + me_block + [""] + ou_block)
        
        inp_path = self.run_dir / "aermod.inp"
        with open(inp_path, "w") as f:
            f.write(full_inp)
        
        return "aermod.inp"

    def run(self):
        print(f"\n[PHASE 4] Running AERMOD Model...")
        
        inp_name = self._write_input_file()
        
        try:
            print(f"    -> Executing AERMOD...")
            # Run AERMOD (Assuming 'aermod' executable name)
            result = subprocess.run([str(self.exe_path), inp_name], 
                                    cwd=self.run_dir,
                                    capture_output=True, text=True)
            
            # Check for success by looking for output files
            out_file = self.run_dir / "aermod.out"
            
            # Print standard output regardless of success (helps debug)
            if result.stdout:
                print(result.stdout)

            if out_file.exists():
                print("    -> AERMOD Completed.")
                shutil.move(out_file, self.output_dir / f"AERMOD_{self.year}.out")
                
                # Move Plot Files
                count = 0
                for plt in self.run_dir.glob("*.PLT"):
                    shutil.move(plt, self.output_dir / plt.name)
                    count += 1
                    
                if count > 0:
                    print(f"    -> Success! {count} Plot files moved to: {self.output_dir}")
                else:
                    print("[WARNING] No .PLT files generated. Check aermod.out for fatal errors.")
            else:
                print("[ERROR] AERMOD output file not found.")
                print(result.stderr)

        except Exception as e:
            print(f"[ERROR] Execution failed: {e}")

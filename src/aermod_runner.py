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
        self.met_dir = self.project_root / "data" / "met" / "processed" / self.station
        self.output_dir = self.project_root / "data" / "model_output" / self.project_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Sandbox: data/model/run/{Project}/{Year}
        self.run_dir = self.project_root / "data" / "model" / "run" / self.project_name / str(self.year)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        self.exe_path = Path(config['paths']['aermod_exe']).resolve()
        self.params = config['aermod_params']

    def _generate_receptors(self):
        """Generates the GRIDCART block using strict float formatting."""
        print("    -> Generating Receptor Grid...")
        grid = self.params.get('receptor_grid', {'range_m': 5000, 'spacing_m': 500})
        rng = float(grid.get('range_m', 5000))
        spc = float(grid.get('spacing_m', 500))
        num_pts = int((rng * 2) / spc) + 1
        start_val = f"-{rng:.1f}"
        delta = f"{spc:.1f}"
        
        return [
            "RE STARTING",
            "   ELEVUNIT METERS",
            "   GRIDCART NET1 STA",
            f"   XYINC    {start_val} {num_pts} {delta} {start_val} {num_pts} {delta}",
            "   END",
            "RE FINISHED"
        ]

    def _write_input_file(self, pollutant, avg_times):
        """
        Generates AERMOD.INP specific to the current pollutant loop.
        avg_times: list of strings e.g. ['1', '24', 'ANNUAL']
        """
        print(f"    -> Generating AERMOD.INP for {pollutant}...")
        
        # 1. CONTROL PATHWAY
        # Format AVERTIME: "AVERTIME 1 24 ANNUAL"
        avg_str = " ".join(avg_times)
        
        co_block = [
            "CO STARTING",
            f"   TITLEONE  {self.project_name} - {self.year} - {pollutant}",
            f"   MODELOPT  CONC FLAT", 
            f"   AVERTIME  {avg_str}", 
            f"   POLLUTID  {pollutant}",
            "   RUNORNOT  RUN",
            "   ERRORFIL  aermod.err",
            "CO FINISHED"
        ]

        # 2. SOURCE PATHWAY
        inv_man = InventoryManager(self.cfg)
        so_block = inv_man.generate_all_sources()
        if len(so_block) <= 3:
            # Fallback dummy
            so_block = [
                "SO STARTING",
                "   LOCATION STACK1 POINT 0.0 0.0 0.0",
                "   SRCPARAM STACK1 1.0 10.0 300.0 10.0 1.0",
                "   SRCGROUP ALL",
                "SO FINISHED"
            ]

        # 3. RECEPTOR PATHWAY
        re_block = self._generate_receptors()

        # 4. METEOROLOGY PATHWAY
        sfc_file = f"AM_{self.year}.SFC"
        pfl_file = f"AM_{self.year}.PFL"
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

        # 5. OUTPUT PATHWAY
        # Dynamic Plot Files based on Avg Times
        ou_block = ["OU STARTING", "   RECTABLE ALLAVE FIRST-SECOND"]
        
        for avg in avg_times:
            # Clean filename suffix
            suffix = "ANN" if avg == "ANNUAL" else f"{int(avg):02d}H"
            
            # Use 'PERIOD' keyword if ANNUAL, else the number
            aer_key = "ANNUAL" if avg == "ANNUAL" else avg
            
            # Format: {Project}_{Year}_{Pollutant}_{Suffix}.PLT
            fname = f"{self.project_name}_{self.year}_{pollutant}_{suffix}.PLT"
            ou_block.append(f"   PLOTFILE {aer_key} ALL 1ST {fname}")

        ou_block.append("OU FINISHED")
        
        full_inp = "\n".join(co_block + [""] + so_block + [""] + re_block + [""] + me_block + [""] + ou_block)
        
        inp_path = self.run_dir / "aermod.inp"
        with open(inp_path, "w") as f:
            f.write(full_inp)
        
        return "aermod.inp"

    def run(self):
        print(f"\n[PHASE 4] Running AERMOD Model for {self.year}...")
        
        # 0. Check & Stage Met Data
        src_sfc = self.met_dir / f"AM_{self.year}.SFC"
        src_pfl = self.met_dir / f"AM_{self.year}.PFL"
        if not src_sfc.exists() or not src_pfl.exists():
            print(f"[ERROR] Met data missing for {self.year} in {self.met_dir}")
            return
            
        shutil.copy(src_sfc, self.run_dir / src_sfc.name)
        shutil.copy(src_pfl, self.run_dir / src_pfl.name)

        if not self.exe_path.exists():
             print(f"[ERROR] AERMOD Executable not found at {self.exe_path}")
             return

        # 1. LOOP THROUGH POLLUTANTS
        pollutants_config = self.params.get('pollutants', {})
        active_pollutants = [p for p, data in pollutants_config.items() if data.get('enabled', False)]
        
        if not active_pollutants:
            print("[WARNING] No pollutants enabled in config! Running default SO2.")
            active_pollutants = ['SO2']
            pollutants_config = {'SO2': {'avg_times': ['1', '24']}}

        for pol in active_pollutants:
            print(f"\n   >>> MODELING POLLUTANT: {pol} <<<")
            settings = pollutants_config.get(pol, {'avg_times': ['1', '24']})
            avg_times = settings.get('avg_times', ['1', '24'])

            # 2. Write INP for this pollutant
            inp_name = self._write_input_file(pol, avg_times)

            try:
                # 3. Execute
                print(f"    -> Executing AERMOD in sandbox...")
                log_name = f"aermod_{pol}.log"
                with open(self.run_dir / log_name, "w") as log_file:
                    subprocess.run([str(self.exe_path), inp_name], 
                                   cwd=self.run_dir,
                                   stdout=log_file,
                                   stderr=subprocess.STDOUT)
                
                # 4. Handle Outputs
                out_file = self.run_dir / "aermod.out"
                if out_file.exists():
                    # Move Main Output
                    final_out = self.output_dir / f"AERMOD_{self.year}_{pol}.out"
                    shutil.move(out_file, final_out)
                    print(f"    -> Output saved: {final_out.name}")

                    # Move PLT files
                    count = 0
                    for plt in self.run_dir.glob("*.PLT"):
                        # Destination is already named correctly in INP generation
                        dest = self.output_dir / plt.name
                        if dest.exists(): os.remove(dest)
                        shutil.move(plt, dest)
                        count += 1
                    
                    if count > 0:
                        print(f"    -> Success! {count} Plot files moved.")
                    else:
                        print("[WARNING] No .PLT files found.")
                else:
                    print(f"[CRITICAL] AERMOD failed for {pol}. Check {log_name}")

            except Exception as e:
                print(f"[ERROR] Execution failed for {pol}: {e}")

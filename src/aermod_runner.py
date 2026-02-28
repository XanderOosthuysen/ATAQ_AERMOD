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
import subprocess
import shutil
import os
import math
import platform  # <-- Added platform import
from pathlib import Path
from src.inventory_manager import InventoryManager
from src.geotiff_exporter import GeotiffExporter

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
        
        self.run_dir = self.project_root / "data" / "model" / "run" / self.project_name / str(self.year)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        self.exe_path = Path(config['paths']['aermod_exe']).resolve()
        
        # --- NEW: Append .exe on Windows if missing ---
        if platform.system() == "Windows" and self.exe_path.suffix.lower() != '.exe':
            self.exe_path = self.exe_path.with_suffix('.exe')
            
        self.params = config['aermod_params']

    def _generate_receptors(self):
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
            f"   GRIDCART NET1 XYINC {start_val} {num_pts} {delta} {start_val} {num_pts} {delta}",
            "   GRIDCART NET1 END",
            "RE FINISHED"
        ]

    def _write_input_file(self, pollutant, avg_times):
        print(f"    -> Generating AERMOD.INP for {pollutant}...")
        
        avg_str = " ".join(avg_times)
        
        # Retrieve Control Pathway params
        disp_env = self.params.get('dispersion_env', 'RURAL')
        nox_method = self.params.get('nox_method', 'NONE')
        
        # Build MODELOPT dynamically
        modelopt_opts = ["CONC", "FLAT"]
        
        # Only append NOx method if the pollutant is NO2 and it's not NONE
        if pollutant == "NO2" and nox_method != "NONE":
            modelopt_opts.append(nox_method)
            
        modelopt_str = " ".join(modelopt_opts)
        
        co_block = [
            "CO STARTING",
            f"   TITLEONE  {self.project_name} - {self.year} - {pollutant}",
            f"   MODELOPT  {modelopt_str}", 
            f"   AVERTIME  {avg_str}", 
            f"   POLLUTID  {pollutant}",
            "   RUNORNOT  RUN",
        ]
        
        if disp_env == "URBAN":
            co_block.append("   URBANOPT  1000000") 
            
        co_block.append("   ERRORFIL  aermod.err")
        co_block.append("CO FINISHED")

        inv_man = InventoryManager(self.cfg)
        so_block = inv_man.generate_all_sources(pollutant)
        
        # FIX: URBANSRC must be inserted BEFORE the SRCGROUP keyword
        if disp_env == "URBAN":
            insert_idx = -1
            # Find the line index where SRCGROUP is first declared
            for i, line in enumerate(so_block):
                if "SRCGROUP" in line:
                    insert_idx = i
                    break
            
            # Insert URBANSRC right before SRCGROUP, otherwise put it at the end
            if insert_idx != -1:
                so_block.insert(insert_idx, "   URBANSRC  ALL")
            elif so_block and "SO FINISHED" in so_block[-1]:
                so_block.insert(-1, "   URBANSRC  ALL")
            else:
                so_block.append("   URBANSRC  ALL")

        re_block = self._generate_receptors()

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

        ou_block = ["OU STARTING", "   RECTABLE ALLAVE FIRST-SECOND"]
        for avg in avg_times:
            suffix = "ANN" if avg == "ANNUAL" else f"{int(avg):02d}H"
            aer_key = "ANNUAL" if avg == "ANNUAL" else avg
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

        pollutants_config = self.params.get('pollutants', {})
        active_pollutants = [p for p, data in pollutants_config.items() if data.get('enabled', False)]
        
        if not active_pollutants:
            print("[WARNING] No pollutants enabled in config! Running default SO2.")
            active_pollutants = ['SO2']
            pollutants_config = {'SO2': {'avg_times': ['1', '24']}}

        # Initialize Exporter for automatic GeoTIFF generation
        tif_exporter = GeotiffExporter(self.cfg)

        for pol in active_pollutants:
            print(f"\n   >>> MODELING POLLUTANT: {pol} <<<")
            settings = pollutants_config.get(pol, {'avg_times': ['1', '24']})
            avg_times = settings.get('avg_times', ['1', '24'])

            inp_name = self._write_input_file(pol, avg_times)

            try:
                print(f"    -> Executing AERMOD in sandbox...")
                log_name = f"aermod_{pol}.log"
                with open(self.run_dir / log_name, "w") as log_file:
                    subprocess.run([str(self.exe_path), inp_name], 
                                   cwd=self.run_dir,
                                   stdout=log_file,
                                   stderr=subprocess.STDOUT)
                
                out_file = self.run_dir / "aermod.out"
                if out_file.exists():
                    final_out = self.output_dir / f"AERMOD_{self.year}_{pol}.out"
                    shutil.move(out_file, final_out)
                    print(f"    -> Output saved: {final_out.name}")

                    count = 0
                    for plt in self.run_dir.glob("*.PLT"):
                        dest = self.output_dir / plt.name
                        if dest.exists(): os.remove(dest)
                        shutil.move(plt, dest)
                        count += 1
                        
                        # --- NEW: AUTO-EXPORT TO TIF ---
                        print(f"    -> Rendering GeoTIFF...")
                        success, msg = tif_exporter.export(dest)
                        if success:
                            print(f"       + {msg}")
                        else:
                            print(f"       - {msg}")
                    
                    if count > 0:
                        print(f"    -> Success! {count} Plot files moved & rasterized.")
                    else:
                        print("[WARNING] No .PLT files found.")
                else:
                    print(f"[CRITICAL] AERMOD failed for {pol}. Check {log_name}")

            except Exception as e:
                print(f"[ERROR] Execution failed for {pol}: {e}")

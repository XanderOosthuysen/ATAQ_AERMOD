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
import shutil
import subprocess
import pandas as pd
from pathlib import Path

class AermetRunner:
    def __init__(self, config):
        self.cfg = config
        self.year = config['project']['year']
        self.project_root = Path(__file__).parent.parent
        
        # Get Station Name
        station = config['project'].get('station_name', 'Station')
        
        # 1. INPUTS: data/met/interim/{station}
        self.interim_dir = self.project_root / "data" / "met" / "interim" / station
        
        # 2. OUTPUTS: data/met/processed/{station}
        self.proc_dir = self.project_root / "data" / "met" / "processed" / station
        self.proc_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. LOGS/SANDBOX: data/met/aermet_logs/{station}/{year}
        self.run_dir = self.project_root / "data" / "met" / "aermet_logs" / station / str(self.year)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        self.params = config.get('aermet_params', {})
        if 'surf_id' not in self.params: self.params['surf_id'] = '99999'
        if 'ua_id' not in self.params: self.params['ua_id'] = '99999'

    def _prepare_onsite_data(self, csv_path):
        print(f"    -> Formatting Onsite Data in logs folder...")
        df = pd.read_csv(csv_path)
        out_name = f"onsite_{self.year}.dat"
        out_path = self.run_dir / out_name
        
        with open(out_path, 'w') as f:
            for _, row in df.iterrows():
                try:
                    line = (f"{int(row['Year']):4d} {int(row['Month']):2d} {int(row['Day']):2d} {int(row['Hour']):2d} "
                            f"{float(row['Temp_C']):6.1f} {float(row['DewPt_C']):6.1f} "
                            f"{float(row['Press_mb']):7.1f} {float(row['Precip_mm']):6.2f} "
                            f"{float(row['WindSpd_ms']):6.2f} {float(row['WindDir_deg']):6.1f} "
                            f"{int(row['CloudCover']):2d}\n")
                    f.write(line)
                except KeyError as e:
                    print(f"[CRITICAL ERROR] CSV missing column: {e}")
                    raise e
        return out_name

    def _write_input_file(self, ua_filename, onsite_filename):
        print(f"    -> Creating AERMET.inp...")
        lat = self.cfg['location']['latitude']
        lon = self.cfg['location']['longitude']
        lat_char = 'N' if lat >= 0 else 'S'
        lon_char = 'E' if lon >= 0 else 'W'
        lat_lon_str = f"{abs(lat):.3f}{lat_char} {abs(lon):.3f}{lon_char}"
        elev = self.cfg['location'].get('elevation', 0)
        
        start_date = f"{self.year}/01/01"
        end_date = f"{self.year}/12/31"
        
        # Output filenames
        out_sfc = f"AM_{self.year}.SFC"
        out_pfl = f"AM_{self.year}.PFL"
        
        inp_content = [
            "JOB",
            "   REPORT     aermet.rpt",
            "   MESSAGES   aermet.msg",
            "",
            "UPPERAIR",
            f"   DATA       {ua_filename} IGRA",
            "   EXTRACT    ua_extract.dat",
            f"   XDATES     {start_date} TO {end_date}",
            f"   LOCATION   {self.params['ua_id']} {lat_lon_str} -2 {elev}",
            "   QAOUT      ua_qa.out",
            "",
            "ONSITE",
            "   OSHEIGHTS  2.0 10.0",
            f"   DATA       {onsite_filename}",
            f"   LOCATION   {self.params['surf_id']} {lat_lon_str} -2 {elev}",
            f"   XDATES     {start_date} TO {end_date}",
            "   QAOUT      onsite_qa.out",
            "   THRESHOLD  0.5",
            "   READ  1  OSYR OSMO OSDY OSHR TT01 DP01 PRES PRCP WS02 WD02 TSKC",
            "   FORMAT    1  FREE",
            "",
            "METPREP",
            f"   XDATES     {start_date} TO {end_date}",
            "   METHOD     WIND_DIR RANDOM",
            "   NWS_HGT    WIND     10.0",
            f"   OUTPUT     {out_sfc}",
            f"   PROFILE    {out_pfl}",
            ""
        ]

        if 'sectors' in self.params:
            for i, sector in enumerate(self.params['sectors']):
                idx = int(i + 1)
                inp_content.append(f"   FREQ_SECT   ANNUAL {idx}")
                inp_content.append(f"   SECTOR      {idx} {int(sector['start'])} {int(sector['end'])}")
                inp_content.append(f"   SITE_CHAR   1 {idx} {float(sector['albedo']):.2f} {float(sector['bowen']):.2f} {float(sector['roughness']):.2f}")

        with open(self.run_dir / "aermet.inp", "w") as f:
            f.write("\n".join(inp_content))
            
        return "aermet.inp"

    def run(self):
        print(f"\n[PHASE 3] Running AERMET for {self.year}...")
        
        # 1. Stage IGRA (Copy from Interim -> Logs/Sandbox)
        src_ua = self.interim_dir / f"upper_air_{self.year}.igra"
        dst_ua = self.run_dir / "upper_air.igra"
        
        if src_ua.exists():
            shutil.copy(src_ua, dst_ua)
        else:
            print(f"[ERROR] Missing Interim file: {src_ua}")
            return

        # 2. Stage Onsite (CSV -> Logs/Sandbox DAT)
        src_sfc = self.interim_dir / f"surface_data_{self.year}.csv"
        if not src_sfc.exists():
            print(f"[ERROR] Missing Interim file: {src_sfc}")
            return
            
        onsite_name = self._prepare_onsite_data(src_sfc)

        # 3. Create INP
        inp_name = self._write_input_file("upper_air.igra", onsite_name)
        
        # 4. Find Binary
        exe_path = self.project_root / "bin" / "aermet"
        if os.name == 'nt': exe_path = exe_path.with_suffix('.exe')
        
        if not exe_path.exists():
            print(f"[ERROR] Binary not found: {exe_path}")
            return

        # 5. Execute
        try:
            print(f"    -> Executing AERMET in {self.run_dir.name}...")
            result = subprocess.run([str(exe_path), inp_name], 
                                    cwd=self.run_dir, 
                                    capture_output=True, text=True)
            
            # 6. RESULT MANAGEMENT
            out_sfc = f"AM_{self.year}.SFC"
            out_pfl = f"AM_{self.year}.PFL"
            
            if (self.run_dir / out_sfc).exists():
                # A. Move Results to Processed
                shutil.copy(self.run_dir / out_sfc, self.proc_dir / out_sfc)
                shutil.copy(self.run_dir / out_pfl, self.proc_dir / out_pfl)
                print(f"    -> Success! {out_sfc} & {out_pfl} saved to {self.proc_dir}")
                
                # B. CLEANUP
                os.remove(self.run_dir / out_sfc)
                os.remove(self.run_dir / out_pfl)
                if (self.run_dir / "upper_air.igra").exists():
                    os.remove(self.run_dir / "upper_air.igra")
                if (self.run_dir / onsite_name).exists():
                    os.remove(self.run_dir / onsite_name)
                
                print(f"    -> Cleaned up logs folder.")

            else:
                print("[ERROR] AERMET finished but no .SFC file created.")
                print("Check 'aermet.rpt' in the logs folder.")
                print("STDOUT Snippet:", result.stdout[:200])

        except Exception as e:
            print(f"[ERROR] Run failed: {e}")

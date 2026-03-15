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
import platform

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
        self.exe_path = Path(config['paths']['aermet_exe']).resolve()
        if platform.system() == "Windows" and self.exe_path.suffix.lower() != '.exe':
            self.exe_path = self.exe_path.with_suffix('.exe')
    def _prepare_onsite_data(self, csv_path):
        print(f"    -> Formatting Onsite Data in logs folder...")
        df = pd.read_csv(csv_path)
        
        # 1. TRUE TIMEZONE SHIFT
        dt_utc = pd.to_datetime(df[['Year', 'Month', 'Day', 'Hour']])
        dt_lst = dt_utc + pd.Timedelta(hours=2)
        
        df['datetime'] = dt_lst
        df = df.set_index('datetime')
        df = df.drop(columns=['Year', 'Month', 'Day', 'Hour'])
        
        # 2. GENERATE EXTENDED GRID (Includes lookback day for METPREP)
        full_idx = pd.date_range(start=f"{self.year - 1}-12-31 00:00", 
                                 end=f"{self.year}-12-31 23:00", 
                                 freq='h')
        df = df.reindex(full_idx)
        
        # 3. THE BACKFILL SPIN-UP (CRITICAL FIX)
        # We backfill the lookback day and timezone gap with the exact physical weather 
        # of the first valid hour. This provides Fortran with real numbers, preventing math crashes.
        df = df.bfill(limit=48)
        
        # 4. APPLY STRICT AERMET CODES FOR ANY REMAINING GAPS DEEP IN THE YEAR
        aermet_missing = {
            'Temp_C': 999.0,
            'DewPt_C': 999.0,
            'Press_mb': 99999.0,
            'Precip_mm': 999.0,
            'WindSpd_ms': 99.0,
            'WindDir_deg': 999.0,
            'CloudCover': 99
        }
        df = df.fillna(aermet_missing)
        
        df['Year'] = df.index.year
        df['Month'] = df.index.month
        df['Day'] = df.index.day
        df['Hour'] = df.index.hour
        
        # 5. SHIFT MIDNIGHT HOUR 0 TO HOUR 24
        mask = df['Hour'] == 0
        shifted_dates = df.index[mask] - pd.Timedelta(days=1)
        
        df.loc[mask, 'Year'] = shifted_dates.year
        df.loc[mask, 'Month'] = shifted_dates.month
        df.loc[mask, 'Day'] = shifted_dates.day
        df.loc[mask, 'Hour'] = 24
        
        out_name = f"onsite_{self.year}.dat"
        out_path = self.run_dir / out_name
        
        with open(out_path, 'w', newline='\r\n') as f:
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

    def _location_strings(self):
        lat = self.cfg['location']['latitude']
        lon = self.cfg['location']['longitude']
        lat_char = 'N' if lat >= 0 else 'S'
        lon_char = 'E' if lon >= 0 else 'W'
        lat_lon_str = f"{abs(lat):.3f}{lat_char} {abs(lon):.3f}{lon_char}"
        elev = self.cfg['location'].get('elevation', 0)
        return lat_lon_str, elev

    def _write_s1_input(self, ua_filename, onsite_filename):
        """Stage 1/2: Extract and QA upper air and onsite data."""
        print(f"    -> Creating aermet_s1.inp (Stage 1: Extract + QA)...")
        lat_lon_str, elev = self._location_strings()

        extract_start = f"{self.year - 1}/12/31"
        end_date = f"{self.year}/12/31"

        inp_content = [
            "JOB",
            "   REPORT     aermet_s1.rpt",
            "   MESSAGES   aermet_s1.msg",
            "",
            "UPPERAIR",
            f"   DATA       {ua_filename} IGRA",
            "   EXTRACT    ua_extract.dat",
            f"   XDATES     {extract_start} TO {end_date}",
            f"   LOCATION   {self.params['ua_id']} {lat_lon_str} -2 {elev}",
            "   QAOUT      ua_qa.out",
            "",
            "ONSITE",
            "   OSHEIGHTS  2.0 10.0",
            f"   DATA       {onsite_filename}",
            f"   LOCATION   {self.params['surf_id']} {lat_lon_str} 0 {elev}",
            f"   XDATES     {extract_start} TO {end_date}",
            "   QAOUT      onsite_qa.out",
            "   THRESHOLD  0.5",
            "   READ  1  OSYR OSMO OSDY OSHR TT01 DP01 PRES PRCP WS02 WD02 TSKC",
            "   FORMAT    1  FREE",
        ]

        with open(self.run_dir / "aermet_s1.inp", "w", newline='\r\n') as f:
            f.write("\n".join(inp_content))

        return "aermet_s1.inp"

    def _write_s3_input(self):
        """Stage 3: METPREP boundary layer calculations."""
        print(f"    -> Creating aermet_s3.inp (Stage 3: METPREP)...")
        lat_lon_str, elev = self._location_strings()

        process_start = f"{self.year}/01/01"
        end_date = f"{self.year}/12/31"
        out_sfc = f"AM_{self.year}.SFC"
        out_pfl = f"AM_{self.year}.PFL"

        inp_content = [
            "JOB",
            "   REPORT     aermet_s3.rpt",
            "   MESSAGES   aermet_s3.msg",
            "",
            "UPPERAIR",
            "   EXTRACT    ua_extract.dat",
            "   QAOUT      ua_qa.out",
            "",
            "ONSITE",
            "   OSHEIGHTS  2.0 10.0",
            "   QAOUT      onsite_qa.out",
            "   THRESHOLD  0.5",
            "",
            "METPREP",
            f"   XDATES     {process_start} TO {end_date}",
            f"   OUTPUT     {out_sfc}",
            f"   PROFILE    {out_pfl}",
            "   UAWINDOW   -1 4",
        ]

        if 'sectors' in self.params and self.params['sectors']:
            for i, sector in enumerate(self.params['sectors']):
                idx = int(i + 1)
                inp_content.append(f"   FREQ_SECT   ANNUAL {idx}")
                inp_content.append(f"   SECTOR      {idx} {int(sector['start'])} {int(sector['end'])}")
                inp_content.append(f"   SITE_CHAR   1 {idx} {float(sector['albedo']):.2f} {float(sector['bowen']):.2f} {float(sector['roughness']):.2f}")
        else:
            inp_content.append("   FREQ_SECT   ANNUAL 1")
            inp_content.append("   SECTOR      1 0 360")
            inp_content.append("   SITE_CHAR   1 1 0.20 1.0 0.5")

        with open(self.run_dir / "aermet_s3.inp", "w", newline='\r\n') as f:
            f.write("\n".join(inp_content))

        return "aermet_s3.inp"
    
    def _check_msg_for_errors(self, msg_filename):
        """Return a list of E-prefixed error lines from an AERMET message file."""
        msg_path = self.run_dir / msg_filename
        if not msg_path.exists():
            return [f"Message file {msg_filename} not found after run."]
        errors = []
        with open(msg_path, 'r', errors='replace') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1].startswith('E'):
                    errors.append(line.strip())
        return errors

    def _run_aermet(self, inp_name, stage_label):
        """Execute AERMET with the given input file. Returns True on success."""
        print(f"    -> Executing AERMET {stage_label} ({inp_name})...")
        try:
            result = subprocess.run(
                [str(self.exe_path), inp_name],
                cwd=self.run_dir,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"[ERROR] AERMET {stage_label} exited with code {result.returncode}")
                print("STDOUT:", result.stdout[:400])
                return False
            return True
        except Exception as e:
            print(f"[ERROR] AERMET {stage_label} failed to launch: {e}")
            return False

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

        # 3. Find Binary
        if not self.exe_path.exists():
            print(f"[ERROR] Binary not found: {self.exe_path}")
            return

        # 4. Write Stage 1 input and run
        s1_inp = self._write_s1_input("upper_air.igra", onsite_name)
        if not self._run_aermet(s1_inp, "Stage 1"):
            return

        # 5. Guard: confirm Stage 1 produced the intermediate files AERMET needs
        s1_errors = self._check_msg_for_errors("aermet_s1.msg")
        if s1_errors:
            print(f"[ERROR] AERMET Stage 1 reported errors:")
            for e in s1_errors:
                print(f"    {e}")
            return

        for required in ("ua_extract.dat", "onsite_qa.out"):
            if not (self.run_dir / required).exists() or (self.run_dir / required).stat().st_size == 0:
                print(f"[ERROR] Stage 1 did not produce {required}. Check aermet_s1.rpt.")
                return
        print(f"    -> Stage 1 complete. Intermediate files verified.")

        # 6. Write Stage 3 input and run
        s3_inp = self._write_s3_input()
        if not self._run_aermet(s3_inp, "Stage 3"):
            return

        # 7. Result management
        out_sfc = f"AM_{self.year}.SFC"
        out_pfl = f"AM_{self.year}.PFL"

        s3_errors = self._check_msg_for_errors("aermet_s3.msg")
        if s3_errors:
            print(f"[WARNING] AERMET Stage 3 reported errors (check aermet_s3.rpt):")
            for e in s3_errors:
                print(f"    {e}")

        if (self.run_dir / out_sfc).exists():
            shutil.copy(self.run_dir / out_sfc, self.proc_dir / out_sfc)
            shutil.copy(self.run_dir / out_pfl, self.proc_dir / out_pfl)
            print(f"    -> Success! {out_sfc} & {out_pfl} saved to {self.proc_dir}")

            # Cleanup input data files; keep .rpt/.msg/.inp for diagnostics
            for f in [out_sfc, out_pfl, "upper_air.igra", onsite_name,
                      "ua_extract.dat", "ua_qa.out", "onsite_qa.out"]:
                p = self.run_dir / f
                if p.exists():
                    os.remove(p)
            print(f"    -> Cleaned up logs folder.")
        else:
            print("[ERROR] AERMET Stage 3 finished but no .SFC file created.")
            print("Check 'aermet_s3.rpt' and 'aermet_s3.msg' in the logs folder.")
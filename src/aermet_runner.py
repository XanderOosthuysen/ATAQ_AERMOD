import subprocess
import shutil
import pandas as pd
from pathlib import Path

class AermetRunner:
    def __init__(self, config):
        self.cfg = config
        self.year = config['project']['year']
        
        # Resolve Paths from Config
        self.proc_dir = Path(config['paths']['processed_dir']).resolve()
        self.interim_dir = Path(config['paths']['interim_dir']).resolve()
        self.output_dir = Path(config['paths']['output_dir']).resolve()
        
        # Create directories if they don't exist
        for d in [self.proc_dir, self.interim_dir, self.output_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Use interim_dir as the 'sandbox' for the Fortran execution
        self.run_dir = self.interim_dir
        self.params = config['aermet_params']

    def _prepare_onsite_data(self, csv_path):
        print(f"    -> Formatting Onsite Data in interim...")
        df = pd.read_csv(csv_path).fillna(-999)
        out_name = f"onsite_{self.year}.dat"
        out_path = self.run_dir / out_name
        
        with open(out_path, 'w') as f:
            for _, row in df.iterrows():
                # Format with extra spacing for Fortran safety
                line = (f"{int(row['Year']):4d} {int(row['Month']):2d} {int(row['Day']):2d} {int(row['Hour']):2d} "
                        f"{float(row['Temp_C']):6.1f} {float(row['DewPt_C']):6.1f} "
                        f"{float(row['Press_mb']):7.1f} {float(row['Precip_mm']):6.2f} "
                        f"{float(row['WindSpd_ms']):6.2f} {float(row['WindDir_deg']):6.1f} "
                        f"{int(row['CloudCover']):2d}\n")
                f.write(line)
        return out_name
    def _write_input_file(self, ua_filename, onsite_filename):
        print(f"    -> Creating AERMET.inp in interim...")
        
        # Format coordinates for AERMET
        lat = self.cfg['location']['latitude']
        lon = self.cfg['location']['longitude']
        lat_char = 'N' if lat >= 0 else 'S'
        lon_char = 'E' if lon >= 0 else 'W'
        lat_lon_str = f"{abs(lat):.3f}{lat_char} {abs(lon):.3f}{lon_char}"
        
        elev = int(self.cfg['location'].get('elevation', 0))
        start_date = f"{self.year}/01/01"
        end_date = f"{self.year}/12/31"
        
        # Final output names (AERMET will create these in the 'cwd', which is interim)
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
            "",
            # Ensure TSKC is included as the 11th column
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

        # Add Surface Characteristics (SITE_CHAR)
        for i, sector in enumerate(self.params['sectors']):
            idx = int(i + 1)
            inp_content.append(f"   FREQ_SECT   ANNUAL {idx}")
            inp_content.append(f"   SECTOR      {idx} {int(sector['start'])} {int(sector['end'])}")
            inp_content.append(f"   SITE_CHAR   1 {idx} {float(sector['albedo']):.2f} {float(sector['bowen']):.2f} {float(sector['roughness']):.2f}")

        inp_path = self.run_dir / "aermet.inp"
        with open(inp_path, "w") as f:
            f.write("\n".join(inp_content))
        
        return "aermet.inp"
    def run(self):
        print(f"\n[PHASE 3] Running AERMET for {self.year} (Standard Tree Mode)...")
        
        # 1. Stage Upper Air into Interim
        src_ua = self.proc_dir / f"upper_air_{self.year}.igra"
        dst_ua = self.run_dir / "upper_air.igra"
        if src_ua.exists():
            shutil.copy(src_ua, dst_ua)

        # 2. Stage Onsite into Interim
        src_sfc_csv = self.proc_dir / f"surface_data_{self.year}.csv"
        onsite_name = self._prepare_onsite_data(src_sfc_csv)

        # 3. Create Input File (Pointing to interim paths)
        # Note: In the .inp, we keep paths relative to run_dir (interim)
        inp_name = self._write_input_file("upper_air.igra", onsite_name)
        
        exe_path = Path(self.cfg['paths']['aermet_exe']).resolve()
        
        try:
            print(f"    -> Executing AERMET in {self.run_dir.name}...")
            result = subprocess.run([str(exe_path), inp_name], 
                                    cwd=self.run_dir, 
                                    capture_output=True, text=True)
            
            # 4. MOVE FINAL OUTPUTS TO PROCESSED/OUTPUT FOLDERS
            # Move report and messages to data/output
            for f in ['aermet.rpt', 'aermet.msg']:
                if (self.run_dir / f).exists():
                    shutil.move(self.run_dir / f, self.output_dir / f)

            # Move .SFC and .PFL to data/processed
            sfc_file = f"AM_{self.year}.SFC"
            pfl_file = f"AM_{self.year}.PFL"
            for f in [sfc_file, pfl_file]:
                if (self.run_dir / f).exists():
                    shutil.move(self.run_dir / f, self.proc_dir / f)
            
            print(f"    -> Success! Final inputs moved to: {self.proc_dir}")
            print(f"    -> Reports moved to: {self.output_dir}")

        except Exception as e:
            print(f"[ERROR] Execution failed: {e}")

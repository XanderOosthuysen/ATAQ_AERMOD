import xarray as xr
import pandas as pd
import numpy as np
import warnings
from pathlib import Path
import sys
import zipfile
import os

warnings.simplefilter("ignore", category=FutureWarning)

class BaseProcessor:
    def __init__(self, config):
        self.cfg = config
        self.raw_dir = Path(config['paths']['raw_dir']).resolve()
        self.proc_dir = Path(config['paths']['processed_dir']).resolve()
        self.proc_dir.mkdir(parents=True, exist_ok=True)
        
        # DEBUG: Print paths
        print(f"[DEBUG] Raw Dir: {self.raw_dir}")
        print(f"[DEBUG] Proc Dir: {self.proc_dir}")

    def _load_dataset(self, file_path):
        # DEBUG: Print what we are trying to load
        if not file_path.exists():
            print(f"   [MISSING] {file_path.name}")
            return None
        
        try:
            print(f"   [LOADING] {file_path.name}...")
            ds = xr.open_dataset(file_path)
            if 'valid_time' in ds.variables: 
                ds = ds.rename({'valid_time': 'time'})
            return ds
        except Exception as e:
            print(f"   [ERROR] Failed to open {file_path.name}: {e}")
            return None

class SurfaceProcessor(BaseProcessor):
    def process(self, year, lat, lon):
        print(f"\n[PROCESS] Surface Data for {year}...")
        dfs = []
        
        for month in range(1, 13):
            base = f"era5_sfc_{year}_{month:02d}.zip"
            fpath = self.raw_dir / base
            
            if not fpath.exists():
                print(f"   [MISSING] {base}")
                continue

            try:
                print(f"   [PROCESSING ZIP] {base}...")
                with zipfile.ZipFile(fpath, 'r') as zip_ref:
                    members = zip_ref.namelist()
                    # Identify instant vs accum files inside the zip
                    instant_file = [m for m in members if 'instant' in m][0]
                    accum_file = [m for m in members if 'accum' in m][0]
                    
                    zip_ref.extract(instant_file, path=self.proc_dir)
                    zip_ref.extract(accum_file, path=self.proc_dir)
                    
                    p_instant = self.proc_dir / instant_file
                    p_accum = self.proc_dir / accum_file
                    
                    ds_inst = xr.open_dataset(p_instant).sel(latitude=lat, longitude=lon, method='nearest')
                    ds_acc = xr.open_dataset(p_accum).sel(latitude=lat, longitude=lon, method='nearest')
                    
                    ds_combined = xr.merge([ds_inst, ds_acc])
                    df = ds_combined.to_dataframe().reset_index()
                    
                    # Cleanup immediately
                    os.remove(p_instant)
                    os.remove(p_accum)

                if 'valid_time' in df.columns: 
                    df = df.rename(columns={'valid_time': 'time'})
                
                # Conversions
                df['temp_c'] = df['t2m'] - 273.15
                df['dewpt_c'] = df['d2m'] - 273.15
                df['pressure_mbx10'] = df['sp'] / 100.0*10.0 #Aetmet want*10
                df['precip_mm'] = df['tp'] * 1000.0
                df['wind_spd_ms'] = np.sqrt(df['u10']**2 + df['v10']**2)
                df['wind_dir_deg'] = (270 - np.degrees(np.arctan2(df['v10'], df['u10']))) % 360
                df['cloud_cover'] = (df['tcc'] * 10).round().astype(int)

                dfs.append(df)
                print(f"      -> Successfully merged month {month}")

            except Exception as e:
                print(f"   [ERROR] Month {month}: {e}")
                continue

        if dfs:
            # THIS IS THE MISSING PIECE
            self._write_outputs(pd.concat(dfs), year)
        else:
            print("[ERROR] No surface data was successfully merged.")

    def _write_outputs(self, full_df, year):
        full_df = full_df.sort_values('time')
        
        # 1. Onsite CSV remains exactly the same
        onsite_df = pd.DataFrame({
            'Year': full_df['time'].dt.year,
            'Month': full_df['time'].dt.month,
            'Day': full_df['time'].dt.day,
            'Hour': full_df['time'].dt.hour + 1,
            'Temp_C': full_df['temp_c'].round(1),
            'DewPt_C': full_df['dewpt_c'].round(1),
            'Press_mb': full_df['pressure_mbx10'].round(1),
            'Precip_mm': full_df['precip_mm'].round(2),
            'WindSpd_ms': full_df['wind_spd_ms'].round(2),
            'WindDir_deg': full_df['wind_dir_deg'].round(1),
            'CloudCover': full_df['cloud_cover'].astype(int) # Tenths 0-10
        })
        onsite_path = self.proc_dir / f"surface_data_{year}.csv"
        onsite_df.to_csv(onsite_path, index=False)

        # 2. NEW: Generate SURFACE EXTRACT file
        # Format: Year Month Day Hour CloudCover(Tenths)
        # AERMET EXTRACT format is very flexible with whitespace
        ext_path = self.proc_dir / f"surface_{year}.ext"
        print(f"    -> Writing Surface EXTRACT file to {ext_path.name}")
        
        with open(ext_path, 'w') as f:
            for _, row in full_df.iterrows():
                yr = int(row['time'].year)
                mo = int(row['time'].month)
                da = int(row['time'].day)
                hr = int(row['time'].hour) + 1
                # Cloud cover in tenths (0-10)
                cc = int(row['cloud_cover'])
                
                # Standard EXTRACT column order for Cloud Cover is usually 
                # mapped via the input file, but a simple 5-column table is safest:
                # Year Month Day Hour CC
                f.write(f"{yr:4d} {mo:2d} {da:2d} {hr:2d} {cc:2d}\n")
            
            # Trailing newline to satisfy the Fortran parser
            f.write("\n")

class UpperAirProcessor(BaseProcessor):
    def __init__(self, config):
        super().__init__(config)
        self.station_id = config['aermet_params'].get('ua_id', '99999')
        self.ua_format = "IGRA"

    def _write_igra(self, df, output_file):
        # The working 9-Column IGRA v2 Logic (Clean & Duplicate Free)
        print(f"    -> Writing CLEAN IGRA v2 format (9 Cols) to {output_file.name}")
        with open(output_file, 'w') as f:
            for timestamp, group in df.groupby('time'):
                header = (f"#{self.station_id:<11s} "
                          f"{timestamp.year:4d} "
                          f"{timestamp.month:02d} "
                          f"{timestamp.day:02d} "
                          f"{timestamp.hour:02d} "
                          f"9999 "
                          f"{len(group):4d}\n")
                f.write(header)

                sorted_group = group.sort_values('pressure_level', ascending=False)
                sorted_group = sorted_group.drop_duplicates(subset=['pressure_level'])
                
                for i, (idx, row) in enumerate(sorted_group.iterrows()):
                    lvl_type = 11 if i == 0 else 10 # 11=Sfc, 10=Upper
                    etime = -9999
                    press = int(row['pressure_level'] * 100)
                    gph = int(row['height_m'])
                    if gph > 99999: gph = 99999
                    temp = int(row['temp_c'] * 10)
                    rh = -9999
                    if pd.notna(row['dewpt_c']):
                        dp_dep = int(max(0, row['temp_c'] - row['dewpt_c']) * 10)
                    else:
                        dp_dep = -9999
                    wdir = int(row['wind_dir'])
                    wspd = int(row['wind_spd_knots'] * 0.514444 * 10)

                    line = (f"{lvl_type:2d} "
                            f"{etime:5d} "
                            f"{press:6d} "
                            f"{gph:5d} "
                            f"{temp:5d} "
                            f"{rh:5d} "
                            f"{dp_dep:5d} "
                            f"{wdir:5d} "
                            f"{wspd:5d}\n")
                    f.write(line)

    def process(self, year, lat, lon):
        print(f"\n[PROCESS] Upper Air Data for {year}...")
        dfs = []
        for month in range(1, 13):
            base = f"era5_ua_{year}_{month:02d}"
            fpath = self.raw_dir / f"{base}.nc"
            if not fpath.exists(): fpath = self.raw_dir / f"{base}.zip"
            
            ds = self._load_dataset(fpath)
            if ds is None: continue
            
            try:
                ds_site = ds.sel(latitude=lat, longitude=lon, method='nearest')
                df = ds_site.to_dataframe().reset_index()
                
                df['height_m'] = df['z'] / 9.80665
                df['temp_c'] = df['t'] - 273.15
                if 'r' in df.columns: df['dewpt_c'] = df['temp_c'] - ((100 - df['r']) / 5)
                else: df['dewpt_c'] = df['temp_c'] - 2
                
                df['wind_spd_knots'] = np.sqrt(df['u']**2 + df['v']**2) * 1.94384
                df['wind_dir'] = (270 - np.degrees(np.arctan2(df['v'], df['u']))) % 360
                
                if 'level' in df.columns: df['pressure_level'] = df['level']
                elif 'pressure_level' in df.index.names: df['pressure_level'] = df.index.get_level_values('pressure_level')

                dfs.append(df[['time','pressure_level','height_m','temp_c','dewpt_c','wind_dir','wind_spd_knots']])
            except: continue

        if dfs:
            full_df = pd.concat(dfs).sort_values(['time','pressure_level'], ascending=[True,False])
            output_path = self.proc_dir / f"upper_air_{year}.igra"
            self._write_igra(full_df, output_path)
            print(f"Success! Output: {output_path}")
        else:
            print("[CRITICAL ERROR] No Upper Air Data loaded.")

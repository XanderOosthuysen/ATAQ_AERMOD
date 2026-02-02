import xarray as xr
import pandas as pd
import numpy as np
import warnings
from pathlib import Path
import zipfile
import tempfile

warnings.simplefilter("ignore", category=FutureWarning)

class BaseProcessor:
    def __init__(self, config):
        self.cfg = config
        self.project_root = Path(__file__).parent.parent
        station = config['project'].get('station_name', 'Station')
        self.raw_dir = self.project_root / "data" / "met" / "raw" / station
        self.proc_dir = Path(config['paths']['processed_dir']).resolve()
        self.proc_dir.mkdir(parents=True, exist_ok=True)

    def _load_dataset(self, base_name):
        nc_path = self.raw_dir / f"{base_name}.nc"
        zip_path = self.raw_dir / f"{base_name}.zip"

        if nc_path.exists():
            try:
                ds = xr.open_dataset(nc_path)
                return self._standardize(ds)
            except Exception as e:
                print(f"    [ERROR] Corrupt NC {nc_path.name}: {e}")

        if zip_path.exists():
            try:
                with zipfile.ZipFile(zip_path, 'r') as z:
                    nc_files = [f for f in z.namelist() if f.endswith('.nc')]
                    if not nc_files: return None
                    temp_dir = tempfile.mkdtemp()
                    extracted_path = z.extract(nc_files[0], path=temp_dir)
                    ds = xr.open_dataset(extracted_path)
                    ds = self._standardize(ds)
                    return ds
            except Exception as e:
                print(f"    [ERROR] Bad ZIP {zip_path.name}: {e}")
        
        # Only warn if neither exists
        return None

    def _standardize(self, ds):
        if 'valid_time' in ds.variables:
            ds = ds.rename({'valid_time': 'time'})
        return ds

class SurfaceProcessor(BaseProcessor):
    def process(self, year, lat, lon):
        print(f"\n[PROCESS] Surface Data for {year}...")
        dfs = []
        
        for month in range(1, 13):
            # MATCHING YOUR FILES: era5_sfc_2023_01
            base_name = f"era5_sfc_{year}_{month:02d}"
            
            ds = self._load_dataset(base_name)
            if ds is None: 
                print(f"    [MISSING] {base_name}")
                continue
            
            try:
                ds_site = ds.sel(latitude=lat, longitude=lon, method='nearest')
                df = ds_site.to_dataframe().reset_index()
                
                # ... (Calculations remain the same) ...
                if 't2m' in df.columns: df['temp_c'] = df['t2m'] - 273.15
                elif '2m_temperature' in df.columns: df['temp_c'] = df['2m_temperature'] - 273.15
                
                if 'd2m' in df.columns: df['dewpt_c'] = df['d2m'] - 273.15
                elif '2m_dewpoint_temperature' in df.columns: df['dewpt_c'] = df['2m_dewpoint_temperature'] - 273.15
                else: df['dewpt_c'] = df['temp_c'] - 2.0
                
                u = df.get('u10', df.get('10m_u_component_of_wind', 0))
                v = df.get('v10', df.get('10m_v_component_of_wind', 0))
                df['wind_spd_ms'] = np.sqrt(u**2 + v**2)
                df['wind_dir'] = (270 - np.degrees(np.arctan2(v, u))) % 360
                
                keep_cols = ['time', 'temp_c', 'dewpt_c', 'wind_spd_ms', 'wind_dir']
                if 'sp' in df.columns: df['pressure_pa'] = df['sp']
                elif 'surface_pressure' in df.columns: df['pressure_pa'] = df['surface_pressure']
                if 'pressure_pa' in df.columns: keep_cols.append('pressure_pa')

                dfs.append(df[keep_cols])
            except Exception as e:
                print(f"    [ERROR] Processing {base_name}: {e}")

        if dfs:
            full_df = pd.concat(dfs).sort_values('time')
            out_path = self.proc_dir / f"SFC_{year}.csv"
            full_df.to_csv(out_path, index=False)
            print(f"    -> Compiled Surface File: {out_path.name}")

class UpperAirProcessor(BaseProcessor):
    def process(self, year, lat, lon):
        print(f"\n[PROCESS] Upper Air Data for {year}...")
        dfs = []
        
        for month in range(1, 13):
            # MATCHING YOUR FILES: era5_ua_2023_01
            base_name = f"era5_ua_{year}_{month:02d}"
            
            ds = self._load_dataset(base_name)
            if ds is None: 
                print(f"    [MISSING] {base_name}")
                continue
            
            try:
                ds_site = ds.sel(latitude=lat, longitude=lon, method='nearest')
                df = ds_site.to_dataframe().reset_index()
                
                # ... (Calculations remain the same) ...
                if 'z' in df.columns: df['height_m'] = df['z'] / 9.80665
                elif 'geopotential' in df.columns: df['height_m'] = df['geopotential'] / 9.80665
                
                if 't' in df.columns: df['temp_c'] = df['t'] - 273.15
                elif 'temperature' in df.columns: df['temp_c'] = df['temperature'] - 273.15
                
                if 'level' in df.columns: df['pressure_level'] = df['level']
                
                cols = ['time', 'pressure_level', 'height_m', 'temp_c']
                if 'u' in df.columns and 'v' in df.columns:
                    df['wind_spd_ms'] = np.sqrt(df['u']**2 + df['v']**2)
                    df['wind_dir'] = (270 - np.degrees(np.arctan2(df['v'], df['u']))) % 360
                    cols.extend(['wind_spd_ms', 'wind_dir'])
                
                available_cols = [c for c in cols if c in df.columns]
                dfs.append(df[available_cols])
            except: continue
            
        if dfs:
            full_df = pd.concat(dfs).sort_values(['time', 'pressure_level'], ascending=[True, False])
            out_path = self.proc_dir / f"UA_{year}.csv"
            full_df.to_csv(out_path, index=False)
            print(f"    -> Compiled Upper Air File: {out_path.name}")

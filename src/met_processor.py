import xarray as xr
import pandas as pd
import numpy as np
import warnings
from pathlib import Path
import zipfile
import os
import shutil

warnings.simplefilter("ignore", category=FutureWarning)

class BaseProcessor:
    def __init__(self, config):
        self.cfg = config
        self.project_root = Path(__file__).parent.parent
        
        # Get Station Name (Default to 'Station' if missing)
        station = config['project'].get('station_name', 'Station')
        
        # 1. Raw Input: data/met/raw/{station}
        self.raw_dir = self.project_root / "data" / "met" / "raw" / station
        
        # 2. Interim Output: data/met/interim/{station}
        self.interim_dir = self.project_root / "data" / "met" / "interim" / station
        self.interim_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. Processed Output: data/met/processed/{station}
        self.proc_dir = self.project_root / "data" / "met" / "processed" / station
        self.proc_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[DEBUG] Raw Dir:     {self.raw_dir}")
        print(f"[DEBUG] Interim Dir: {self.interim_dir}")
        print(f"[DEBUG] Proc Dir:    {self.proc_dir}")

    def _load_dataset(self, file_path):
        if not file_path.exists():
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
    
    def _get_var(self, df, short_name, long_name, default=None):
        if short_name in df.columns: return df[short_name]
        if long_name in df.columns: return df[long_name]
        if default is not None: return default
        raise KeyError(f"Missing {short_name} or {long_name}")

class SurfaceProcessor(BaseProcessor):
    def process(self, year, lat, lon):
        print(f"\n[PROCESS] Surface Data for {year}...")
        dfs = []
        
        for month in range(1, 13):
            base_zip = f"era5_sfc_{year}_{month:02d}.zip"
            base_nc = f"era5_sfc_{year}_{month:02d}.nc"
            fpath_zip = self.raw_dir / base_zip
            fpath_nc = self.raw_dir / base_nc
            temp_extract = self.raw_dir / f"temp_{year}_{month}"

            try:
                if fpath_zip.exists():
                    try:
                        temp_extract.mkdir(exist_ok=True)
                        with zipfile.ZipFile(fpath_zip, 'r') as z:
                            z.extractall(temp_extract)
                        sub_dfs = []
                        for nc in temp_extract.glob("*.nc"):
                            ds = xr.open_dataset(nc)
                            if 'valid_time' in ds.variables: ds = ds.rename({'valid_time': 'time'})
                            ds = ds.sel(latitude=lat, longitude=lon, method='nearest')
                            sub_dfs.append(ds.to_dataframe().reset_index())
                            ds.close()
                        if sub_dfs:
                            df_merged = sub_dfs[0]
                            for other in sub_dfs[1:]:
                                df_merged = pd.merge(df_merged, other, on='time', how='outer', suffixes=('', '_dup'))
                                df_merged = df_merged.loc[:,~df_merged.columns.str.endswith('_dup')]
                            df = df_merged
                        else:
                            continue
                    except: continue
                elif fpath_nc.exists():
                    ds = self._load_dataset(fpath_nc)
                    if ds is None: continue
                    ds_site = ds.sel(latitude=lat, longitude=lon, method='nearest')
                    df = ds_site.to_dataframe().reset_index()
                    ds.close()
                else:
                    continue

                if 'valid_time' in df.columns: df = df.rename(columns={'valid_time': 'time'})
                
                t2m = self._get_var(df, 't2m', '2m_temperature')
                df['temp_c'] = t2m - 273.15
                
                d2m = self._get_var(df, 'd2m', '2m_dewpoint_temperature')
                df['dewpt_c'] = d2m - 273.15
                
                sp = self._get_var(df, 'sp', 'surface_pressure')
                df['pressure_mbx10'] = (sp / 100.0) * 10.0 
                
                tp = self._get_var(df, 'tp', 'total_precipitation', default=0.0)
                df['precip_mm'] = tp * 1000.0
                
                u10 = self._get_var(df, 'u10', '10m_u_component_of_wind', default=0.0)
                v10 = self._get_var(df, 'v10', '10m_v_component_of_wind', default=0.0)
                
                # Wind Fix: 0 deg with wind -> 360
                df['wind_spd_ms'] = np.sqrt(u10**2 + v10**2)
                raw_dir = (270 - np.degrees(np.arctan2(v10, u10))) % 360
                df['wind_dir_deg'] = np.where((raw_dir == 0) & (df['wind_spd_ms'] > 0), 360.0, raw_dir)
                df.loc[df['wind_spd_ms'] == 0, 'wind_dir_deg'] = 0.0
                
                tcc = self._get_var(df, 'tcc', 'total_cloud_cover', default=0.0)
                df['cloud_cover'] = (tcc * 10).round().astype(int)

                dfs.append(df)

            except Exception as e:
                print(f"   [ERROR] Month {month}: {e}")
            finally:
                if temp_extract.exists():
                    try: shutil.rmtree(temp_extract)
                    except: pass

        if dfs:
            self._write_outputs(pd.concat(dfs), year)
        else:
            print(f"[ERROR] No surface data processed for {year}.")

    def _write_outputs(self, full_df, year):
        full_df = full_df.sort_values('time')
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
            'CloudCover': full_df['cloud_cover'].astype(int)
        })
        # Save to INTERIM subfolder
        p = self.interim_dir / f"surface_data_{year}.csv"
        onsite_df.to_csv(p, index=False)
        print(f"    -> Compiled Surface CSV: {p.name}")

class UpperAirProcessor(BaseProcessor):
    def __init__(self, config):
        super().__init__(config)
        self.station_id = config.get('aermet_params', {}).get('ua_id', '99999')

    def _write_igra(self, df, output_file):
        print(f"    -> Writing CLEAN IGRA v2 format to {output_file.name}")
        with open(output_file, 'w') as f:
            for timestamp, group in df.groupby('time'):
                group['press_int'] = (group['pressure_level']).round().astype(int)
                sorted_group = group.sort_values('press_int', ascending=False)
                sorted_group = sorted_group.drop_duplicates(subset=['press_int'])

                header = (f"#{self.station_id:<11s} "
                          f"{timestamp.year:4d} "
                          f"{timestamp.month:02d} "
                          f"{timestamp.day:02d} "
                          f"{timestamp.hour:02d} "
                          f"9999 "
                          f"{len(sorted_group):4d}\n")
                f.write(header)

                for i, (idx, row) in enumerate(sorted_group.iterrows()):
                    lvl_type = 11 if i == 0 else 10
                    press_pa = int(row['press_int'] * 100)
                    gph = int(row['height_m']) if pd.notna(row['height_m']) else -9999
                    if gph > 99999: gph = 99999
                    temp = int(row['temp_c'] * 10) if pd.notna(row['temp_c']) else -9999
                    if pd.notna(row['dewpt_c']) and pd.notna(row['temp_c']):
                        dep = int(max(0, row['temp_c'] - row['dewpt_c']) * 10)
                    else: dep = -9999
                    
                    wdir = int(row['wind_dir']) if pd.notna(row['wind_dir']) else -9999
                    if wdir == 0 and row['wind_spd_knots'] > 0: wdir = 360 # Fix for UA too
                    
                    wspd = int(row['wind_spd_knots'] * 0.514444 * 10) if pd.notna(row['wind_spd_knots']) else -9999

                    line = (f"{lvl_type:2d} -9999 {press_pa:6d} {gph:5d} {temp:5d} -9999 {dep:5d} {wdir:5d} {wspd:5d}\n")
                    f.write(line)

    def process(self, year, lat, lon):
        print(f"\n[PROCESS] Upper Air Data for {year}...")
        dfs = []
        for month in range(1, 13):
            base_nc = f"era5_ua_{year}_{month:02d}.nc"
            fpath = self.raw_dir / base_nc
            if not fpath.exists(): 
                 fpath = self.raw_dir / f"era5_ua_{year}_{month:02d}.zip"
            
            ds = self._load_dataset(fpath)
            if ds is None: continue
            
            try:
                ds_site = ds.sel(latitude=lat, longitude=lon, method='nearest')
                df = ds_site.to_dataframe().reset_index()
                
                z = self._get_var(df, 'z', 'geopotential')
                df['height_m'] = z / 9.80665
                
                t = self._get_var(df, 't', 'temperature')
                df['temp_c'] = t - 273.15
                
                try:
                    r = self._get_var(df, 'r', 'relative_humidity')
                    df['dewpt_c'] = df['temp_c'] - ((100 - r) / 5)
                except KeyError:
                    df['dewpt_c'] = df['temp_c'] - 2
                
                u = self._get_var(df, 'u', 'u_component_of_wind', 0)
                v = self._get_var(df, 'v', 'v_component_of_wind', 0)
                df['wind_spd_knots'] = np.sqrt(u**2 + v**2) * 1.94384
                df['wind_dir'] = (270 - np.degrees(np.arctan2(v, u))) % 360
                
                if 'level' in df.columns: df['pressure_level'] = df['level']
                elif 'pressure_level' in df.index.names: df['pressure_level'] = df.index.get_level_values('pressure_level')

                dfs.append(df[['time','pressure_level','height_m','temp_c','dewpt_c','wind_dir','wind_spd_knots']])
                ds.close()
            except Exception as e: 
                continue

        if dfs:
            full_df = pd.concat(dfs).sort_values(['time','pressure_level'], ascending=[True,False])
            # Save to INTERIM subfolder
            output_path = self.interim_dir / f"upper_air_{year}.igra"
            self._write_igra(full_df, output_path)
            print(f"    -> Compiled Upper Air IGRA: {output_path.name}")
        else:
            print(f"[ERROR] No Upper Air data processed for {year}.")

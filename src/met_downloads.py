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
import cdsapi
import os
from pathlib import Path
import shutil
import sys

class ERA5Downloader:
    def __init__(self, overwrite=False):
        self.force_overwrite = overwrite
        self.client = cdsapi.Client()
        self.project_root = Path(__file__).parent.parent
        self.met_root = self.project_root / "data" / "met"

    def _get_storage_dir(self, station_name):
        store_dir = self.met_root / "raw" / station_name
        store_dir.mkdir(parents=True, exist_ok=True)
        return store_dir

    def _smart_rename(self, temp_path, final_path):
        if not temp_path.exists(): return
        
        # Default to .nc, check magic bytes for zip
        ext = ".nc"
        try:
            with open(temp_path, 'rb') as f:
                header = f.read(4)
            if header.startswith(b'PK'):
                ext = ".zip"
        except: pass

        final_with_ext = final_path.with_suffix(ext)
        if final_with_ext.exists(): os.remove(final_with_ext)
            
        temp_path.rename(final_with_ext)
        print(f"    -> Saved as: {final_with_ext.name}")

    def _check_existing_batch(self, save_dir, year, prefix):
        """
        Scans for existing files (e.g., era5_sfc_2023_01.zip)
        """
        import sys  # Ensure sys is available for the TTY check

        count = 0
        for m in range(1, 13):
            # MATCHING YOUR NAMING CONVENTION HERE
            base = f"{prefix}_{year}_{m:02d}"
            if (save_dir / f"{base}.nc").exists() or (save_dir / f"{base}.zip").exists():
                count += 1
        
        if count == 0: return False 

        if getattr(self, 'force_overwrite', False):
            print(f"    [INFO] Force overwrite active. Deleting {count} existing files...")
            return True

        print(f"\n    [?] Found {count}/12 existing files for {year} in {save_dir.name}.")
        
        # --- NEW: GUI / Non-Interactive Check ---
        # If there is no active terminal attached (like when running from the GUI),
        # automatically answer 'Yes' to keeping existing data to prevent freezing.
        if not sys.stdin.isatty():
            print("        -> [GUI Mode] Auto-keeping existing files.")
            return False

        # --- EXISTING: Command Line Check ---
        while True:
            response = input("        Use existing data? [Y/n]: ").strip().lower()
            if response in ['', 'y', 'yes']:
                print("        -> Keeping existing files.")
                return False 
            elif response in ['n', 'no']:
                print("        -> Refreshing data.")
                return True

    def download_surface(self, year, station_name, lat, lon, buffer=0.25):
        save_dir = self._get_storage_dir(station_name)
        print(f"\n[DOWNLOAD] Surface Data for {year} -> {save_dir.name}")

        # Prefix matched to your files: 'era5_sfc'
        batch_overwrite = self._check_existing_batch(save_dir, year, "era5_sfc")
        area = [lat + buffer, lon - buffer, lat - buffer, lon + buffer]

        for month in range(1, 13):
            month_str = f"{month:02d}"
            # MATCHING YOUR NAMING CONVENTION
            base_name = f"era5_sfc_{year}_{month_str}"
            final_path_base = save_dir / base_name
            
            exists = (save_dir / f"{base_name}.nc").exists() or (save_dir / f"{base_name}.zip").exists()
            
            if exists:
                if batch_overwrite:
                    if (save_dir / f"{base_name}.nc").exists(): os.remove(save_dir / f"{base_name}.nc")
                    if (save_dir / f"{base_name}.zip").exists(): os.remove(save_dir / f"{base_name}.zip")
                else:
                    print(f"    -> Skipping {base_name} (Exists)")
                    continue

            print(f"    -> Requesting {base_name}...")
            temp_file = save_dir / f"{base_name}_temp"
            
            try:
                self.client.retrieve(
                    'reanalysis-era5-single-levels',
                    {
                        'product_type': 'reanalysis', 'format': 'netcdf',
                        'variable': [
                            '2m_temperature', '2m_dewpoint_temperature', 'surface_pressure',
                            '10m_u_component_of_wind', '10m_v_component_of_wind',
                            'total_cloud_cover', 'boundary_layer_height',
                            'forecast_surface_roughness', 'surface_sensible_heat_flux',
                            'friction_velocity'
                        ],
                        'year': str(year), 'month': month_str,
                        'day': [f"{i:02d}" for i in range(1, 32)],
                        'time': [f"{i:02d}:00" for i in range(24)],
                        'area': area,
                    },
                    str(temp_file)
                )
                self._smart_rename(temp_file, final_path_base)
            except Exception as e:
                print(f"[ERROR] Failed {base_name}: {e}")
                if temp_file.exists(): os.remove(temp_file)

    def download_upper_air(self, year, station_name, lat, lon, buffer=0.25):
        save_dir = self._get_storage_dir(station_name)
        print(f"\n[DOWNLOAD] Upper Air Data for {year} -> {save_dir.name}")
        
        # Prefix matched to your files: 'era5_ua'
        batch_overwrite = self._check_existing_batch(save_dir, year, "era5_ua")
        
        area = [lat + buffer, lon - buffer, lat - buffer, lon + buffer]
        levels = ['1000', '975', '950', '925', '900', '875', '850', '825', 
                  '800', '775', '750', '700', '650', '600', '550', '500']

        for month in range(1, 13):
            month_str = f"{month:02d}"
            # MATCHING YOUR NAMING CONVENTION
            base_name = f"era5_ua_{year}_{month_str}"
            final_path_base = save_dir / base_name
            
            exists = (save_dir / f"{base_name}.nc").exists() or (save_dir / f"{base_name}.zip").exists()
            
            if exists:
                if batch_overwrite:
                    if (save_dir / f"{base_name}.nc").exists(): os.remove(save_dir / f"{base_name}.nc")
                    if (save_dir / f"{base_name}.zip").exists(): os.remove(save_dir / f"{base_name}.zip")
                else:
                    print(f"    -> Skipping {base_name} (Exists)")
                    continue

            print(f"    -> Requesting {base_name}...")
            temp_file = save_dir / f"{base_name}_temp"
            
            try:
                self.client.retrieve(
                    'reanalysis-era5-pressure-levels',
                    {
                        'product_type': 'reanalysis', 'format': 'netcdf',
                        'variable': ['temperature', 'geopotential'],
                        'pressure_level': levels,
                        'year': str(year), 'month': month_str,
                        'day': [f"{i:02d}" for i in range(1, 32)],
                        'time': ['00:00', '06:00', '12:00', '18:00'],
                        'area': area,
                    },
                    str(temp_file)
                )
                self._smart_rename(temp_file, final_path_base)
            except Exception as e:
                print(f"[ERROR] Failed {base_name}: {e}")
                if temp_file.exists(): os.remove(temp_file)

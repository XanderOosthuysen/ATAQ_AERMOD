import cdsapi
import os
import calendar
from pathlib import Path

class ERA5Downloader:
    def __init__(self):
        self.c = cdsapi.Client()
        self.project_root = Path(__file__).parent.parent
        self.output_dir = self.project_root / 'data' / 'raw'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _smart_rename(self, temp_path, base_name):
        """Helper to determine if file is .zip or .nc"""
        if not temp_path.exists(): return
        
        with open(temp_path, 'rb') as f:
            header = f.read(4)

        if header.startswith(b'PK'): extension = '.zip'
        elif header.startswith(b'\x89HDF'): extension = '.nc'
        else: extension = '.nc' 

        final_path = self.output_dir / f"{base_name}{extension}"
        if final_path.exists(): os.remove(final_path)
        temp_path.rename(final_path)
        print(f"    -> Saved as: {final_path.name}")

    def download_surface(self, year, lat, lon, area_buffer=0.25):
        print(f"\n[DOWNLOAD] Starting Surface Data for {year}...")
        area = [lat + area_buffer, lon - area_buffer, lat - area_buffer, lon + area_buffer]

        for month in range(1, 13):
            month_str = f"{month:02d}"
            base_name = f'era5_sfc_{year}_{month_str}'
            
            if (self.output_dir / f"{base_name}.zip").exists() or \
               (self.output_dir / f"{base_name}.nc").exists():
                print(f"  Skipping {month_str} (Exists)")
                continue

            print(f"  Requesting {month_str}...")
            temp_file = self.output_dir / f"{base_name}_temp"
            try:
                self.c.retrieve(
                    'reanalysis-era5-single-levels',
                    {
                        'product_type': 'reanalysis', 'format': 'netcdf',
                        'variable': ['2m_temperature', '2m_dewpoint_temperature', 
                                     '10m_u_component_of_wind', '10m_v_component_of_wind',
                                     'surface_pressure', 'total_cloud_cover', 'total_precipitation',
                                     'boundary_layer_height', 'friction_velocity', 'surface_sensible_heat_flux'],
                        'year': str(year), 'month': month_str,
                        'day': [f"{i:02d}" for i in range(1, 32)],
                        'time': [f"{i:02d}:00" for i in range(0, 24)],
                        'area': area, 
                    }, str(temp_file))
                self._smart_rename(temp_file, base_name)
            except Exception as e: print(f"  Error {month_str}: {e}")

    def download_upper_air(self, year, lat, lon, area_buffer=0.25):
        print(f"\n[DOWNLOAD] Starting Upper Air Data for {year}...")
        area = [lat + area_buffer, lon - area_buffer, lat - area_buffer, lon + area_buffer]
        levels = ['1000', '975', '950', '925', '900', '875', '850', '825', 
                  '800', '775', '750', '700', '650', '600', '550', '500']

        for month in range(1, 13):
            month_str = f"{month:02d}"
            base_name = f'era5_ua_{year}_{month_str}'
            
            if (self.output_dir / f"{base_name}.zip").exists() or \
               (self.output_dir / f"{base_name}.nc").exists():
                print(f"  Skipping {month_str} (Exists)")
                continue

            print(f"  Requesting {month_str}...")
            temp_file = self.output_dir / f"{base_name}_temp"
            try:
                self.c.retrieve(
                    'reanalysis-era5-pressure-levels',
                    {
                        'product_type': 'reanalysis', 'format': 'netcdf',
                        'variable': ['geopotential', 'temperature', 
                                     'u_component_of_wind', 'v_component_of_wind', 
                                     'relative_humidity'],
                        'pressure_level': levels,
                        'year': str(year), 'month': month_str,
                        'day': [f"{i:02d}" for i in range(1, 32)],
                        'time': ['00:00', '12:00'], # Optimized
                        'area': area,
                    }, str(temp_file))
                self._smart_rename(temp_file, base_name)
            except Exception as e: print(f"  Error {month_str}: {e}")

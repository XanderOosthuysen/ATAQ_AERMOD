import pandas as pd
import numpy as np
from pathlib import Path
from scipy.interpolate import griddata
import pyproj
import rasterio
from rasterio.transform import from_bounds

class GeotiffExporter:
    def __init__(self, config):
        self.config = config
        
        # 1. Setup Coordinate System
        lat = float(self.config['location'].get('latitude', 0.0))
        lon = float(self.config['location'].get('longitude', 0.0))
        
        zone = int((lon + 180) / 6) + 1
        south = lat < 0
        
        self.wgs84 = pyproj.CRS("EPSG:4326")
        utm_str = f"+proj=utm +zone={zone} {'+south' if south else ''} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
        self.utm_crs = pyproj.CRS.from_string(utm_str)
        
        self.transformer = pyproj.Transformer.from_crs(self.wgs84, self.utm_crs, always_xy=True)
        self.center_x, self.center_y = self.transformer.transform(lon, lat)

    def export(self, plt_path):
        """Converts a PLT file into a GeoTIFF."""
        plt_path = Path(plt_path)
        if not plt_path.exists():
            return False, f"File not found: {plt_path.name}"

        try:
            # Read PLT file
            df = pd.read_csv(plt_path, sep=r'\s+', comment='*', header=None)
            df = df.iloc[:, :3]
            df.columns = ['x', 'y', 'conc']
            
            # Convert relative grid coordinates to absolute UTM
            x_abs = df['x'].values + self.center_x
            y_abs = df['y'].values + self.center_y
            z = df['conc'].values

            # Define high-resolution raster grid (500x500 pixels)
            res = 500 
            xi = np.linspace(x_abs.min(), x_abs.max(), res)
            yi = np.linspace(y_abs.min(), y_abs.max(), res)
            Xi, Yi = np.meshgrid(xi, yi)
            
            # Interpolate
            Zi = griddata((x_abs, y_abs), z, (Xi, Yi), method='linear')
            
            # Replace NaNs (outside convex hull) with a NoData value
            nodata_val = -9999.0
            Zi = np.nan_to_num(Zi, nan=nodata_val)

            # Raster arrays are written top-to-bottom. Meshgrid Y goes bottom-to-top.
            # We must flip the array vertically.
            Zi = np.flipud(Zi)

            # Calculate spatial transform
            minx, maxx = x_abs.min(), x_abs.max()
            miny, maxy = y_abs.min(), y_abs.max()
            transform = from_bounds(minx, miny, maxx, maxy, res, res)
            
            # Write GeoTIFF
            out_path = plt_path.with_suffix('.tif')
            with rasterio.open(
                out_path, 'w',
                driver='GTiff',
                height=Zi.shape[0],
                width=Zi.shape[1],
                count=1,
                dtype=Zi.dtype,
                crs=self.utm_crs,
                transform=transform,
                nodata=nodata_val
            ) as dst:
                dst.write(Zi, 1)

            return True, f"Exported {out_path.name}"
            
        except Exception as e:
            return False, f"GeoTIFF export failed for {plt_path.name}: {e}"

import pandas as pd
from pathlib import Path
import pyproj
from shapely import wkt

class InventoryManager:
    def __init__(self, config):
        self.cfg = config
        self.inv_paths = config.get('inventory', {})
        
        # Site Location (WGS84)
        lat = float(self.cfg['location'].get('latitude', 0.0))
        lon = float(self.cfg['location'].get('longitude', 0.0))
        
        # Dynamically determine UTM Zone based on Longitude
        zone = int((lon + 180) / 6) + 1
        south = lat < 0
        
        # Setup Coordinate Transformers (WGS84 -> UTM)
        self.wgs84 = pyproj.CRS("EPSG:4326")
        utm_str = f"+proj=utm +zone={zone} {'+south' if south else ''} +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
        self.utm_crs = pyproj.CRS.from_string(utm_str)
        self.transformer = pyproj.Transformer.from_crs(self.wgs84, self.utm_crs, always_xy=True)
        
        # Calculate Site Center in UTM (This acts as the 0,0 origin on our AERMOD grid)
        self.center_x, self.center_y = self.transformer.transform(lon, lat)

    def _convert_coords(self, lon, lat):
        """Converts WGS84 to UTM, then shifts to be relative to the Site Center (0,0)"""
        try:
            x, y = self.transformer.transform(float(lon), float(lat))
            rel_x = x - self.center_x
            rel_y = y - self.center_y
            return rel_x, rel_y
        except Exception as e:
            print(f"[WARNING] Coordinate conversion failed for {lon}, {lat}: {e}")
            return 0.0, 0.0

    def generate_all_sources(self, pollutant):
        """
        Parses inventory files, extracts WKT geometries, 
        and generates the SO block for the specified pollutant.
        """
        so_block = ["SO STARTING"]
        src_ids = []
        
        # ==========================================
        # 1. POINT SOURCES
        # ==========================================
        pt_path = Path(self.inv_paths.get('point', ''))
        if pt_path.exists():
            try:
                df = pd.read_csv(pt_path)
                for _, row in df.iterrows():
                    rate = float(row.get(pollutant, 0.0)) if pd.notna(row.get(pollutant)) else 0.0
                    
                    if rate > 0:
                        sid = str(row['source_id']).strip().replace(" ", "_")
                        src_ids.append(sid)
                        
                        # Parse WKT Point
                        geom = wkt.loads(str(row['WKT']).strip())
                        x, y = self._convert_coords(geom.x, geom.y)
                        
                        elev = float(row.get('elevation', 0.0))
                        hs = float(row.get('stack_height', 0.0))
                        ts = float(row.get('stack_temp_k', 293.0))
                        vs = float(row.get('stack_velocity', 0.0))
                        ds = float(row.get('stack_diameter', 0.0))
                        
                        so_block.append(f"   LOCATION {sid} POINT {x:.2f} {y:.2f} {elev:.1f}")
                        so_block.append(f"   SRCPARAM {sid} {rate:.6f} {hs:.2f} {ts:.2f} {vs:.2f} {ds:.2f}")
            except Exception as e:
                print(f"[ERROR] Failed reading point sources: {e}")

        # ==========================================
        # 2. AREA SOURCES (Now handles True Polygons)
        # ==========================================
        ar_path = Path(self.inv_paths.get('area', ''))
        if ar_path.exists():
            try:
                df = pd.read_csv(ar_path)
                for _, row in df.iterrows():
                    rate = float(row.get(pollutant, 0.0)) if pd.notna(row.get(pollutant)) else 0.0
                    
                    if rate > 0:
                        sid = str(row['source_id']).strip().replace(" ", "_")
                        src_ids.append(sid)
                        
                        # Parse WKT Polygon
                        geom = wkt.loads(str(row['WKT']).strip())
                        
                        # Extract the vertices (exterior ring)
                        coords = list(geom.exterior.coords)
                        
                        # WKT closes the loop by repeating the first coordinate at the end. 
                        # AERMOD doesn't want the duplicated closure point.
                        if coords[0] == coords[-1]:
                            coords = coords[:-1]
                            
                        num_vertices = len(coords)
                        
                        # Convert all vertices to relative UTM
                        utm_coords = [self._convert_coords(lon, lat) for lon, lat in coords]
                        
                        # The LOCATION keyword for AREAPOLY takes the first vertex (x_init, y_init)
                        x_init, y_init = utm_coords[0]
                        
                        elev = float(row.get('elevation', 0.0))
                        rel_ht = float(row.get('release_height', 0.0))
                        szinit = float(row.get('szinit', 0.0))
                        
                        so_block.append(f"   LOCATION {sid} AREAPOLY {x_init:.2f} {y_init:.2f} {elev:.1f}")
                        so_block.append(f"   SRCPARAM {sid} {rate:.6f} {rel_ht:.2f} {num_vertices} {szinit:.2f}")
                        
                        # Generate AREAVERT lines. Chunk to max 4 points per line to avoid Fortran line limits
                        vert_str = ""
                        for i, (x, y) in enumerate(utm_coords):
                            vert_str += f"{x:.2f} {y:.2f} "
                            # Write line if we have 4 pairs, or if it's the last vertex
                            if (i + 1) % 4 == 0 or (i + 1) == num_vertices:
                                so_block.append(f"   AREAVERT {sid} {vert_str.strip()}")
                                vert_str = ""
            except Exception as e:
                print(f"[ERROR] Failed reading area sources: {e}")

        # ==========================================
        # 3. LINE SOURCES
        # ==========================================
        ln_path = Path(self.inv_paths.get('line', ''))
        if ln_path.exists():
            try:
                df = pd.read_csv(ln_path)
                for _, row in df.iterrows():
                    rate = float(row.get(pollutant, 0.0)) if pd.notna(row.get(pollutant)) else 0.0
                    
                    if rate > 0:
                        sid = str(row['source_id']).strip().replace(" ", "_")
                        src_ids.append(sid)
                        
                        # Parse WKT Linestring
                        geom = wkt.loads(str(row['WKT']).strip())
                        start_coord = geom.coords[0]
                        end_coord = geom.coords[-1]
                        
                        x1, y1 = self._convert_coords(start_coord[0], start_coord[1])
                        x2, y2 = self._convert_coords(end_coord[0], end_coord[1])
                        
                        elev = float(row.get('elevation', 0.0))
                        rel_ht = float(row.get('release_height', 0.0))
                        width = float(row.get('width_m', 10.0))
                        szinit = float(row.get('szinit', 0.0))
                        
                        so_block.append(f"   LOCATION {sid} LINE {x1:.2f} {y1:.2f} {x2:.2f} {y2:.2f} {elev:.1f}")
                        so_block.append(f"   SRCPARAM {sid} {rate:.6f} {rel_ht:.2f} {width:.2f} {szinit:.2f}")
            except Exception as e:
                print(f"[ERROR] Failed reading line sources: {e}")

        # ==========================================
        # GROUPING
        # ==========================================
        if src_ids:
            # 'ALL' is a reserved group name. Do not list individual IDs after it.
            so_block.append("   SRCGROUP ALL")
        else:
            print(f"[WARNING] No active sources found for {pollutant}. Adding dummy source.")
            so_block.append("   LOCATION DUMMY POINT 0.0 0.0 0.0")
            so_block.append("   SRCPARAM DUMMY 0.0 10.0 300.0 1.0 1.0")
            so_block.append("   SRCGROUP ALL")
            
        so_block.append("SO FINISHED")
        
        return so_block

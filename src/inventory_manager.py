import pandas as pd
from shapely import wkt
from shapely.geometry import LineString, Polygon
from geopy.distance import geodesic
from pathlib import Path

class InventoryManager:
    def __init__(self, config):
        self.cfg = config
        self.center_lat = config['location']['latitude']
        self.center_lon = config['location']['longitude']
        self.base_elev = config['location'].get('elevation', 0)
        self.target_pollutant = config['aermod_params']['pollutant']
        
        self.inventory_dir = Path(__file__).parent.parent.resolve() / "data" / "inventory"
        
        # File definitions
        self.files = {
            'point': self.inventory_dir / "point_sources.csv",
            'area': self.inventory_dir / "area_sources.csv",
            'line': self.inventory_dir / "line_sources.csv"
        }

    def _latlon_to_xy(self, lat, lon):
        """ Converts Lat/Lon to Local X/Y Meters (relative to site center) """
        dist_y = geodesic((self.center_lat, self.center_lon), (lat, self.center_lon)).meters
        if lat < self.center_lat: dist_y = -dist_y

        dist_x = geodesic((self.center_lat, self.center_lon), (self.center_lat, lon)).meters
        if lon < self.center_lon: dist_x = -dist_x
            
        return dist_x, dist_y

    def _should_skip(self, row_poll):
        """ Checks if pollutant matches the run target """
        p = str(row_poll).strip().upper()
        t = str(self.target_pollutant).strip().upper()
        return (p != 'ALL') and (p != t)

    # ==========================
    # 1. POINT SOURCES
    # ==========================
    def get_point_sources(self):
        f = self.files['point']
        if not f.exists(): return []
        
        print(f"    -> Loading Points: {f.name}")
        df = pd.read_csv(f)
        lines = []
        
        for _, row in df.iterrows():
            if self._should_skip(row['pollutant']): continue

            try:
                geom = wkt.loads(row['wkt_geometry'])
                x, y = self._latlon_to_xy(geom.y, geom.x)
                
                sid = row['source_id']
                elev = row.get('elevation_base', self.base_elev)
                
                # Cards
                lines.append(f"   LOCATION  {sid} POINT {x:.1f} {y:.1f} {elev}")
                lines.append(f"   SRCPARAM  {sid} {row['emission_rate_gs']} {row['stack_height_m']} {row['temp_k']} {row['velocity_ms']} {row['diameter_m']}")
            except Exception as e:
                print(f"[WARN] Bad Point {row.get('source_id')}: {e}")

        return lines

    # ==========================
    # 2. AREA SOURCES (AREAPOLY)
    # ==========================
    def get_area_sources(self):
        f = self.files['area']
        if not f.exists(): return []

        print(f"    -> Loading Areas: {f.name}")
        df = pd.read_csv(f)
        lines = []

        for _, row in df.iterrows():
            if self._should_skip(row['pollutant']): continue

            try:
                poly = wkt.loads(row['wkt_geometry'])
                if not isinstance(poly, Polygon): continue

                sid = row['source_id']
                elev = row.get('elevation_base', self.base_elev)
                
                coords = list(poly.exterior.coords)
                if coords[0] == coords[-1]: coords.pop()
                
                # Count the actual vertices to provide to AERMOD
                num_verts = len(coords)
                
                ref_x, ref_y = self._latlon_to_xy(coords[0][1], coords[0][0])
                
                # 1. LOCATION Card
                lines.append(f"   LOCATION  {sid} AREAPOLY {ref_x:.1f} {ref_y:.1f} {elev}")

                # 2. SRCPARAM Card 
                # FIX: Added {num_verts} after release_height_m
                lines.append(f"   SRCPARAM  {sid} {row['emission_flux_gsm2']} {row['release_height_m']} {num_verts} {row.get('init_sz_m', 0.0)}")

                # 3. AREAVERT Cards
                for lon, lat in coords:
                    vx, vy = self._latlon_to_xy(lat, lon)
                    lines.append(f"   AREAVERT  {sid} {vx:.1f} {vy:.1f}")
                    
            except Exception as e:
                print(f"[WARN] Bad Area {row.get('source_id')}: {e}")
        
        return lines
    # ==========================
    # 3. LINE SOURCES (Splitting Segments)
    # ==========================
    def get_line_sources(self):
        f = self.files['line']
        if not f.exists(): return []

        print(f"    -> Loading Lines: {f.name}")
        df = pd.read_csv(f)
        lines = []

        for _, row in df.iterrows():
            if self._should_skip(row['pollutant']): continue

            try:
                line = wkt.loads(row['wkt_geometry'])
                if not isinstance(line, LineString): continue

                base_id = row['source_id']
                elev = row.get('elevation_base', self.base_elev)
                width = row['width_m']
                
                # Iterate through segments (Point A -> Point B)
                coords = list(line.coords)
                for i in range(len(coords) - 1):
                    # Create a unique ID for each segment (ROAD01_S1, ROAD01_S2)
                    seg_id = f"{base_id}_S{i+1}"
                    # Truncate ID if > 8 chars (AERMOD Legacy limit) or keep clean
                    # Modern AERMOD allows longer IDs, but let's keep it safe
                    
                    p1_lon, p1_lat = coords[i]
                    p2_lon, p2_lat = coords[i+1]
                    
                    x1, y1 = self._latlon_to_xy(p1_lat, p1_lon)
                    x2, y2 = self._latlon_to_xy(p2_lat, p2_lon)

                    # LOCATION ID LINE X1 Y1 X2 Y2 ELEV
                    lines.append(f"   LOCATION  {seg_id} LINE {x1:.1f} {y1:.1f} {x2:.1f} {y2:.1f} {elev}")
                    
                    # SRCPARAM ID EmisRate RelHgt Width
                    lines.append(f"   SRCPARAM  {seg_id} {row['emission_rate_gs']} {row['release_height_m']} {width}")

            except Exception as e:
                print(f"[WARN] Bad Line {row.get('source_id')}: {e}")

        return lines

    def generate_all_sources(self):
        """ Helper to get everything at once """
        all_lines = ["SO STARTING", "   ELEVUNIT METERS"]
        
        all_lines.extend(self.get_point_sources())
        all_lines.extend(self.get_area_sources())
        all_lines.extend(self.get_line_sources())
        
        all_lines.append("   SRCGROUP  ALL")
        all_lines.append("SO FINISHED")
        
        return all_lines

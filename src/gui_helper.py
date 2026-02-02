import tkinter as tk
from tkinter import ttk, messagebox
import yaml
from pathlib import Path
import platform
import subprocess
import os

class ConfigHelper:
    def __init__(self, root):
        self.root = root
        self.root.title("ATAQ AERMOD Configurator")
        self.root.geometry("650x600")
        
        # Paths
        self.root_dir = Path(__file__).parent.parent
        self.config_path = self.root_dir / "config.yaml"
        self.inventory_dir = self.root_dir / "data" / "inventory"
        self.inventory_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure default files exist so they can be opened
        self._ensure_defaults()

        # Load Data
        self.config = self.load_config()

        # Build UI
        self.create_widgets()

    def _ensure_defaults(self):
        """Creates empty CSVs if they don't exist, so the user has something to edit."""
        files = {
            'point_sources.csv': 'source_id,description,wkt_geometry,pollutant,elevation_base,emission_rate_gs,stack_height_m,temp_k,velocity_ms,diameter_m',
            'area_sources.csv': 'source_id,description,wkt_geometry,pollutant,elevation_base,emission_flux_gsm2,release_height_m,init_sz_m',
            'line_sources.csv': 'source_id,description,wkt_geometry,pollutant,elevation_base,emission_rate_gs,release_height_m,width_m'
        }
        for fname, header in files.items():
            fpath = self.inventory_dir / fname
            if not fpath.exists():
                with open(fpath, 'w') as f:
                    f.write(header + "\n")

    def load_config(self):
        if not self.config_path.exists():
            messagebox.showerror("Error", "config.yaml not found!")
            self.root.destroy()
            return {}
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def save_config(self):
        try:
            # Project
            self.config['project']['name'] = self.vars['proj_name'].get()
            self.config['project']['station_name'] = self.vars['station_name'].get()
            
            # Years
            years_str = self.vars['years'].get()
            self.config['project']['years'] = [int(y.strip()) for y in years_str.split(',') if y.strip().isdigit()]

            # Location
            self.config['location']['latitude'] = float(self.vars['lat'].get())
            self.config['location']['longitude'] = float(self.vars['lon'].get())
            self.config['location']['elevation'] = float(self.vars['elev'].get())
            
            # AERMOD Params
            self.config['aermod_params']['pollutant'] = self.vars['pollutant'].get()
            
            # Data Source (Just creating the key for future use, logic is hardcoded to ERA5 for now)
            self.config['project']['data_source'] = self.vars['data_source'].get()

            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, sort_keys=False, default_flow_style=False)
            
            messagebox.showinfo("Success", "Configuration Saved!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")

    def open_path(self, path):
        """Opens a file or directory in the OS default viewer."""
        path = str(path)
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", path], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open path:\n{e}")

    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(expand=True, fill='both', padx=10, pady=10)

        self.vars = {}

        # --- TAB 1: METEOROLOGY ---
        tab_met = ttk.Frame(notebook)
        notebook.add(tab_met, text="1. Meteorology & Location")
        
        # Project
        lf_proj = ttk.LabelFrame(tab_met, text="Project Settings")
        lf_proj.pack(fill='x', padx=10, pady=5)
        self.add_entry(lf_proj, "Project Name:", 'proj_name', self.config['project']['name'])
        self.add_entry(lf_proj, "Station Name:", 'station_name', self.config['project']['station_name'])
        
        years_list = self.config['project'].get('years', [2023])
        if isinstance(years_list, int): years_list = [years_list]
        self.add_entry(lf_proj, "Years (comma sep):", 'years', ", ".join(map(str, years_list)))

        # Data Source (Radio Buttons)
        lf_src = ttk.LabelFrame(tab_met, text="Met Data Source")
        lf_src.pack(fill='x', padx=10, pady=5)
        
        self.vars['data_source'] = tk.StringVar(value=self.config['project'].get('data_source', 'ERA5'))
        
        rb1 = ttk.Radiobutton(lf_src, text="ERA5 (Copernicus CDS)", variable=self.vars['data_source'], value="ERA5")
        rb1.pack(anchor='w', padx=10, pady=2)
        
        rb2 = ttk.Radiobutton(lf_src, text="User Provided (WRF/MM5) [Future]", variable=self.vars['data_source'], value="USER", state="disabled")
        rb2.pack(anchor='w', padx=10, pady=2)

        # Location
        lf_loc = ttk.LabelFrame(tab_met, text="Site Location")
        lf_loc.pack(fill='x', padx=10, pady=5)
        self.add_entry(lf_loc, "Latitude:", 'lat', self.config['location']['latitude'])
        self.add_entry(lf_loc, "Longitude:", 'lon', self.config['location']['longitude'])
        self.add_entry(lf_loc, "Elevation (m):", 'elev', self.config['location']['elevation'])


        # --- TAB 2: INVENTORY ---
        tab_inv = ttk.Frame(notebook)
        notebook.add(tab_inv, text="2. Emissions Inventory")
        
        # Header / Open Folder
        frm_header = ttk.Frame(tab_inv)
        frm_header.pack(fill='x', padx=10, pady=15)
        
        lbl_info = ttk.Label(frm_header, text="Edit the master inventory files directly.\nAERMOD will read whatever is saved in these files.")
        lbl_info.pack(side='left')
        
        btn_folder = ttk.Button(frm_header, text="📂 Open Inventory Folder", command=lambda: self.open_path(self.inventory_dir))
        btn_folder.pack(side='right')

        # File Managers
        lf_files = ttk.LabelFrame(tab_inv, text="Source Files")
        lf_files.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.add_file_row(lf_files, "Point Sources (Stacks)", "point_sources.csv")
        self.add_file_row(lf_files, "Area Sources (Polygons)", "area_sources.csv")
        self.add_file_row(lf_files, "Line Sources (Roads)", "line_sources.csv")


        # --- TAB 3: MODEL PARAMS ---
        tab_mod = ttk.Frame(notebook)
        notebook.add(tab_mod, text="3. Model Options")
        
        lf_opts = ttk.LabelFrame(tab_mod, text="AERMOD Parameters")
        lf_opts.pack(fill='x', padx=10, pady=10)
        self.add_entry(lf_opts, "Pollutant (SO2, PM10):", 'pollutant', self.config['aermod_params']['pollutant'])

        # --- FOOTER ---
        btn_area = ttk.Frame(self.root)
        btn_area.pack(fill='x', padx=20, pady=10)
        ttk.Button(btn_area, text="Save Configuration", command=self.save_config).pack(side='right')
        ttk.Button(btn_area, text="Cancel", command=self.root.destroy).pack(side='right', padx=5)

    def add_entry(self, parent, label_text, var_name, default_val):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=5, pady=2)
        lbl = ttk.Label(frame, text=label_text, width=20, anchor='w')
        lbl.pack(side='left')
        var = tk.StringVar(value=str(default_val))
        self.vars[var_name] = var
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(side='right', expand=True, fill='x')

    def add_file_row(self, parent, label_text, filename):
        """Creates a row: [Label] [Path] [Edit Button]"""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=5, pady=8)
        
        # Label (Title)
        lbl = ttk.Label(frame, text=label_text, width=25, anchor='w', font=('Arial', 10, 'bold'))
        lbl.pack(side='left')
        
        # Path Display (Greyed out entry)
        full_path = self.inventory_dir / filename
        path_var = tk.StringVar(value=str(full_path))
        entry = ttk.Entry(frame, textvariable=path_var, state='readonly', width=40)
        entry.pack(side='left', padx=5)
        
        # Edit Button
        btn = ttk.Button(frame, text="✏️ Edit File", command=lambda: self.open_path(full_path))
        btn.pack(side='left', padx=5)

def launch_gui():
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam') 
    app = ConfigHelper(root)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()

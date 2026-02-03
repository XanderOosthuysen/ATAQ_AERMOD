import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import yaml
from pathlib import Path
import platform
import subprocess
import os

class ToolTip(object):
    """
    Creates a tooltip for a given widget
    """
    def __init__(self, widget, text='widget info'):
        self.wait_time = 500     # milliseconds
        self.wrap_length = 180   # pixels
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.wait_time, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()

class ConfigHelper:
    def __init__(self, root):
        self.root = root
        self.root.title("ATAQ AERMOD Configurator")
        self.root.geometry("750x650")
        
        # Paths
        self.root_dir = Path(__file__).parent.parent
        self.config_path = self.root_dir / "config.yaml"
        self.inventory_dir = self.root_dir / "data" / "inventory"
        self.inventory_dir.mkdir(parents=True, exist_ok=True)
        
        self._ensure_defaults()
        self.config = self.load_config()
        self.create_widgets()

    def _ensure_defaults(self):
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
            return {}
        with open(self.config_path, 'r') as f:
            cfg = yaml.safe_load(f)
            # Ensure inventory dict exists
            if 'inventory' not in cfg: cfg['inventory'] = {}
            return cfg

    def save_config(self):
        try:
            # Project
            self.config['project']['name'] = self.vars['proj_name'].get()
            self.config['project']['station_name'] = self.vars['station_name'].get()
            
            years_str = self.vars['years'].get()
            self.config['project']['years'] = [int(y.strip()) for y in years_str.split(',') if y.strip().isdigit()]

            # Location
            self.config['location']['latitude'] = float(self.vars['lat'].get())
            self.config['location']['longitude'] = float(self.vars['lon'].get())
            self.config['location']['elevation'] = float(self.vars['elev'].get())
            
            # AERMOD Params
            self.config['aermod_params']['pollutant'] = self.vars['pollutant'].get()
            
            # Met Data Source
            source = self.vars['data_source'].get()
            self.config['project']['data_source'] = source
            if source == 'USER':
                self.config['project']['user_sfc'] = self.vars['sfc_path'].get()
                self.config['project']['user_pfl'] = self.vars['pfl_path'].get()

            # Inventory Paths (New!)
            self.config['inventory']['point'] = self.vars['inv_point'].get()
            self.config['inventory']['area'] = self.vars['inv_area'].get()
            self.config['inventory']['line'] = self.vars['inv_line'].get()

            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, sort_keys=False, default_flow_style=False)
            
            messagebox.showinfo("Success", "Configuration Saved!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")

    def open_path(self, path):
        path = str(path)
        if not Path(path).exists():
            messagebox.showwarning("File Missing", f"File not found:\n{path}")
            return

        system = platform.system()
        try:
            if system == "Windows": os.startfile(path)
            elif system == "Darwin": subprocess.run(["open", path], check=True)
            else: subprocess.run(["xdg-open", path], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open path:\n{e}")

    def browse_file(self, var_name, file_type):
        fpath = filedialog.askopenfilename(filetypes=[(f"{file_type} Files", f"*.{file_type.lower()}"), ("All Files", "*.*")])
        if fpath:
            self.vars[var_name].set(fpath)

    def toggle_met_source(self):
        mode = self.vars['data_source'].get()
        state = 'normal' if mode == 'USER' else 'disabled'
        for row_frame in self.frm_user_met.winfo_children():
            for widget in row_frame.winfo_children():
                try: widget.configure(state=state)
                except: pass

    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(expand=True, fill='both', padx=10, pady=10)

        self.vars = {}

        # --- TAB 1: METEOROLOGY ---
        tab_met = ttk.Frame(notebook)
        notebook.add(tab_met, text="1. Meteorology & Location")
        
        # 1. Project Settings
        lf_proj = ttk.LabelFrame(tab_met, text="Project Settings")
        lf_proj.pack(fill='x', padx=10, pady=5)
        self.add_entry(lf_proj, "Project Name:", 'proj_name', self.config['project'].get('name', ''))
        self.add_entry(lf_proj, "Station Name:", 'station_name', self.config['project'].get('station_name', ''))
        
        years_list = self.config['project'].get('years', [2023])
        if isinstance(years_list, int): years_list = [years_list]
        self.add_entry(lf_proj, "Years (comma sep):", 'years', ", ".join(map(str, years_list)))

        # 2. Site Location (With Tooltips)
        lf_loc = ttk.LabelFrame(tab_met, text="Site Location")
        lf_loc.pack(fill='x', padx=10, pady=5)
        
        lat_entry = self.add_entry(lf_loc, "Latitude:", 'lat', self.config['location']['latitude'])
        ToolTip(lat_entry, "Format: Decimal Degrees (e.g. -26.204)\nCRS: WGS84 (EPSG:4326)\nNegative for Southern Hemisphere")
        
        lon_entry = self.add_entry(lf_loc, "Longitude:", 'lon', self.config['location']['longitude'])
        ToolTip(lon_entry, "Format: Decimal Degrees (e.g. 28.047)\nCRS: WGS84 (EPSG:4326)")
        
        self.add_entry(lf_loc, "Elevation (m):", 'elev', self.config['location']['elevation'])

        # 3. Met Data Source
        lf_src = ttk.LabelFrame(tab_met, text="Met Data Source")
        lf_src.pack(fill='x', padx=10, pady=5)
        
        self.vars['data_source'] = tk.StringVar(value=self.config['project'].get('data_source', 'ERA5'))
        
        ttk.Radiobutton(lf_src, text="ERA5 (Copernicus CDS) - Automatic Download", 
                        variable=self.vars['data_source'], value="ERA5", 
                        command=self.toggle_met_source).pack(anchor='w', padx=10, pady=2)
        
        ttk.Radiobutton(lf_src, text="User Processed (.SFC / .PFL) - Manual Path", 
                        variable=self.vars['data_source'], value="USER", 
                        command=self.toggle_met_source).pack(anchor='w', padx=10, pady=2)

        self.frm_user_met = ttk.Frame(lf_src)
        self.frm_user_met.pack(fill='x', padx=30, pady=5)
        
        sfc_val = self.config['project'].get('user_sfc', '')
        pfl_val = self.config['project'].get('user_pfl', '')
        
        self.add_file_picker(self.frm_user_met, "Surface File (.SFC):", 'sfc_path', sfc_val, "SFC")
        self.add_file_picker(self.frm_user_met, "Profile File (.PFL):", 'pfl_path', pfl_val, "PFL")
        
        self.toggle_met_source()


        # --- TAB 2: INVENTORY ---
        tab_inv = ttk.Frame(notebook)
        notebook.add(tab_inv, text="2. Emissions Inventory")
        
        frm_header = ttk.Frame(tab_inv)
        frm_header.pack(fill='x', padx=10, pady=15)
        
        lbl_info = ttk.Label(frm_header, text="Select inventory files. Default files are in data/inventory/.", justify='left')
        lbl_info.pack(side='left')
        
        btn_folder = ttk.Button(frm_header, text="📂 Open Inventory Folder", command=lambda: self.open_path(self.inventory_dir))
        btn_folder.pack(side='right')

        lf_files = ttk.LabelFrame(tab_inv, text="Source Files")
        lf_files.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Load paths from config OR default to standard inventory
        cfg_inv = self.config.get('inventory', {})
        
        p_path = cfg_inv.get('point', str(self.inventory_dir / "point_sources.csv"))
        a_path = cfg_inv.get('area', str(self.inventory_dir / "area_sources.csv"))
        l_path = cfg_inv.get('line', str(self.inventory_dir / "line_sources.csv"))

        self.add_inv_row(lf_files, "Point Sources (Stacks)", 'inv_point', p_path)
        self.add_inv_row(lf_files, "Area Sources (Polygons)", 'inv_area', a_path)
        self.add_inv_row(lf_files, "Line Sources (Roads)", 'inv_line', l_path)

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
        ttk.Button(btn_area, text="Close", command=self.root.destroy).pack(side='right', padx=5)

    def add_entry(self, parent, label_text, var_name, default_val):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=5, pady=2)
        lbl = ttk.Label(frame, text=label_text, width=20, anchor='w')
        lbl.pack(side='left')
        var = tk.StringVar(value=str(default_val))
        self.vars[var_name] = var
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(side='right', expand=True, fill='x')
        return entry # Return widget so we can attach tooltips

    def add_file_picker(self, parent, label_text, var_name, default_val, ftype):
        """Standard file picker for Met Data"""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=2)
        lbl = ttk.Label(frame, text=label_text, width=18, anchor='w')
        lbl.pack(side='left')
        var = tk.StringVar(value=str(default_val))
        self.vars[var_name] = var
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(side='left', expand=True, fill='x', padx=5)
        btn = ttk.Button(frame, text="Browse...", width=8, command=lambda: self.browse_file(var_name, ftype))
        btn.pack(side='right')

    def add_inv_row(self, parent, label_text, var_name, default_path):
        """Special row for Inventory: Label | Path Entry | Browse | Edit"""
        frame = ttk.Frame(parent)
        frame.pack(fill='x', padx=5, pady=8)
        
        # Label
        lbl = ttk.Label(frame, text=label_text, width=25, anchor='w', font=('Arial', 10, 'bold'))
        lbl.pack(side='left')
        
        # Variable & Entry
        var = tk.StringVar(value=default_path)
        self.vars[var_name] = var
        entry = ttk.Entry(frame, textvariable=var, width=35)
        entry.pack(side='left', padx=5)
        
        # Browse Button (Change the path)
        btn_browse = ttk.Button(frame, text="Browse...", width=8, 
                                command=lambda: self.browse_file(var_name, "CSV"))
        btn_browse.pack(side='left', padx=2)
        
        # Edit Button (Open the file at the path)
        btn_edit = ttk.Button(frame, text="✏️ Edit File", 
                              command=lambda: self.open_path(var.get()))
        btn_edit.pack(side='left', padx=2)

def launch_gui():
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam') 
    app = ConfigHelper(root)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()

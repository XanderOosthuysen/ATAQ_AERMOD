import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import yaml
from pathlib import Path
import platform
import subprocess
import os
import threading
import queue

class ToolTip(object):
    """Creates a tooltip for a given widget"""
    def __init__(self, widget, text='widget info'):
        self.wait_time = 500
        self.wrap_length = 180
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
        if id: self.widget.after_cancel(id)
    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)
    def hidetip(self):
        tw = self.tw
        self.tw= None
        if tw: tw.destroy()

class GUIHelper:
    def __init__(self, root):
        self.root = root
        self.root.title("ATAQ AERMOD Pipeline Controller")
        self.root.geometry("900x900") 
        
        # --- PATH ANCHORING ---
        self.project_root = Path(__file__).parent.parent.resolve()
        self.config_dir = self.project_root / "project_configs"
        self.config_dir.mkdir(exist_ok=True)
        self.data_dir = self.project_root / "data"
        self.inventory_dir = self.data_dir / "inventory"
        
        # Default Config Path
        self.current_config_path = self.config_dir / "default.yaml"
        
        self.config = {}
        self.vars = {}
        self.pollutant_vars = {}
        self.pollutant_configs = {}
        self.pollutant_options = ["SO2", "NO2", "PM10", "PM2.5", "CO", "Pb", "OTHER"]
        self.aermet_completed = False
        self.is_running = False # Global lock for actions

        # Queue for thread-safe logging
        self.log_queue = queue.Queue()
        
        # Load Initial Config
        self.load_config(self.current_config_path)
        
        self.create_widgets()
        
        # Start the log polling loop
        self.check_log_queue()

    def load_config(self, path):
        """Loads a specific YAML file into self.config"""
        self.log(f"Loading config: {path.name}...")
        if path.exists():
            with open(path, 'r') as f:
                try:
                    self.config = yaml.safe_load(f)
                    self.current_config_path = path
                    if hasattr(self, 'notebook'):
                        self.refresh_ui_from_config()
                except Exception as e:
                    self.log(f"[ERROR] Failed to load config: {e}")
                    self.config = {}
        else:
            self.log("[WARNING] Config not found, using internal defaults.")
            self.config = {}
        
        # Ensure Defaults
        defaults = {
            'project': {'name': 'NewProject', 'years': [2024], 'data_source': 'ERA5'},
            'location': {'latitude': 0.0, 'longitude': 0.0, 'elevation': 0.0},
            'paths': {},
            'inventory': {},
            'aermod_params': {'pollutants': {}}
        }
        for k, v in defaults.items():
            if k not in self.config:
                self.config[k] = v

    def save_config(self):
        # Update config dict from UI variables
        self.config['project']['name'] = self.vars['project_name'].get()
        
        try:
            y_str = self.vars['years'].get().strip('[] ')
            if y_str: self.config['project']['years'] = [int(y.strip()) for y in y_str.split(',')]
            else: self.config['project']['years'] = []
        except: pass

        self.config['location']['latitude'] = float(self.vars['lat'].get())
        self.config['location']['longitude'] = float(self.vars['lon'].get())
        self.config['location']['elevation'] = float(self.vars['elev'].get())
        
        self.config['paths']['aermet_exe'] = self.vars['aermet_exe'].get()
        self.config['paths']['aermod_exe'] = self.vars['aermod_exe'].get()
        
        src = self.vars['data_source'].get()
        self.config['project']['data_source'] = src
        if src == 'USER':
            self.config['project']['user_sfc'] = self.vars['sfc_path'].get()
            self.config['project']['user_pfl'] = self.vars['pfl_path'].get()
        
        self.config['inventory']['point'] = self.vars['inv_point'].get()
        self.config['inventory']['area'] = self.vars['inv_area'].get()
        self.config['inventory']['line'] = self.vars['inv_line'].get()
        
        p_data = {}
        for pol in self.pollutant_options:
            if self.pollutant_vars[pol].get():
                p_data[pol] = {'enabled': True, 'avg_times': self.pollutant_configs.get(pol, ['1', '24'])}
        self.config['aermod_params']['pollutants'] = p_data

        # Save Logic
        proj_name = self.config['project']['name'].replace(" ", "_")
        if not proj_name: proj_name = "default"
        save_path = self.config_dir / f"{proj_name}.yaml"
        
        try:
            with open(save_path, 'w') as f:
                yaml.dump(self.config, f, sort_keys=False)
            
            self.current_config_path = save_path
            self.log(f"[SUCCESS] Configuration saved to: {save_path.name}")
            self.root.title(f"ATAQ Controller - {save_path.name}")
        except Exception as e:
            self.log(f"[ERROR] Save failed: {e}")

    def refresh_ui_from_config(self):
        # Project
        self.vars['project_name'].set(self.config['project'].get('name', ''))
        self.vars['years'].set(str(self.config['project'].get('years', [])).strip('[]'))
        self.vars['data_source'].set(self.config['project'].get('data_source', 'ERA5'))
        
        # Location
        loc = self.config.get('location', {})
        self.vars['lat'].set(loc.get('latitude', 0.0))
        self.vars['lon'].set(loc.get('longitude', 0.0))
        self.vars['elev'].set(loc.get('elevation', 0.0))
        
        # Paths
        paths = self.config.get('paths', {})
        self.vars['aermet_exe'].set(paths.get('aermet_exe', ''))
        self.vars['aermod_exe'].set(paths.get('aermod_exe', ''))
        
        # Inventory
        inv = self.config.get('inventory', {})
        self.vars['inv_point'].set(inv.get('point', ''))
        self.vars['inv_area'].set(inv.get('area', ''))
        self.vars['inv_line'].set(inv.get('line', ''))
        
        # Pollutants
        pols = self.config.get('aermod_params', {}).get('pollutants', {})
        for pol in self.pollutant_options:
            is_checked = pol in pols
            self.pollutant_vars[pol].set(is_checked)
            if is_checked:
                self.pollutant_configs[pol] = pols[pol].get('avg_times', ['1', '24'])
            else:
                self.pollutant_configs[pol] = ['1', '24']

        self.update_button_states()

    def load_project_dialog(self):
        f = filedialog.askopenfilename(
            initialdir=self.config_dir,
            title="Load Project Configuration",
            filetypes=[("YAML Config", "*.yaml"), ("All Files", "*.*")]
        )
        if f: self.load_config(Path(f))

    # --- LOGGING SYSTEM ---
    def log(self, message):
        """Adds a message to the queue to be printed in the GUI text box."""
        self.log_queue.put(message)

    def check_log_queue(self):
        """Polls the queue and updates the Text widget."""
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.console.config(state='normal')
            self.console.insert(tk.END, msg + "\n")
            self.console.see(tk.END) # Auto-scroll
            self.console.config(state='disabled')
        self.root.after(100, self.check_log_queue)

    # --- PIPELINE EXECUTION ---
    def run_pipeline_action(self, action_name, success_msg=None, on_complete=None):
        if self.is_running:
            self.log("[WARNING] A process is already running. Please wait.")
            return

        self.is_running = True
        self.update_button_states() # Disable all buttons
        
        self.save_config()
        config_name = self.current_config_path.name 
        
        self.log(f"\n--- STARTING ACTION: {action_name.upper()} ---")

        def _run():
            try:
                cmd = ["python3", "run_pipeline.py", "--action", action_name, "--config", config_name]
                
                # Start subprocess and pipe output
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                    text=True, cwd=self.project_root, bufsize=1, universal_newlines=True
                )
                
                # Read output line by line
                for line in process.stdout:
                    self.log(line.strip())
                
                process.wait()
                
                if process.returncode == 0:
                    if success_msg: self.log(f"[SUCCESS] {success_msg}")
                    if on_complete: on_complete(True)
                else:
                    self.log(f"[ERROR] Action '{action_name}' failed with exit code {process.returncode}")
                    if on_complete: on_complete(False)

            except Exception as e:
                self.log(f"[EXCEPTION] {str(e)}")
                if on_complete: on_complete(False)
            finally:
                self.is_running = False
                self.log(f"--- FINISHED ACTION: {action_name.upper()} ---\n")
                # Need to schedule UI update on main thread
                self.root.after(0, self.update_button_states)
        
        threading.Thread(target=_run, daemon=True).start()
        
    # --- WIDGET CREATION ---
    def create_widgets(self):
        # 1. Main Content Area (Top 2/3) - Using PanedWindow
        # PanedWindow does NOT support weight in add()
        main_pane = tk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_pane.pack(fill='both', expand=True)

        top_frame = ttk.Frame(main_pane)
        # Use stretch='always' so it resizes. 
        main_pane.add(top_frame, stretch="always")

        # --- Header ---
        header = ttk.Frame(top_frame, padding=5)
        header.pack(fill='x')
        ttk.Label(header, text="Active Project:", font=('Arial', 10, 'bold')).pack(side='left')
        ttk.Button(header, text="📂 Load Project", command=self.load_project_dialog).pack(side='right')

        # --- Notebook ---
        self.notebook = ttk.Notebook(top_frame)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        self.tab_project = ttk.Frame(self.notebook); self.notebook.add(self.tab_project, text='1. Project')
        self.create_project_tab(self.tab_project)
        
        self.tab_met = ttk.Frame(self.notebook); self.notebook.add(self.tab_met, text='2. Meteorology')
        self.create_met_tab(self.tab_met)
        
        self.tab_inv = ttk.Frame(self.notebook); self.notebook.add(self.tab_inv, text='3. Inventory')
        self.create_inventory_tab(self.tab_inv)
        
        self.tab_pol = ttk.Frame(self.notebook); self.notebook.add(self.tab_pol, text='4. Pollutants')
        self.create_analysis_tab(self.tab_pol)
        
        # --- Action Buttons ---
        btn_frame = ttk.Frame(top_frame, padding=10)
        btn_frame.pack(fill='x')
        
        self.btn_setup = ttk.Button(btn_frame, text="🛠️ Setup Env", command=self.confirm_and_setup)
        self.btn_setup.pack(side='left', padx=5)
        
        self.btn_aermod = ttk.Button(btn_frame, text="🏭 Run AERMOD Model", command=self.run_aermod_model)
        self.btn_aermod.pack(side='left', padx=20)
        
        self.btn_save = ttk.Button(btn_frame, text="💾 Save Config", command=self.save_config)
        self.btn_save.pack(side='right', padx=5)

        # 2. Console Area (Bottom 1/3)
        bottom_frame = ttk.Frame(main_pane)
        main_pane.add(bottom_frame, stretch="always")
        
        ttk.Label(bottom_frame, text="Process Output Log:", font=('Arial', 9, 'bold')).pack(anchor='w', padx=5)
        
        self.console = scrolledtext.ScrolledText(bottom_frame, height=10, state='disabled', bg='#1e1e1e', fg='#00ff00', font=('Consolas', 9))
        self.console.pack(fill='both', expand=True, padx=5, pady=5)

        # Force initial Sash position to 2/3 down (approx 600px)
        self.root.update_idletasks() # Ensure widget is drawn first
        try:
            main_pane.sash_place(0, 0, 600)
        except:
            pass # Fails if window not ready, minor issue

        # Populate UI
        self.refresh_ui_from_config()

    # --- Actions ---
    def confirm_and_setup(self):
        if messagebox.askyesno("Confirm", "Setup Environment?"): self.run_pipeline_action("setup_aermod")
    def run_setup_inventory(self): self.run_pipeline_action("setup_inventory")
    def run_download(self): self.run_pipeline_action("download")
    def run_met_process(self): self.run_pipeline_action("met_process")
    def run_aermet(self): self.run_pipeline_action("aermet", on_complete=lambda s: setattr(self, 'aermet_completed', s))
    def run_aermod_model(self): self.run_pipeline_action("run_model")

    # --- State Management (LOCKING LOGIC) ---
    def toggle_met_source(self):
        self.update_button_states()

    def update_button_states(self):
        """Handles locking buttons during runs AND toggling based on config"""
        
        # If running, DISABLE ALL ACTION BUTTONS
        if self.is_running:
            state = 'disabled'
            # Disable main buttons
            if hasattr(self, 'btn_setup'): self.btn_setup.config(state=state)
            if hasattr(self, 'btn_aermod'): self.btn_aermod.config(state=state)
            if hasattr(self, 'btn_save'): self.btn_save.config(state=state)
            
            # Disable Tab 2 buttons
            if hasattr(self, 'btn_dl'): self.btn_dl.config(state=state)
            if hasattr(self, 'btn_proc'): self.btn_proc.config(state=state)
            if hasattr(self, 'btn_aermet'): self.btn_aermet.config(state=state)
            
            # Disable Tab 3 buttons
            if hasattr(self, 'btn_init_inv'): self.btn_init_inv.config(state=state)
            return

        # --- If NOT running, apply normal logic ---
        # Re-enable Setup/Save
        if hasattr(self, 'btn_setup'): self.btn_setup.config(state='normal')
        if hasattr(self, 'btn_save'): self.btn_save.config(state='normal')
        if hasattr(self, 'btn_init_inv'): self.btn_init_inv.config(state='normal')

        try:
            mode = self.vars['data_source'].get()
            era_state = 'normal' if mode == 'ERA5' else 'disabled'
            
            if hasattr(self, 'btn_dl'): self.btn_dl.config(state=era_state)
            if hasattr(self, 'btn_proc'): self.btn_proc.config(state=era_state)
            if hasattr(self, 'btn_aermet'): self.btn_aermet.config(state=era_state)
            
            # AERMOD Button
            mod_state = 'disabled'
            if mode == 'USER': mod_state = 'normal'
            elif mode == 'ERA5' and self.aermet_completed: mod_state = 'normal'
            
            if hasattr(self, 'btn_aermod'): self.btn_aermod.config(state=mod_state)
            
            # Toggle User Met Inputs
            u_state = 'normal' if mode == 'USER' else 'disabled'
            for child in self.frm_user_met.winfo_children():
                try: child.configure(state=u_state)
                except: pass

        except: pass

    # --- POPUPS ---
    def open_pollutant_settings(self, pollutant):
        win = tk.Toplevel(self.root)
        win.title(f"{pollutant} Settings")
        win.geometry("300x250")
        ttk.Label(win, text=f"Averaging Times for {pollutant}", font=('Arial', 10, 'bold')).pack(pady=10)
        current = self.pollutant_configs.get(pollutant, ['1', '24'])
        opts = ["1", "3", "8", "24", "ANNUAL"]
        vars = {}
        for o in opts:
            v = tk.BooleanVar(value=(o in current))
            vars[o] = v
            ttk.Checkbutton(win, text=f"{o}-Hour" if o != "ANNUAL" else "Annual", variable=v).pack(anchor='w', padx=20)
        def save():
            sel = [k for k,v in vars.items() if v.get()]
            if not sel: return messagebox.showwarning("Warning", "Select at least one.")
            self.pollutant_configs[pollutant] = sel
            self.pollutant_vars[pollutant].set(True)
            win.destroy()
        ttk.Button(win, text="Save", command=save).pack(pady=15)

    # --- TABS ---
    def create_project_tab(self, parent):
        f = ttk.LabelFrame(parent, text="Project", padding=10)
        f.pack(fill='x', pady=5, padx=10)
        self.add_entry(f, "Project Name:", "project_name", self.config['project'].get('name', 'MyProject'))
        self.add_entry(f, "Years:", "years", str(self.config['project'].get('years', [2024])).strip('[]'))
        
        f = ttk.LabelFrame(parent, text="Location", padding=10)
        f.pack(fill='x', pady=5, padx=10)
        self.add_entry(f, "Lat:", "lat", self.config['location'].get('latitude', 0.0))
        self.add_entry(f, "Lon:", "lon", self.config['location'].get('longitude', 0.0))
        self.add_entry(f, "Elev:", "elev", self.config['location'].get('elevation', 0.0))
        
        f = ttk.LabelFrame(parent, text="Paths", padding=10)
        f.pack(fill='x', pady=5, padx=10)
        daer = self.config['paths'].get('aermet_exe', str(self.project_root / 'bin' / 'aermet'))
        dmod = self.config['paths'].get('aermod_exe', str(self.project_root / 'bin' / 'aermod'))
        self.add_file_picker(f, "AERMET:", "aermet_exe", daer, "EXE")
        self.add_file_picker(f, "AERMOD:", "aermod_exe", dmod, "EXE")

    def create_met_tab(self, parent):
        f = ttk.LabelFrame(parent, text="Source", padding=10)
        f.pack(fill='both', expand=True, padx=10, pady=10)
        self.vars['data_source'] = tk.StringVar(value=self.config['project'].get('data_source', 'ERA5'))
        
        ttk.Radiobutton(f, text="ERA5 Pipeline", variable=self.vars['data_source'], value="ERA5", command=self.toggle_met_source).pack(anchor='w', padx=10)
        
        # ERA5 Buttons
        b_frame = ttk.Frame(f)
        b_frame.pack(fill='x', padx=30, pady=5)
        self.btn_dl = ttk.Button(b_frame, text="1. Download", command=self.run_download)
        self.btn_dl.pack(side='left', padx=2)
        self.btn_proc = ttk.Button(b_frame, text="2. Process", command=self.run_met_process)
        self.btn_proc.pack(side='left', padx=2)
        self.btn_aermet = ttk.Button(b_frame, text="3. Run AERMET", command=self.run_aermet)
        self.btn_aermet.pack(side='left', padx=2)
        
        ttk.Separator(f).pack(fill='x', pady=10)
        
        ttk.Radiobutton(f, text="User Files", variable=self.vars['data_source'], value="USER", command=self.toggle_met_source).pack(anchor='w', padx=10)
        self.frm_user_met = ttk.Frame(f)
        self.frm_user_met.pack(fill='x', padx=30, pady=5)
        self.add_file_picker(self.frm_user_met, "SFC File:", 'sfc_path', self.config['project'].get('user_sfc', ''), "SFC")
        self.add_file_picker(self.frm_user_met, "PFL File:", 'pfl_path', self.config['project'].get('user_pfl', ''), "PFL")

    def create_inventory_tab(self, parent):
        h = ttk.Frame(parent); h.pack(fill='x', padx=10, pady=10)
        self.btn_init_inv = ttk.Button(h, text="Init Templates", command=self.run_setup_inventory)
        self.btn_init_inv.pack(side='left')
        
        pname = self.config['project'].get('name', 'MyProject')
        def_path = self.data_dir / "inventory" / pname
        ttk.Button(h, text="Open Folder", command=lambda: self.open_path(def_path)).pack(side='right')
        
        f = ttk.LabelFrame(parent, text="Files", padding=10)
        f.pack(fill='both', padx=10)
        cinv = self.config.get('inventory', {})
        self.add_inv_row(f, "Point:", 'inv_point', cinv.get('point', str(def_path/"point_sources.csv")))
        self.add_inv_row(f, "Area:", 'inv_area', cinv.get('area', str(def_path/"area_sources.csv")))
        self.add_inv_row(f, "Line:", 'inv_line', cinv.get('line', str(def_path/"line_sources.csv")))

    def create_analysis_tab(self, parent):
        f = ttk.LabelFrame(parent, text="Pollutants", padding=10)
        f.pack(fill='both', expand=True, padx=10, pady=10)
        saved = self.config.get('aermod_params', {}).get('pollutants', {})
        gf = ttk.Frame(f); gf.pack(fill='both', expand=True)
        r=0; c=0
        for pol in self.pollutant_options:
            pf = ttk.Frame(gf)
            pf.grid(row=r, column=c, sticky='w', padx=20, pady=10)
            chk = pol in saved
            self.pollutant_vars[pol] = tk.BooleanVar(value=chk)
            if chk: self.pollutant_configs[pol] = saved[pol].get('avg_times', ['1', '24'])
            else: self.pollutant_configs[pol] = ['1', '24']
            
            ttk.Button(pf, text="⚙️", width=3, command=lambda p=pol: self.open_pollutant_settings(p)).pack(side='left', padx=(0,5))
            ttk.Checkbutton(pf, text=pol, variable=self.pollutant_vars[pol]).pack(side='left')
            c+=1
            if c>1: c=0; r+=1

    # --- HELPERS ---
    def add_entry(self, p, l, v, d):
        f=ttk.Frame(p); f.pack(fill='x', pady=2)
        ttk.Label(f, text=l, width=15).pack(side='left')
        val=tk.StringVar(value=str(d)); self.vars[v]=val
        ttk.Entry(f, textvariable=val).pack(side='right', expand=True, fill='x')
    
    def add_file_picker(self, p, l, v, d, t):
        f=ttk.Frame(p); f.pack(fill='x', pady=2)
        ttk.Label(f, text=l, width=15).pack(side='left')
        val=tk.StringVar(value=str(d)); self.vars[v]=val
        ttk.Entry(f, textvariable=val).pack(side='left', expand=True, fill='x')
        ttk.Button(f, text="...", width=4, command=lambda: self.browse_file(v,t)).pack(side='right')

    def add_inv_row(self, p, l, v, d):
        f=ttk.Frame(p); f.pack(fill='x', pady=2)
        ttk.Label(f, text=l, width=10).pack(side='left')
        val=tk.StringVar(value=str(d)); self.vars[v]=val
        ttk.Entry(f, textvariable=val).pack(side='left', expand=True, fill='x')
        ttk.Button(f, text="...", width=4, command=lambda: self.browse_file(v,"CSV")).pack(side='left')
        ttk.Button(f, text="Edit", width=5, command=lambda: self.open_path(val.get())).pack(side='left')

    def browse_file(self, v, t):
        f = filedialog.askopenfilename(initialdir=self.project_root)
        if f: self.vars[v].set(f)
    
    def open_path(self, path):
        if not path: return
        p = Path(path)
        if not p.exists() and p.parent.exists(): p = p.parent
        if platform.system() == "Windows": os.startfile(p)
        else: subprocess.call(["xdg-open", str(p)])

def launch_gui():
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam')
    app = GUIHelper(root)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()

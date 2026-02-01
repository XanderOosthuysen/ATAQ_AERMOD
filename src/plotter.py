import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy.interpolate import griddata

class AermodPlotter:
    def __init__(self, config):
        self.output_dir = Path(config['paths']['output_dir']).resolve()
        self.year = config['project']['year']

    def plot_concentration(self, period="1HR"):
        filename = f"{self.year}_{period}_CONC.PLT"
        file_path = self.output_dir / filename
        
        if not file_path.exists():
            print(f"[ERROR] Could not find {filename} in output directory.")
            return

        print(f"    -> Visualizing {filename}...")
        
        try:
            # FIX 1: Use sep='\s+' instead of delim_whitespace=True (Pandas 2.0+ compat)
            # We skip lines starting with '*' using comment='*'
            df = pd.read_csv(file_path, sep=r'\s+', comment='*', header=None)
            
            # AERMOD PLT columns are usually: X, Y, CONC, Z_ELEV, Z_HILL, Z_FLAG, AVE, GRP, DATE
            # We only care about the first 3 columns for a basic plot
            df = df.iloc[:, :3]
            df.columns = ['x', 'y', 'conc']
            
        except Exception as e:
            print(f"[ERROR] Failed to parse PLT file: {e}")
            return

        # 2. Prepare Grid for Contour Plot
        x = df['x'].values
        y = df['y'].values
        z = df['conc'].values

        # Define a regular grid
        # We add a buffer to the min/max to ensure the plot looks centered
        xi = np.linspace(min(x), max(x), 200)
        yi = np.linspace(min(y), max(y), 200)
        Xi, Yi = np.meshgrid(xi, yi)

        # Interpolate data onto the grid
        Zi = griddata((x, y), z, (Xi, Yi), method='linear')

        # 3. Plot
        plt.figure(figsize=(10, 8))
        
        # Contour Fill
        levels = np.linspace(z.min(), z.max(), 20)
        cp = plt.contourf(Xi, Yi, Zi, levels=levels, cmap='jet', alpha=0.8)
        
        # Add colorbar
        cbar = plt.colorbar(cp)
        # FIX 2: Use raw string r'' for LaTeX symbols to avoid SyntaxWarning
        cbar.set_label(r'Concentration ($\mu g/m^3$)')

        # Add Source Point (0,0)
        plt.scatter([0], [0], color='black', marker='*', s=150, label='Source', zorder=10)

        plt.title(f"AERMOD {period} Average Concentration - {self.year}")
        plt.xlabel("Distance East (m)")
        plt.ylabel("Distance North (m)")
        plt.legend()
        plt.grid(True, alpha=0.3)

        # Save
        out_name = f"plot_{self.year}_{period}.png"
        save_path = self.output_dir / out_name
        plt.savefig(save_path, dpi=150)
        plt.close()
        
        print(f"    -> Plot saved to: {save_path}")

    def run(self):
        print(f"\n[PHASE 5] Visualization...")
        # Plot both 1-Hour and 24-Hour averages
        self.plot_concentration("1HR")
        self.plot_concentration("24HR")

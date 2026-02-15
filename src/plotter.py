import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy.interpolate import griddata

class AermodPlotter:
    def __init__(self, config=None):
        self.config = config

    def plot_file(self, file_path):
        """Generates a contour plot directly from a specified .PLT file."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return False, f"Could not find {file_path.name}."

        try:
            # Pandas 2.0+ compatibility using regex separator
            df = pd.read_csv(file_path, sep=r'\s+', comment='*', header=None)
            
            # AERMOD PLT columns: X, Y, CONC, Z_ELEV, Z_HILL, Z_FLAG, AVE, GRP, DATE
            df = df.iloc[:, :3]
            df.columns = ['x', 'y', 'conc']
            
        except Exception as e:
            return False, f"Failed to parse PLT file: {e}"

        # Prepare Grid for Contour Plot
        x = df['x'].values
        y = df['y'].values
        z = df['conc'].values

        # Define a regular grid and interpolate data onto it
        xi = np.linspace(min(x), max(x), 200)
        yi = np.linspace(min(y), max(y), 200)
        Xi, Yi = np.meshgrid(xi, yi)
        Zi = griddata((x, y), z, (Xi, Yi), method='linear')

        # ---------------------------------------------------------
        # SET CONTOUR LEVELS BASED ON POLLUTANT
        # ---------------------------------------------------------
        # Check if the filename contains the Pb indicator
        if "_Pb_" in file_path.name:
            # 20 intervals of 2 (0, 2, 4 ... 40)
            levels = np.arange(0, 42, 2)
        else:
            # 20 intervals of 10 (0, 10, 20 ... 200)
            levels = np.arange(0, 210, 10)

        # Plot
        plt.figure(figsize=(10, 8))
        
        # 'extend="max"' ensures values above our max level get the darkest color 
        # instead of being left blank
        cp = plt.contourf(Xi, Yi, Zi, levels=levels, cmap='jet', alpha=0.8, extend='max')
        
        cbar = plt.colorbar(cp)
        cbar.set_label(r'Concentration ($\mu g/m^3$)')

        # Add Source Point (0,0)
        plt.scatter([0], [0], color='black', marker='*', s=150, label='Source Center', zorder=10)

        plt.title(f"AERMOD Concentration Plume - {file_path.stem}")
        plt.xlabel("Distance East (m)")
        plt.ylabel("Distance North (m)")
        plt.legend()
        plt.grid(True, alpha=0.3)

        # Show the plot in a new window
        plt.show()
        
        return True, f"Plot generated successfully for {file_path.name}."

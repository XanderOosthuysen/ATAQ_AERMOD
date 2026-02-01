import xarray as xr
import matplotlib.pyplot as plt

# Load one of your new INTERIM files
ds = xr.open_dataset('data/interim/merged_era5_sfc_2023_01.nc')

# 1. View the raw structure
print(ds) 

# 2. Quick Plot of Temperature (Kelvin) for the whole month
ds['t2m'].isel(latitude=0, longitude=0).plot()

# 3. Check Precipitation accumulation
# (If this line goes up and down like a saw-tooth, it's cumulative)
# (If it looks like random spikes, it's instantaneous)
ds['tp'].isel(latitude=0, longitude=0).plot()

# duwcm/__init__.py

# Import main components
from .main import run_urban_water_balance
from .water_model import UrbanWaterModel
from .water_balance import run_simulation
from . import forcing
from . import read_data

# Import subpackages
from . import functions
from . import components

# Define version
__version__ = "0.1.0"

# Define all importable names
__all__ = [
    "run_urban_water_balance",
    "UrbanWaterModel",
    "run_simulation",
    "forcing",
    "read_data",
    "functions",
    "components"
]

# Package metadata
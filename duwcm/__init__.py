# duwcm/__init__.py

# Import main components
from .main import run
from .water_model import UrbanWaterModel
from .water_balance import run_water_balance
from .postprocess import plot_global, check_water_balance

# Import subpackages
from . import functions
from . import components

# Define version
__version__ = "0.1.0"

# Define all importable names
__all__ = [
    "run",
    "run_water_balance",
    "UrbanWaterModel",
    "check_water_balance",
    "plot_global",
]

# Package metadata
__author__ = "Ricardo"
__email__ = "ricardo.reyes@eawag.ch"
__description__ = "Distributed urban water cycle model"
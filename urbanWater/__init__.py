# duwcm/__init__.py

# Import main components
from .water_model import UrbanWaterModel
from .water_balance import run_water_balance
from .plots import plot_all

# Import subpackages
from . import functions
from . import components

# Define version
__version__ = "0.1.0"

# Define all importable names
__all__ = [
    "run_water_balance",
    "UrbanWaterModel"
]

# Package metadata
__author__ = "Ricardo"
__email__ = "ricardo.reyes@eawag.ch"
__description__ = "Distributed urban water cycle model"
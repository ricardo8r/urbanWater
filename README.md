# Distributed Urban Water Cycle Model (DUWCM)

## Overview

Distributed Urban Water Cycle Model (DUWCM) is a urban water balance model designed to simulate and analyze water dynamics in urban environments. It includes various components of the urban water cycle: roofs, rain tanks, pavements, pervious surfaces, vadose zone, groundwater, stormwater, and wastewater systems.

## Features

- Modular structure of the water balance components
- Simulation of water flows and interactions between urban surfaces and water systems
- Support for water reuse strategies
- Configuration options for different urban layouts and water management scenarios
- oGlobal and local outputs for water balance analysis and visualization

## Installation

To install DUWM, clone this repository and install the required dependencies:

```bash
git clone https://github.com//duwcm.git
cd duwcm
pip install -e .
```

## Dependencies

DUWCM requires the following Python packages:

- pandas
- numpy
- simpledbf
- matplotlib
- dynaconf

You can install these dependencies using the `requirements.txt` file:

```bash
pip install -r requirements.txt
```

Or you can create an enviroment in conda using the `enviroment.yml` file:
```bash
conda env create -f enviroment.yml
```

## Usage

To run a simulation using DUWM:

1. Prepare your input data files as specified in the `config.toml` file.
2. Adjust the configuration in `config.toml` to match your simulation requirements.
3. Run the main simulation script:

```bash
duwm --config path/to/your/config.toml --env default
```

## Configuration

The `config.toml` file contains all the necessary settings for the simulation, including:

- Grid settings (cell size, number of neighbors)
- File paths for input data
- Simulation parameters (start date, end date, time step)
- Output settings

Modify this file to suit your specific simulation needs.

## Input Data

DUWCM requires several input data files:

- Urban layout data (from UrbanBEATS or similar tools)
- Calibration parameters
- Alternative water device data
- Initial groundwater levels
- Soil and evapotranspiration parameters
- Climate data
- Water demand data

## Output

The model generates several output files:

- Detailed results for each grid cell
- Global results for the entire simulated area

Output files are saved in the directory specified in the configuration file.

## Acknowledgments

This model is based in https://github.com/schsu2021/DUWBM 

from typing import Dict
from pathlib import Path
import pandas as pd

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

import logging

logger = logging.getLogger(__name__)


def generate_scenario_comparison(all_results: Dict[str, Dict], output_dir: Path) -> None:
    """
    Generate one comparison figure per aggregated field across all scenarios.

    Each figure overlays the time series for every scenario on the same axes,
    allowing direct visual comparison.

    Args:
        all_results: Dict mapping scenario name -> results dict.
                     Each results dict must contain 'aggregated' and 'forcing' keys.
        output_dir:  Directory to save the output PNG files.
    """
    custom_params = {"axes.spines.bottom": False, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.spines.left": False}
    sns.set_theme(context='notebook', style='ticks', palette='colorblind',
                  font='serif', font_scale=0.8, rc=custom_params)

    color_palette = [
        "#4e79a7", "#f28e2b", "#e15759",
        "#9c755f", "#59a14f", "#edc948",
        "#b07aa1", "#ff9da7", "#76b7b2",
        "#bab0ac"
    ]
    sns.set_palette(color_palette)

    lw = 0.7
    markers = ['o', 's', '^', 'D', 'v', 'P', 'X', 'p', 'h', '*']
    marker_every = 30  # show a marker every N data points
    fig_width_cm = 18
    fig_height_cm = 12
    fig_width_inch = fig_width_cm / 2.54
    fig_height_inch = fig_height_cm / 2.54

    output_dir.mkdir(parents=True, exist_ok=True)

    # Define the fields to plot, with display names and units
    # Fields in m³
    volume_fields = {
        'stormwater':     'Stormwater',
        'sewerage':       'Sewerage',
        'baseflow':       'Baseflow',
        'total_seepage':  'Total Seepage',
        'imported_water': 'Imported Water',
    }
    # Fields in mm (need evaporation + transpiration combined)
    mm_fields = {
        'evapotranspiration': 'Evapotranspiration',
    }

    scenario_names = list(all_results.keys())

    # --- Volume fields: one figure per field ---
    for field_key, field_label in volume_fields.items():
        fig, ax = plt.subplots(figsize=(fig_width_inch, fig_height_inch))
        ax.set_xlabel("Time")
        locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

        for i, scenario in enumerate(scenario_names):
            agg = all_results[scenario]['aggregated']
            index = pd.to_datetime(agg.index)
            values = agg[field_key].pint.to('meter^3').pint.magnitude

            color = color_palette[i % len(color_palette)]
            marker = markers[i % len(markers)]
            ax.plot(index, values, color=color, linewidth=lw, label=scenario,
                    marker=marker, markevery=marker_every, markersize=4)

        ax.set_ylabel(fr"{field_label} [$\mathrm{{m}}^3$/day]")
        ax.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
        ax.yaxis.offsetText.set_fontsize(8)
        ax.yaxis.offsetText.set_position((1.05, 1.0))

        ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.15),
                  ncol=min(len(scenario_names), 5), frameon=False)
        plt.tight_layout()

        out_file = output_dir / f'{field_key}.png'
        plt.savefig(out_file, format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)

    # --- Evapotranspiration figure ---
    fig, ax = plt.subplots(figsize=(fig_width_inch, fig_height_inch))
    ax.set_xlabel("Time")
    locator = mdates.AutoDateLocator(minticks=4, maxticks=12)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    for i, scenario in enumerate(scenario_names):
        agg = all_results[scenario]['aggregated']
        index = pd.to_datetime(agg.index)
        et = (agg['evaporation'] + agg['transpiration']).pint.to('millimeter').pint.magnitude

        color = color_palette[i % len(color_palette)]
        marker = markers[i % len(markers)]
        ax.plot(index, et, color=color, linewidth=lw, label=scenario,
                marker=marker, markevery=marker_every, markersize=4)

    ax.set_ylabel("Evapotranspiration [mm/day]")

    ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.15),
              ncol=min(len(scenario_names), 5), frameon=False)
    plt.tight_layout()

    out_file = output_dir / 'evapotranspiration.png'
    plt.savefig(out_file, format='png', dpi=300, bbox_inches='tight')
    plt.close(fig)

    logger.info("Scenario comparison plots saved to %s", output_dir)

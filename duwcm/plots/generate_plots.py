from typing import Dict, List
from pathlib import Path
import pandas as pd

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns

def generate_plots(results: pd.DataFrame, forcing: pd.DataFrame, output_dir: Path):
    """
    Plot figures for aggregated results across all cells using df.plot with custom styling.

    Args:
        results (pd.DataFrame): DataFrame containing aggregated results
        forcing (pd.DataFrame): Climate forcing data
        output_dir (Path): Directory to save the output figures

    Returns:
        None (saves PDF and PGF files for each plot)
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

    fig_width_cm = 18
    fig_height_cm = 12
    fig_width_inch = fig_width_cm / 2.54
    fig_height_inch = fig_height_cm / 2.54

    output_dir.mkdir(parents=True, exist_ok=True)

    results.index = forcing.index
    plot_data = pd.DataFrame({
        'Precipitation': forcing['precipitation'],
        'PotentialEvaporation': forcing['potential_evaporation'],
        'Evapotranspiration': (results['evaporation'] + results['transpiration']),
        'Runoff': results['stormwater'],
        'Sewerage': results['sewerage'],
        'Baseflow': results['baseflow']
    })

    plot_configs = [
        ('Runoff'),
        ('Baseflow'),
        ('Sewerage')
    ]
    index = pd.to_datetime(plot_data.index)
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']

    fig, ax1 = plt.subplots(figsize=(fig_width_inch, fig_height_inch))
    ax1.set_xlabel("Time")
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))

    ax1.fill_between(index, 0, plot_data['Precipitation'],
                            facecolor='C0', alpha=0.8, label='Precipitation')
    ax1.plot(index, plot_data['PotentialEvaporation'], linestyle='--', linewidth=lw,
             color='C6', label='Potential Evaporation')
    ax1.plot(index, plot_data['Evapotranspiration'], color='C4', linewidth=lw, label='Evapotranspiration')
    ax1.set_ylabel(r"Precipitation & Evapotranspiration [mm/day]")
    ax1.invert_yaxis()

    plt.tight_layout()

    lines, labels = ax1.get_legend_handles_labels()
    # Modified legend positioning
    ax1.legend(lines, labels, loc='upper center', bbox_to_anchor=(0.5, 1.15),
              ncol=3, frameon=False)

    # Save the figure
    base_filename = output_dir / 'evapotranspiration'
    plt.savefig(f"{base_filename}.png", format='png', dpi=300, bbox_inches='tight')
    plt.savefig(f"{base_filename}.pdf", format='pdf', dpi=300, bbox_inches='tight')
    plt.close(fig)

    for i, config in enumerate(plot_configs):
        fig, ax1 = plt.subplots(figsize=(fig_width_inch, fig_height_inch))
        ax1.set_xlabel("Time")
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))

        ax1.fill_between(index, 0, plot_data['Precipitation'], color='C0',
                         alpha=0.5,linewidth=0.1, label='Precipitation')
        ax1.plot(index, plot_data['Evapotranspiration'], linestyle='--', linewidth=lw,
                 color='C4', label='Evapotranspiration')
        ax1.set_ylabel(r"Precipitation & Evapotranspiration [mm/day]")
        ax1.invert_yaxis()

        ax2 = ax1.twinx()
        config_color = color_cycle[(i+1) % len(color_cycle)]
        ax2.plot(index, plot_data[config], color=config_color, linewidth=lw, label=config)
        ax2.set_ylabel(fr"{config} [$\mathrm{{m}}^3$/day]")

        # Format with scientific notation
        ax2.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
        ax2.yaxis.offsetText.set_fontsize(8)
        ax2.yaxis.offsetText.set_position((1.05, 1.0))

        plt.tight_layout()

        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        # Modified legend positioning
        ax2.legend(lines + lines2, labels + labels2, loc='upper center',
                  bbox_to_anchor=(0.5, 1.15), ncol=3, frameon=False)

        # Save the figure
        base_filename = output_dir / config.lower()
        plt.savefig(f"{base_filename}.png", format='png', dpi=300, bbox_inches='tight')
#        plt.savefig(f"{base_filename}.pdf", format='pdf', dpi=300, bbox_inches='tight')
        plt.close(fig)

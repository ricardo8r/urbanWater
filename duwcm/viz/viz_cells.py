import ipywidgets as widgets
import geopandas as gpd
import plotly.graph_objects as go
from IPython.display import display
from duwcm.viz import create_map_base

def interactive_cell_selection(config, geo_file, background_file, flow_paths):
    """
    Creates an interactive cell selection tool with a selectable map and action buttons.

    Parameters:
    - config: Configuration object containing grid settings.
    - geo_file: Path to the spatial grid file.
    - background_file: Path to the background shapefile.
    - flow_paths: Flow paths used in visualization.

    Returns:
    - selected_cells (set): A set of selected cell IDs.
    """
    selected_cells = set()
    selection_output = widgets.Output()

    def create_selectable_map():
        gdf_geometry = gpd.read_file(geo_file)
        fig = create_map_base(geo_file, background_file, flow_paths)

        # Set proper customdata for selection
        fig.data[0].customdata = gdf_geometry['BlockID'].values
        fig.data[0].hovertemplate = "Cell ID: %{customdata}<extra></extra>"

        # Proper styling for selection state
        fig.data[0].selected = {'marker': {'opacity': 1.0}}
        fig.data[0].unselected = {'marker': {'opacity': 0.3}}

        fig.update_layout(
            clickmode='event+select',
            dragmode='select',
            showlegend=False,
            height=800,
            updatemenus=[]
        )
        return fig

    def selection_fn(trace, points, _):
        if points.point_inds:
            selected_cells.clear()  # Clear previous selection
            for i in points.point_inds:
                cell_id = int(trace.customdata[i])
                selected_cells.add(cell_id)

    def apply_selection(_):
        with selection_output:
            selection_output.clear_output()
            if selected_cells:
                config.grid['selected_cells'] = sorted(selected_cells)
                print(f"Selected cells: {config.grid['selected_cells']}")
            else:
                if 'selected_cells' in config.grid:
                    del config.grid['selected_cells']
                print("No cells selected - will use all cells")

    def clear_selection(_):
        selected_cells.clear()
        if 'selected_cells' in config.grid:
            del config.grid['selected_cells']
        with selection_output:
            selection_output.clear_output()
            print("Selection cleared")

    # Create buttons
    apply_button = widgets.Button(description='Apply Selection', button_style='success')
    clear_button = widgets.Button(description='Clear Selection', button_style='danger')

    apply_button.on_click(apply_selection)
    clear_button.on_click(clear_selection)

    base_map = create_selectable_map()
    fig_widget = go.FigureWidget(base_map)
    fig_widget.data[0].on_selection(selection_fn)

    display(widgets.VBox([
        fig_widget,
        widgets.HBox([apply_button, clear_button]),
        selection_output
    ]))

    return selected_cells


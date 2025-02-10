import ipywidgets as widgets
import geopandas as gpd
import plotly.graph_objects as go
from IPython.display import display
from duwcm.functions.cell_selector import select_cells
from duwcm.viz import create_map_base

def interactive_cell_selection(config, geo_file, background_file, flow_paths, model_params):
    """
    Creates an interactive cell selection tool with a selectable map and action buttons.

    Parameters:
    - config: Configuration object containing grid settings.
    - geo_file: Path to the spatial grid file.
    - background_file: Path to the background shapefile.
    - flow_paths: Flow paths used in visualization.
    - model_params: Dictionary containing model parameters.

    Returns:
    - filtered_params: Dictionary of model parameters for selected cells.
    - filtered_paths: DataFrame of flow paths for selected cells.
    """
    selected_cells = set(config.grid.get("selected_cells", []))  # Ensure persistence
    selection_output = widgets.Output()

    def create_selectable_map():
        gdf_geometry = gpd.read_file(geo_file)
        fig = create_map_base(geo_file, background_file, flow_paths)

        fig.data[0].customdata = gdf_geometry['BlockID'].values
        fig.data[0].hovertemplate = "Cell ID: %{customdata}<extra></extra>"

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
            selected_cells.update(int(trace.customdata[i]) for i in points.point_inds)

    def apply_selection(_):
        with selection_output:
            selection_output.clear_output()
            if selected_cells:
                config.grid["selected_cells"] = sorted(selected_cells)  # Persist selection
                print(f"Selected cells: {config.grid['selected_cells']}")
            else:
                config.grid.pop("selected_cells", None)
                print("No cells selected - using all cells")

    def clear_selection(_):
        selected_cells.clear()
        config.grid.pop("selected_cells", None)
        with selection_output:
            selection_output.clear_output()
            print("Selection cleared")

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

    return select_cells(model_params, flow_paths, config.grid.get("selected_cells", []))

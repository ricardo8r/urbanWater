from typing import Dict, List, Tuple
import logging
import pandas as pd
from pathlib import Path

from duwcm.data_structures import UrbanWaterData

logger = logging.getLogger(__name__)

def check_cell(urban_data: UrbanWaterData) -> Dict[str, Dict]:
    """
    Run comprehensive checks on a single cell's water balance.

    Args:
        urban_data (UrbanWaterData): Data for a single urban cell

    Returns:
        Dict[str, Dict]: Dictionary containing validation results for:
            - Flow connections
            - Storage constraints
            - Water balance
    """
    results = {
        'flow_validation': urban_data.validate_flows(),
        'storage_validation': urban_data.validate_storage(),
        'water_balance': urban_data.validate_water_balance()
    }

    return results

def check_all(cells: Dict[int, UrbanWaterData]) -> Tuple[Dict[int, Dict], List[str]]:
    """
    Run comprehensive checks on all cells in the model.

    Args:
        cells (Dict[int, UrbanWaterData]): Dictionary of cell data indexed by cell ID

    Returns:
        Tuple[Dict[int, Dict], List[str]]:
            - Dictionary of validation results for each cell
            - List of critical issues found
    """
    all_results = {}
    critical_issues = []

    for cell_id, cell_data in cells.items():
        cell_results = check_cell(cell_data)
        all_results[cell_id] = cell_results

        # Check for critical issues
        if cell_results['flow_validation']['unlinked']:
            critical_issues.append(f"Cell {cell_id}: Unlinked flows detected")

        if cell_results['storage_validation']:
            critical_issues.append(f"Cell {cell_id}: Storage violations detected")

        # Check for significant water balance errors (e.g., > 1% of total flow)
        for comp_name, balance in cell_results['water_balance'].items():
            if abs(balance['balance']) > 0.01 * max(balance['inflow'], balance['outflow']):
                critical_issues.append(
                    f"Cell {cell_id}, {comp_name}: Significant water balance error "
                    f"({balance['balance']:.2f})"
                )

    return all_results, critical_issues

def generate_report(results: Dict[int, Dict], output_dir: Path) -> None:
    """
    Generate detailed CSV reports of water balance check results.

    Args:
        results (Dict[int, Dict]): Check results from check_all()
        output_dir (Path): Directory to save the reports
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare data for each report type
    balance_data = []
    storage_violations = []
    flow_issues = []

    for cell_id, cell_results in results.items():
        # Water balance summary
        for comp_name, balance in cell_results['water_balance'].items():
            balance_data.append({
                'cell_id': cell_id,
                'component': comp_name,
                'inflow': balance['inflow'],
                'outflow': balance['outflow'],
                'storage_change': balance['total_storage_change'],
                'balance': balance['balance'],
                'error_percent': (balance['balance'] / max(balance['inflow'], balance['outflow'], 1e-10)) * 100
            })

        # Storage violations
        for comp_name, issues in cell_results['storage_validation'].items():
            for issue in issues:
                storage_violations.append({
                    'cell_id': cell_id,
                    'component': comp_name,
                    'issue': issue
                })

        # Flow issues
        for issue_type, issues in cell_results['flow_validation'].items():
            for issue in issues:
                flow_issues.append({
                    'cell_id': cell_id,
                    'type': issue_type,
                    'issue': issue
                })

    # Convert to DataFrames and save as CSV
    if balance_data:
        pd.DataFrame(balance_data).to_csv(output_dir / 'water_balance.csv', index=False)

    if storage_violations:
        pd.DataFrame(storage_violations).to_csv(output_dir / 'storage_violations.csv', index=False)

    if flow_issues:
        pd.DataFrame(flow_issues).to_csv(output_dir / 'flow_issues.csv', index=False)

    logger.info(f"Water balance check reports saved in {output_dir}")

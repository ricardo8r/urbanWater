"""
Validation and checking functionality for urban water model.

This module provides comprehensive validation and checking capabilities:
- Component-level validation (flows, storage, water balance)
- Cell-level validation
- Temporal tracking of validation results
- Analysis and reporting functions
"""
from typing import Dict
from pathlib import Path
import pandas as pd
from duwcm.water_model import UrbanWaterModel
from duwcm.data_structures import Storage

ZERO_THRESHOLD = 1e-10

def check_balance(model: UrbanWaterModel, current_date: pd.Timestamp) -> pd.DataFrame:
    """
    Track water balance for all cells and components at a given timestep.
    """
    balance_data = {
        'timestep': [],
        'cell': [],
        'component': [],
        'inflow': [],
        'outflow': [],
        'storage_change': [],
        'balance': [],
        'balance_error_percent': []
    }

    for cell_id, data in model.data.items():
        check_result = data.validate_water_balance(skip_components = {'groundwater'})

        for comp_name, values in check_result.items():
            balance_data['timestep'].append(current_date)
            balance_data['cell'].append(cell_id)
            balance_data['component'].append(comp_name)
            balance_data['inflow'].append(values['inflow'])
            balance_data['outflow'].append(values['outflow'])
            balance_data['storage_change'].append(values['total_storage_change'])
            balance_data['balance'].append(values['balance'])

            if abs(values['balance']) < ZERO_THRESHOLD:
                error_percent = 0
            else:
                total_magnitude = abs(values['inflow']) + abs(values['outflow']) + abs(values['total_storage_change'])
                if total_magnitude > ZERO_THRESHOLD:
                    error_percent = (values['balance'] / total_magnitude) * 100
                else:
                    error_percent = 0
            balance_data['balance_error_percent'].append(error_percent)

    return pd.DataFrame(balance_data)

def check_flows(model: UrbanWaterModel, current_date: pd.Timestamp) -> pd.DataFrame:
    """
    Check flow connections between components for all cells at given timestep.
    """
    flow_data = {
        'timestep': [],
        'cell': [],
        'issue_type': [],
        'description': [],
        'source_component': [],
        'target_component': [],
        'source_flow': [],
        'target_flow': [],
        'source_amount': [],
        'target_amount': []
    }

    for cell_id, data in model.data.items():
        # Use validate_flows from UrbanWaterData
        validation = data.validate_flows()

        # Process unlinked flows
        for issue in validation['unlinked']:
            source, target = issue.split(' -> ')
            src_comp, src_flow = source.split('.')
            tgt_comp, tgt_flow = target.split('.')

            flow_data['timestep'].append(current_date)
            flow_data['cell'].append(cell_id)
            flow_data['issue_type'].append('unlinked')
            flow_data['description'].append(f"Unlinked flow between {source} and {target}")
            flow_data['source_component'].append(src_comp)
            flow_data['target_component'].append(tgt_comp)
            flow_data['source_flow'].append(src_flow)
            flow_data['target_flow'].append(tgt_flow)
            flow_data['source_amount'].append(None)
            flow_data['target_amount'].append(None)

        # Process mismatched flows
        for issue in validation['mismatched']:
            src, tgt = issue.split(' ≠ ')
            src_comp, src_detail = src.split('(')
            tgt_comp, tgt_detail = tgt.split('(')

            src_amount = float(src_detail.strip(')'))
            tgt_amount = float(tgt_detail.strip(')'))

            flow_data['timestep'].append(current_date)
            flow_data['cell'].append(cell_id)
            flow_data['issue_type'].append('mismatched')
            flow_data['description'].append(f"Mismatched flow amounts: {issue}")
            flow_data['source_component'].append(src_comp.split('.')[0])
            flow_data['target_component'].append(tgt_comp.split('.')[0])
            flow_data['source_flow'].append(src_comp.split('.')[1])
            flow_data['target_flow'].append(tgt_comp.split('.')[1])
            flow_data['source_amount'].append(src_amount)
            flow_data['target_amount'].append(tgt_amount)

    return pd.DataFrame(flow_data)

def check_storage(model: UrbanWaterModel, current_date: pd.Timestamp) -> pd.DataFrame:
    """
    Check if any storage in any component violates physical constraints.

    Args:
        model: The water model instance
        current_date: Current simulation timestep

    Returns:
        DataFrame with columns:
        - timestep: When violation occurred
        - cell: Which grid cell
        - component: Which component (roof, groundwater etc)
        - storage_name: Name of the storage variable
        - issue_type: 'exceeds_capacity' or 'negative_storage'
        - current_value: The problematic storage value
        - capacity: The storage capacity (or 0 for negative checks)
    """
    violations = []

    for cell_id, data in model.data.items():
        # Check each component that has storage
        for comp_name, component in data.iter_components():
            # Check each storage attribute in the component
            for attr_name, attr_value in vars(component).items():
                if isinstance(attr_value, Storage):
                    current_storage = attr_value.get_amount('m3')
                    capacity = attr_value.get_capacity('m3')

                    # Check if storage exceeds capacity
                    if current_storage > capacity * 1.001:  # Small tolerance
                        violations.append({
                            'timestep': current_date,
                            'cell': cell_id,
                            'component': comp_name,
                            'storage_name': attr_name,
                            'issue_type': 'exceeds_capacity',
                            'current_value': current_storage,
                            'capacity': capacity
                        })

                    # Check for negative storage
                    if current_storage < 0:
                        violations.append({
                            'timestep': current_date,
                            'cell': cell_id,
                            'component': comp_name,
                            'storage_name': attr_name,
                            'issue_type': 'negative_storage',
                            'current_value': current_storage,
                            'capacity': 0
                        })

    return pd.DataFrame(violations)

def track_validation_results(model: UrbanWaterModel, current_date: pd.Timestamp) -> Dict[str, pd.DataFrame]:
    """
    Track all validation results for given timestep.
    """
    return {
        'balance': check_balance(model, current_date),
        'flows': check_flows(model, current_date),
        'storage': check_storage(model, current_date)
    }

def analyze_balance_errors(balance_df: pd.DataFrame, threshold: float = 1.0) -> Dict[str, pd.DataFrame]:
    """
    Analyze water balance errors and identify problematic components/cells.
    """
    violations = balance_df[abs(balance_df['balance_error_percent']) > threshold].copy()

    summary = balance_df.groupby(['component']).agg({
        'balance_error_percent': ['mean', 'std', 'min', 'max'],
        'balance': ['mean', 'std', 'min', 'max']
    })

    return {
        'summary': summary,
        'violations': violations
    }

def generate_report(validation_results: Dict[str, pd.DataFrame], output_dir: Path) -> None:
    """
    Generate detailed CSV reports of validation results.

    Args:
        validation_results: Dictionary of validation DataFrames
            - balance: Water balance validation DataFrame
            - flows: Flow validation DataFrame
            - storage: Storage validation DataFrame
        output_dir: Directory to save the reports
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Process each type of validation result
    for check_type, df in validation_results.items():
        # Save full results
        df.to_csv(output_dir / f'validation_{check_type}.csv')

        # Generate summaries based on validation type
        if check_type == 'balance' and 'balance_error_percent' in df.columns:
            # Create balance summary
            summary = df.groupby(['component']).agg({
                'balance_error_percent': ['mean', 'std', 'min', 'max'],
                'balance': ['mean', 'std', 'min', 'max']
            })
            summary.to_csv(output_dir / 'balance_summary.csv')

            # Save violations (errors > 1%)
            violations = df[abs(df['balance_error_percent']) > 1.0]
            if not violations.empty:
                violations.to_csv(output_dir / 'balance_violations.csv')

        elif check_type == 'flows' and not df.empty:
            # Summary of flow issues by type
            flow_summary = df.groupby(['issue_type', 'source_component', 'target_component']).size()
            flow_summary.to_csv(output_dir / 'flow_issues_summary.csv')

        elif check_type == 'storage' and not df.empty:
            # Summary of storage violations by component
            storage_summary = df.groupby(['component', 'issue_type']).size()
            storage_summary.to_csv(output_dir / 'storage_violations_summary.csv')

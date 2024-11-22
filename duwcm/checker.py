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
        check_result = data.validate_water_balance()

        for comp_name, values in check_result.items():
            balance_data['timestep'].append(current_date)
            balance_data['cell'].append(cell_id)
            balance_data['component'].append(comp_name)
            balance_data['inflow'].append(values['inflow'])
            balance_data['outflow'].append(values['outflow'])
            balance_data['storage_change'].append(values['total_storage_change'])
            balance_data['balance'].append(values['balance'])

            if values['balance'] == 0:
                error_percent = 0
            else:
                if abs(values['inflow']) > 0 or abs(values['outflow']) > 0 or abs(values['total_storage_change']) > 0:
                    error_percent = (values['balance'] /
                                     max(abs(values['inflow']),
                                         abs(values['outflow']),
                                         abs(values['total_storage_change']))) * 100
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
    Check storage constraints for all cells at given timestep.
    """
    storage_data = {
        'timestep': [],
        'cell': [],
        'component': [],
        'storage_name': [],
        'issue_type': [],
        'current_value': [],
        'limit_value': [],
        'description': []
    }

    for cell_id, data in model.data.items():
        # Use validate_storage from UrbanWaterData
        validation = data.validate_storage()

        for comp_name, issues in validation.items():
            for issue in issues:
                # Parse issue string to extract values
                if 'exceeds capacity' in issue:
                    storage_name, details = issue.split(': ')
                    current_val = float(details.split('(')[1].split(')')[0])
                    capacity_val = float(details.split('(')[2].split(')')[0])
                    issue_type = 'exceeds_capacity'
                elif 'Negative storage' in issue:
                    storage_name, details = issue.split(': ')
                    current_val = float(details)
                    capacity_val = 0
                    issue_type = 'negative_storage'
                else:
                    continue

                storage_data['timestep'].append(current_date)
                storage_data['cell'].append(cell_id)
                storage_data['component'].append(comp_name)
                storage_data['storage_name'].append(storage_name)
                storage_data['issue_type'].append(issue_type)
                storage_data['current_value'].append(current_val)
                storage_data['limit_value'].append(capacity_val)
                storage_data['description'].append(issue)

    return pd.DataFrame(storage_data)

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

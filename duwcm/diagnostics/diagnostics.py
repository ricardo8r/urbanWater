"""
diagnostic and checking functionality for urban water model.

This module provides comprehensive diagnostic and checking capabilities:
- Component-level diagnostic (flows, storage, water balance)
- Cell-level diagnostic
- Temporal tracking of diagnostic results
- Analysis and reporting functions
"""
from typing import Dict, Optional
from pathlib import Path
import pandas as pd
from duwcm.water_model import UrbanWaterModel
from duwcm.data_structures import Storage

ZERO_THRESHOLD = 1e-10

class DiagnosticTracker:

    def __init__(self):
        """Initialize empty diagnostic history."""
        self.history = []

    def track_diagnostic_results(self, model: UrbanWaterModel, current_date: pd.Timestamp) -> None:
        """Store diagnostic results for current timestep using existing checker functions."""
        timestep_results = {
            'balance': self.check_balance(model, current_date),
            'flows': self.check_flows(model, current_date),
            'storage': self.check_storage(model, current_date),
            'detailed_flows': self.track_detailed_flows(model, current_date)

        }
        self.history.append(timestep_results)

    def get_results(self) -> Dict[str, pd.DataFrame]:
        """Get complete diagnostic history by concatenating timestep results."""
        return {
            diagnostic_type: pd.concat([results[diagnostic_type] for results in self.history])
            for diagnostic_type in ['balance', 'flows', 'storage']
        }

    def generate_report(self, output_dir: Path) -> None:
        """
        Generate detailed CSV reports of diagnostic results.

        Args:
            diagnostic_results: Dictionary of diagnostic DataFrames
                - balance: Water balance diagnostic DataFrame
                - flows: Flow diagnostic DataFrame
                - storage: Storage diagnostic DataFrame
            output_dir: Directory to save the reports
        """
        diagnostic_results = self.get_results()

        output_dir.mkdir(parents=True, exist_ok=True)

        # Process each type of diagnostic result
        for check_type, df in diagnostic_results.items():
            # Generate summaries based on diagnostic type
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


    def check_balance(self, model: UrbanWaterModel, current_date: pd.Timestamp) -> pd.DataFrame:
        """
        Track water balance for all cells and components at a given timestep.
        """
        balance_data = {
            'timestep': [],
            'cell': [],
            'component': [],
            'total_inflow': [],
            'total_outflow': [],
            'storage_change': [],
            'balance': [],
            'balance_error_percent': []
        }

        for cell_id, data in model.data.items():
            check_result = data.validate_water_balance(skip_components = {})

            for comp_name, values in check_result.items():
                balance_data['timestep'].append(current_date)
                balance_data['cell'].append(cell_id)
                balance_data['component'].append(comp_name)
                balance_data['total_inflow'].append(values['total_inflow'])
                balance_data['total_outflow'].append(values['total_outflow'])
                balance_data['storage_change'].append(values['total_storage_change'])
                balance_data['balance'].append(values['balance'])

                if abs(values['balance']) < ZERO_THRESHOLD:
                    error_percent = 0
                else:
                    total_magnitude = (abs(values['total_inflow']) + abs(values['total_outflow']) +
                                       abs(values['total_storage_change']))
                    if total_magnitude > ZERO_THRESHOLD:
                        error_percent = (values['balance'] / total_magnitude) * 100
                    else:
                        error_percent = 0
                balance_data['balance_error_percent'].append(error_percent)

        return pd.DataFrame(balance_data)

    def check_flows(self, model: UrbanWaterModel, current_date: pd.Timestamp) -> pd.DataFrame:
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
            diagnostic = data.validate_flows()

            # Process unlinked flows
            for issue in diagnostic['unlinked']:
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
            for issue in diagnostic['mismatched']:
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

    def check_storage(self, model: UrbanWaterModel, current_date: pd.Timestamp) -> pd.DataFrame:
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
                        if current_storage > capacity * 1.00001:
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


    def track_detailed_flows(self, model: UrbanWaterModel, current_date: pd.Timestamp) -> pd.DataFrame:
        """
        Track detailed component flows for all cells at a given timestep.
        """
        flow_data = {
            'timestep': [],
            'cell': [],
            'component': [],
            'flow_type': [],
            'flow_name': [],
            'amount': []
        }

        for cell_id, data in model.data.items():
            check_result = data.validate_water_balance(skip_components={})

            for comp_name, values in check_result.items():
                # Track inflows
                for flow_name, amount in values['inflows'].items():
                    flow_data['timestep'].append(current_date)
                    flow_data['cell'].append(cell_id)
                    flow_data['component'].append(comp_name)
                    flow_data['flow_type'].append('inflow')
                    flow_data['flow_name'].append(flow_name)
                    flow_data['amount'].append(amount)

                # Track outflows
                for flow_name, amount in values['outflows'].items():
                    flow_data['timestep'].append(current_date)
                    flow_data['cell'].append(cell_id)
                    flow_data['component'].append(comp_name)
                    flow_data['flow_type'].append('outflow')
                    flow_data['flow_name'].append(flow_name)
                    flow_data['amount'].append(amount)

                # Track storage changes
                for storage_name, change in values['storage_changes'].items():
                    flow_data['timestep'].append(current_date)
                    flow_data['cell'].append(cell_id)
                    flow_data['component'].append(comp_name)
                    flow_data['flow_type'].append('storage')
                    flow_data['flow_name'].append(storage_name)
                    flow_data['amount'].append(change)

        return pd.DataFrame(flow_data)

    def get_detailed_results(self) -> pd.DataFrame:
        """Get detailed flow tracking history."""
        return pd.concat([results['detailed_flows'] for results in self.history])

    def get_internal_flow_matrix(self, cell_id: Optional[int] = None,
                                 timestep: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        """
        Generate a cell internal flow matrix.
        """
        detailed_flows = self.get_detailed_results()

        # Apply filters
        if cell_id is not None:
            detailed_flows = detailed_flows[detailed_flows['cell'] == cell_id]
        if timestep is not None:
            detailed_flows = detailed_flows[detailed_flows['timestep'] == timestep]

        # Identify unique components and special flows
        components = set(detailed_flows['component'].unique())

        # Compute net storage changes
        storage_flows = detailed_flows[detailed_flows['flow_type'] == 'storage']
        net_storage_changes = storage_flows.groupby(['component', 'flow_name'])['amount'].sum()
        storage_nodes = {f"{comp}_{storage}" for comp, storage in net_storage_changes.index if storage}

        # Calculate net seepage and baseflow
        seepage_flows = detailed_flows[detailed_flows['flow_name'] == 'seepage']
        net_seepage = seepage_flows['amount'].sum()

        baseflow_flows = detailed_flows[detailed_flows['flow_name'] == 'baseflow']
        net_baseflow = baseflow_flows['amount'].sum()

        # Define special nodes
        special_nodes = {'precipitation', 'imported_water', 'evaporation', 'transpiration', 'seepage', 'baseflow'}
        all_nodes = list(components) + list(storage_nodes) + list(special_nodes)
        all_nodes = [node for node in all_nodes if node]

        # Initialize flow matrix
        flow_matrix = pd.DataFrame(0.0, index=all_nodes, columns=all_nodes)

        # Process each flow type
        for _, flow in detailed_flows.iterrows():
            src, dest, amount = None, None, flow['amount']
            if flow['flow_type'] == 'inflow':
                if flow['flow_name'] in {'precipitation', 'imported_water'}:
                    src, dest = flow['flow_name'], flow['component']
                elif flow['flow_name'].startswith('from_'):
                    src = flow['flow_name'].replace('from_', '')
                    dest = flow['component'] if src in components else None
            elif flow['flow_type'] == 'outflow':
                if flow['flow_name'] in {'evaporation', 'transpiration'}:
                    dest = flow['flow_name']
                    src = flow['component']
            if src and dest:
                flow_matrix.loc[src, dest] += amount

        # Add net storage changes
        for (comp, storage), net_change in net_storage_changes.items():
            if storage:
                storage_name = f"{comp}_{storage}"
                if comp == 'groundwater':
                    net_change = -net_change
                if net_change > 0:
                    flow_matrix.loc[storage_name, comp] += net_change
                elif net_change < 0:
                    flow_matrix.loc[comp, storage_name] += abs(net_change)


        # Add net seepage/baseflow
        if net_seepage > 0:
            flow_matrix.loc['groundwater', 'seepage'] = net_seepage
        else:
            flow_matrix.loc['seepage', 'groundwater'] = abs(net_seepage)

        if net_baseflow > 0:
            flow_matrix.loc['groundwater', 'baseflow'] = net_baseflow
        else:
            flow_matrix.loc['baseflow', 'groundwater'] = abs(net_baseflow)

        # Flip direction of negative flows
        negative_mask = flow_matrix < 0
        if negative_mask.any().any():
            # Add absolute values in opposite direction
            flow_matrix.T[negative_mask] = abs(flow_matrix[negative_mask])
            # Clear original negative values
            flow_matrix[negative_mask] = 0

        # Remove empty rows and columns
        mask = (flow_matrix.sum(axis=0) != 0) | (flow_matrix.sum(axis=1) != 0)
        return flow_matrix.loc[mask, mask]

    def get_external_flow_matrix(self, cell_id: Optional[int] = None,
                               timestep: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        """
        Generate a flow matrix showing external cell flows with net storage change.
        """
        detailed_flows = self.get_detailed_results()

        # Apply filters
        if cell_id is not None:
            detailed_flows = detailed_flows[detailed_flows['cell'] == cell_id]
        if timestep is not None:
            detailed_flows = detailed_flows[detailed_flows['timestep'] == timestep]

        # Define nodes
        nodes = ['precipitation', 'imported_water', 'evapotranspiration',
                 'sewerage_upstream', 'runoff_upstream',
                 'sewerage_downstream', 'runoff_downstream',
                 'seepage', 'baseflow', 'storage', f'cell_{cell_id}']

        flow_matrix = pd.DataFrame(0.0, index=nodes, columns=nodes)

        # Calculate net storage change first
        storage_changes = detailed_flows[detailed_flows['flow_type'] == 'storage']
        net_storage_change = storage_changes['amount'].sum()

        seepage_flows = detailed_flows[detailed_flows['flow_name'] == 'seepage']
        net_seepage = seepage_flows['amount'].sum()

        baseflow_flows = detailed_flows[detailed_flows['flow_name'] == 'baseflow']
        net_baseflow = baseflow_flows['amount'].sum()

        # Add net storage flow in the appropriate direction
        if net_storage_change > 0:
            flow_matrix.loc[f'cell_{cell_id}', 'storage'] = net_storage_change
        else:
            flow_matrix.loc['storage', f'cell_{cell_id}'] = abs(net_storage_change)

        # Process other flows
        for _, flow in detailed_flows.iterrows():
            if flow['flow_type'] == 'inflow':
                if flow['flow_name'] == 'precipitation':
                    flow_matrix.loc['precipitation', f'cell_{cell_id}'] += flow['amount']
                elif flow['flow_name'] == 'imported_water':
                    flow_matrix.loc['imported_water', f'cell_{cell_id}'] += flow['amount']
                elif flow['component'] == 'sewerage' and 'upstream' in flow['flow_name']:
                    flow_matrix.loc['sewerage_upstream', f'cell_{cell_id}'] += flow['amount']
                elif flow['component'] == 'stormwater' and 'upstream' in flow['flow_name']:
                    flow_matrix.loc['runoff_upstream', f'cell_{cell_id}'] += flow['amount']

            elif flow['flow_type'] == 'outflow':
                if flow['flow_name'] in ['evaporation', 'transpiration']:
                    flow_matrix.loc[f'cell_{cell_id}', 'evapotranspiration'] += flow['amount']
                elif flow['component'] == 'sewerage' and flow['flow_name'] == 'to_downstream':
                    flow_matrix.loc[f'cell_{cell_id}', 'sewerage_downstream'] += flow['amount']
                elif flow['component'] == 'stormwater' and flow['flow_name'] == 'to_downstream':
                    flow_matrix.loc[f'cell_{cell_id}', 'runoff_downstream'] += flow['amount']

        # Set seepage direction
        if net_seepage > 0:
            flow_matrix.loc[f'cell_{cell_id}', 'seepage'] = net_seepage
        else:
            flow_matrix.loc['seepage', f'cell_{cell_id}'] = abs(net_seepage)

        # Set baseflow direction
        if net_baseflow > 0:
            flow_matrix.loc[f'cell_{cell_id}', 'baseflow'] = net_baseflow
        else:
            flow_matrix.loc['baseflow', f'cell_{cell_id}'] = abs(net_baseflow)

        # Flip direction of negative flows
        negative_mask = flow_matrix < 0
        if negative_mask.any().any():
            # Add absolute values in opposite direction
            flow_matrix.T[negative_mask] = abs(flow_matrix[negative_mask])
            # Clear original negative values
            flow_matrix[negative_mask] = 0

        # Remove empty rows and columns
        mask = (flow_matrix.sum(axis=0) != 0) | (flow_matrix.sum(axis=1) != 0)
        return flow_matrix.loc[mask, mask]

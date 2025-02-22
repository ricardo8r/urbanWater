import logging
from duwcm.diagnostics import DiagnosticTracker

logger = logging.getLogger(__name__)
def alert(tracker: DiagnosticTracker) -> None:
    """Alert if there are significant diagnostic issues."""
    if not tracker:
        return

    results = tracker.get_results()

    # Check water balance
    balance_df = results['balance']
    errors = balance_df[abs(balance_df['balance_error_percent']) > 1.0]
    if not errors.empty:
        for comp in errors['component'].unique():
            comp_errors = errors[errors['component'] == comp]
            logger.warning("%d balance errors in %s component (max error: %.2f%%)",
                         len(comp_errors), comp,
                         comp_errors['balance_error_percent'].abs().max())

    # Check flow connections
    flows_df = results['flows']
    if not flows_df.empty:
        for issue_type in flows_df['issue_type'].unique():
            count = len(flows_df[flows_df['issue_type'] == issue_type])
            logger.warning("%d %s flow issues", count, issue_type)

    # Check storage violations
    storage_df = results['storage']
    if not storage_df.empty:
        for issue_type in storage_df['issue_type'].unique():
            issues = storage_df[storage_df['issue_type'] == issue_type]
            logger.warning("%d storage %s violations", len(issues), issue_type)

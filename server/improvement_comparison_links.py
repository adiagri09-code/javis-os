"""SQL-only comparison format selection; no grant, source or native readiness."""
from improvement_experiment_protocol import _id


def has_view_binding(connection, brain, comparison_id):
    _id(comparison_id)
    installed = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='improvement_comparison_views'").fetchone()
    return bool(installed and connection.execute('SELECT 1 FROM improvement_comparison_views WHERE comparison_id=? AND brain_id=?',
        (comparison_id, brain)).fetchone())


def require_legacy_comparison(connection, brain, comparison_id):
    if has_view_binding(connection, brain, comparison_id):
        raise PermissionError('view_trial_version_required')

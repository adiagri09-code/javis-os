"""Append-only isolated skill-view metadata; never execution or live authority.

Encrypted manifests and current host authority require separate verification.
These joins only establish immutable lineage within the existing shared store.
"""


def _digest(column):
    return f"CHECK(length({column})=64 AND {column} NOT GLOB '*[^0-9a-f]*')"


SCHEMA = (
    "CREATE TABLE improvement_effective_views("
    "id TEXT PRIMARY KEY,brain_id TEXT NOT NULL,experiment_id TEXT NOT NULL,target_id TEXT NOT NULL,"
    "context_id TEXT NOT NULL,comparison_id TEXT NOT NULL,variant TEXT NOT NULL CHECK(variant IN ('baseline','candidate')),"
    "candidate_id TEXT NOT NULL,base_revision_id TEXT NOT NULL,base_hash TEXT NOT NULL,"
    "base_generation INTEGER NOT NULL CHECK(base_generation>0),source_authority_hash TEXT NOT NULL,"
    "semantic_receipt_id TEXT NOT NULL,manifest_hash TEXT NOT NULL,manifest_blob_hash TEXT NOT NULL,created_at REAL NOT NULL,"
    "UNIQUE(id,brain_id),UNIQUE(comparison_id,brain_id,variant),CHECK(manifest_hash=manifest_blob_hash),"
    f"{_digest('manifest_hash')},{_digest('source_authority_hash')},"
    "FOREIGN KEY(experiment_id,brain_id) REFERENCES improvement_experiments(id,brain_id),"
    "FOREIGN KEY(target_id,brain_id) REFERENCES improvement_targets(id,brain_id),"
    "FOREIGN KEY(context_id,brain_id) REFERENCES improvement_trial_contexts(id,brain_id),"
    "FOREIGN KEY(comparison_id,brain_id) REFERENCES improvement_comparisons(id,brain_id),"
    "FOREIGN KEY(candidate_id,brain_id) REFERENCES improvement_skill_candidates(id,brain_id),"
    "FOREIGN KEY(base_revision_id,brain_id) REFERENCES improvement_revisions(id,brain_id),"
    "FOREIGN KEY(semantic_receipt_id,brain_id) REFERENCES improvement_semantic_receipts(id,brain_id))",
    "CREATE TABLE improvement_effective_view_assets("
    "view_id TEXT NOT NULL,brain_id TEXT NOT NULL,position INTEGER NOT NULL CHECK(position=0),"
    "asset_id TEXT NOT NULL,canonical_ref TEXT NOT NULL,before_hash TEXT NOT NULL,content_hash TEXT NOT NULL,"
    "identity TEXT NOT NULL,authority_hash TEXT NOT NULL,origin TEXT NOT NULL CHECK(origin IN ('baseline','candidate')),"
    "PRIMARY KEY(view_id,brain_id,position),"
    "FOREIGN KEY(view_id,brain_id) REFERENCES improvement_effective_views(id,brain_id))",
    "CREATE TABLE improvement_comparison_views("
    "comparison_id TEXT NOT NULL,brain_id TEXT NOT NULL,base_view_id TEXT NOT NULL,candidate_view_id TEXT NOT NULL,"
    "semantic_receipt_id TEXT NOT NULL,binding_hash TEXT NOT NULL,binding_blob_hash TEXT NOT NULL,created_at REAL NOT NULL,"
    "PRIMARY KEY(comparison_id,brain_id),CHECK(base_view_id!=candidate_view_id),CHECK(binding_hash=binding_blob_hash),"
    f"{_digest('binding_hash')},"
    "FOREIGN KEY(comparison_id,brain_id) REFERENCES improvement_comparisons(id,brain_id),"
    "FOREIGN KEY(base_view_id,brain_id) REFERENCES improvement_effective_views(id,brain_id),"
    "FOREIGN KEY(candidate_view_id,brain_id) REFERENCES improvement_effective_views(id,brain_id),"
    "FOREIGN KEY(semantic_receipt_id,brain_id) REFERENCES improvement_semantic_receipts(id,brain_id))",
    "CREATE TRIGGER improvement_effective_view_scope BEFORE INSERT ON improvement_effective_views WHEN NOT EXISTS "
    "(SELECT 1 FROM improvement_comparisons p "
    "JOIN improvement_experiments e ON e.id=p.experiment_id AND e.brain_id=p.brain_id "
    "JOIN improvement_experiment_arms a ON a.experiment_id=e.id AND a.brain_id=e.brain_id AND a.ordinal=p.ordinal "
    "JOIN improvement_skill_candidates c ON c.id=a.candidate_id AND c.brain_id=a.brain_id "
    "JOIN improvement_revisions r ON r.id=c.base_revision_id AND r.brain_id=c.brain_id "
    "JOIN improvement_trial_contexts x ON x.id=e.context_id AND x.brain_id=e.brain_id "
    "JOIN improvement_semantic_receipts s ON s.id=NEW.semantic_receipt_id AND s.brain_id=e.brain_id "
    "WHERE p.id=NEW.comparison_id AND p.brain_id=NEW.brain_id AND e.id=NEW.experiment_id "
    "AND e.target_id=NEW.target_id AND e.context_id=NEW.context_id AND x.experiment_id=e.id "
    "AND c.id=NEW.candidate_id AND c.experiment_id=e.id AND c.context_id=e.context_id AND c.target_id=e.target_id "
    "AND c.base_revision_id=NEW.base_revision_id AND c.base_hash=NEW.base_hash AND c.base_generation=NEW.base_generation "
    "AND r.target_id=e.target_id AND r.content_hash=c.base_hash "
    "AND a.envelope_hash=p.arm_hash AND p.definition_hash=e.definition_hash "
    "AND json_extract(a.envelope_json,'$.source_authority_hash')=NEW.source_authority_hash "
    "AND s.experiment_id=e.id AND s.candidate_id=c.id) "
    "BEGIN SELECT RAISE(ABORT,'effective_view_scope_mismatch'); END",
    "CREATE TRIGGER improvement_effective_view_asset_scope BEFORE INSERT ON improvement_effective_view_assets WHEN NOT EXISTS "
    "(SELECT 1 FROM improvement_effective_views v "
    "JOIN improvement_targets t ON t.id=v.target_id AND t.brain_id=v.brain_id "
    "JOIN improvement_skill_candidates c ON c.id=v.candidate_id AND c.brain_id=v.brain_id "
    "WHERE v.id=NEW.view_id AND v.brain_id=NEW.brain_id AND NEW.origin=v.variant "
    "AND NEW.canonical_ref=t.canonical_ref AND NEW.identity=t.identity "
    "AND NEW.before_hash=v.base_hash AND NEW.authority_hash=v.source_authority_hash "
    "AND ((v.variant='baseline' AND NEW.asset_id=v.base_revision_id AND NEW.content_hash=v.base_hash) "
    "OR (v.variant='candidate' AND NEW.asset_id=c.id AND NEW.content_hash=c.content_hash))) "
    "BEGIN SELECT RAISE(ABORT,'effective_view_asset_scope_mismatch'); END",
    "CREATE TRIGGER improvement_comparison_view_scope BEFORE INSERT ON improvement_comparison_views WHEN NOT EXISTS "
    "(SELECT 1 FROM improvement_effective_views b "
    "JOIN improvement_effective_views c ON c.comparison_id=b.comparison_id AND c.brain_id=b.brain_id "
    "JOIN improvement_effective_view_assets ba ON ba.view_id=b.id AND ba.brain_id=b.brain_id AND ba.position=0 "
    "JOIN improvement_effective_view_assets ca ON ca.view_id=c.id AND ca.brain_id=c.brain_id AND ca.position=0 "
    "WHERE b.id=NEW.base_view_id AND c.id=NEW.candidate_view_id AND b.brain_id=NEW.brain_id "
    "AND b.comparison_id=NEW.comparison_id AND b.variant='baseline' AND c.variant='candidate' "
    "AND b.semantic_receipt_id=NEW.semantic_receipt_id AND c.semantic_receipt_id=NEW.semantic_receipt_id "
    "AND b.candidate_id=c.candidate_id AND b.source_authority_hash=c.source_authority_hash "
    "AND ba.canonical_ref=ca.canonical_ref AND ba.identity=ca.identity AND ba.before_hash=ca.before_hash) "
    "BEGIN SELECT RAISE(ABORT,'comparison_view_scope_mismatch'); END",
)

IMMUTABLE = ('improvement_effective_views', 'improvement_effective_view_assets', 'improvement_comparison_views')


def assert_installed(connection):
    """Refuse changed draft guards before authority, without repairing history."""
    import re
    from improvement_store import ConflictError
    from improvement_operation_schema import assert_installed as assert_operations

    assert_operations(connection)
    statements = list(SCHEMA)
    statements.extend(f"CREATE TRIGGER {table}_{action.lower()} BEFORE {action} ON {table} "
                      "BEGIN SELECT RAISE(ABORT,'immutable_improvement_history'); END"
                      for table in IMMUTABLE for action in ('UPDATE', 'DELETE'))
    installed = {row['name']: ' '.join((row['sql'] or '').split()).rstrip(';')
                 for row in connection.execute("SELECT name,sql FROM sqlite_master WHERE name LIKE 'improvement_%'")}
    for statement in statements:
        name = re.match(r'CREATE (?:UNIQUE )?(?:TABLE|INDEX|TRIGGER) ([a-z_][a-z_0-9]*)', statement)[1]
        if installed.get(name) != ' '.join(statement.split()).rstrip(';'):
            raise ConflictError('view_schema_changed')

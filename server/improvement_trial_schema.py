"""M1 durable execution references in the existing improvement/resonance database."""

SCHEMA = (
    "CREATE TABLE improvement_trials(id TEXT PRIMARY KEY,brain_id TEXT NOT NULL,logical_key TEXT NOT NULL,"
    "request_hash TEXT NOT NULL,request_json TEXT NOT NULL,status TEXT NOT NULL,generation INTEGER NOT NULL,"
    "attempt INTEGER NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL,"
    "UNIQUE(brain_id,logical_key),UNIQUE(id,brain_id))",
    "CREATE TABLE improvement_trial_attempts(trial_id TEXT NOT NULL,brain_id TEXT NOT NULL,attempt INTEGER NOT NULL,"
    "status TEXT NOT NULL,call_id INTEGER NOT NULL UNIQUE,lease_token TEXT,lease_until REAL,engine_at REAL,"
    "materialization_hash TEXT,workspace_json TEXT,result_json TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL,"
    "PRIMARY KEY(trial_id,attempt),FOREIGN KEY(trial_id,brain_id) REFERENCES improvement_trials(id,brain_id),"
    "FOREIGN KEY(call_id) REFERENCES agent_calls(id))",
    "CREATE TABLE improvement_trial_observations(trial_id TEXT NOT NULL,brain_id TEXT NOT NULL,attempt INTEGER NOT NULL,"
    "sequence INTEGER NOT NULL,kind TEXT NOT NULL,payload_hash TEXT NOT NULL,blob_hashes_json TEXT NOT NULL,"
    "created_at REAL NOT NULL,PRIMARY KEY(trial_id,attempt,sequence),"
    "FOREIGN KEY(trial_id,brain_id) REFERENCES improvement_trials(id,brain_id),"
    "FOREIGN KEY(trial_id,attempt) REFERENCES improvement_trial_attempts(trial_id,attempt))",
)

IMMUTABLE = ("improvement_trial_observations",)

# MotorAI SIL Worker

This is a lightweight remote Simulink worker. It keeps no iteration history.
Each run overwrites the files directly under `jobs/`.

## Reused Existing Code

The worker reuses these files from `Optimize/agent_silhelper`:

- `agent_silhelper/local_sil_runner.py`
  - Connects to a shared local MATLAB Engine session.
  - Loads and runs the local `.slx` model.
  - Reads Scope/workspace variables from MATLAB.
  - Converts raw Scope data into semantic `signals`.

- `agent_silhelper/run_local_job.py`
  - Command-line wrapper for one simulation job.
  - Writes `raw.json` and `processed.json`.

`remote_sil_worker.py` is only an HTTP wrapper around `run_local_job.py`.
Before each remote simulation it writes the received network ports to
`<remote_model_dir>/network.json`, then starts `run_local_job.py`.

## Remote PC Setup

1. Start MATLAB on the remote PC.
2. In MATLAB, run:

```matlab
matlab.engine.shareEngine
```

3. Edit `silworker_config.json` if needed.
4. Start the worker:

```bat
start_worker.bat
```

The default endpoint is:

```text
http://<remote-pc-ip>:8787
```

## API

Health check:

```http
GET /health
```

Run one simulation:

```http
POST /run_simulation
Content-Type: application/json
```

Example body:

```json
{
  "job_id": "candidate_02_iter_001",
  "candidate_id": "candidate_02",
  "remote_model_path": "D:/MotorAIWorker/candidate_02/project/simulate/MCS_STD_PMSM_MODEL.slx",
  "scope_map": {
    "ScopeData1": ["speed_ref", "speed_fb"],
    "ScopeData2": ["iq_ref", "iq_fb"]
  },
  "network_config": {
    "target_address": "192.168.1.10",
    "receive_port": 12500,
    "transmit_port": 12501,
    "command_recv_port": 12502,
    "command_trans_port": 12503
  },
  "timeout_sec": 1800,
  "no_open_ui": false
}
```

Response body contains `processed_json`. The main MotorAI process should write
that object to:

```text
candidate_xx/log/optimize/simulation/processed.json
```

## Worker Output Files

These files are overwritten on every run:

```text
jobs/request.json
jobs/scope_channel_map.json
jobs/raw.json
jobs/processed.json
jobs/run_local_job_stdout.txt
jobs/run_local_job_stderr.txt
```

The worker intentionally does not create `jobs/<job_id>/` folders. Historical
evaluation records belong on the main MotorAI side, not on the SIL worker.

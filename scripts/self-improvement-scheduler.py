#!/usr/bin/env python3
"""
Self-Improvement Scheduler
===========================
Background daemon that runs calibration, gate effectiveness, stop optimization,
and outcome updates on schedule. Includes startup catch-up for missed jobs.

Usage:
    python3 scripts/self-improvement-scheduler.py          # foreground
    python3 scripts/self-improvement-scheduler.py --daemon  # background (via start-analyst.sh)
    python3 scripts/self-improvement-scheduler.py --stop    # stop daemon
    python3 scripts/self-improvement-scheduler.py --status  # show job status

All jobs run inside the investor-agent-mcp Docker container via `docker exec`.
Job checkpoints are stored in the MSSQL `job_checkpoints` table for resilience.
"""

import subprocess
import time
import json
import signal
import sys
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

REPO_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_DIR / "logs"
PID_FILE = LOG_DIR / "scheduler.pid"
LOG_FILE = LOG_DIR / "scheduler.log"
CONTAINER = "investor-agent-mcp"
CHECK_INTERVAL_SECONDS = 60  # Check for due jobs every 60 seconds

# Job definitions: name → interval + Python code to run inside container
JOBS = {
    "daily_outcomes": {
        "interval_hours": 24,
        "description": "Update prediction outcomes with current prices + MFE/MAE",
        "python": (
            "from investor_agent.prediction_tracker import PredictionTracker; "
            "import json; t = PredictionTracker(); r = t.update_outcomes(); "
            "print(json.dumps({k:v for k,v in r.items() if k != 'updated_predictions'}, default=str))"
        ),
    },
    "weekly_calibration": {
        "interval_hours": 168,  # 7 days
        "description": "Brier score calibration + confidence multipliers",
        "python": (
            "from investor_agent.prediction_tracker import CalibrationEngine; "
            "import json; e = CalibrationEngine(); "
            "print(json.dumps(e.calibrate(), default=str))"
        ),
    },
    "weekly_gate_effectiveness": {
        "interval_hours": 168,
        "description": "Gate lift scores + recommended weights",
        "python": (
            "from investor_agent.prediction_tracker import GateEffectivenessAnalyzer; "
            "import json; a = GateEffectivenessAnalyzer(); "
            "print(json.dumps(a.analyze(), default=str))"
        ),
    },
    "weekly_efficiency_report": {
        "interval_hours": 168,
        "description": "Weekly efficiency report with component accuracy",
        "python": (
            "from investor_agent.prediction_tracker import EfficiencyReportGenerator; "
            "import json; g = EfficiencyReportGenerator(); "
            "print(json.dumps({k:v for k,v in g.generate_weekly_report(period_days=7).items() "
            "if k != 'full_report_markdown'}, default=str))"
        ),
    },
    "daily_vault_ingest": {
        "interval_hours": 24,
        "description": "Scan vault reports and backfill missing predictions into DB",
        "host_python": '''
import json, glob, subprocess, os
from pathlib import Path
from datetime import datetime, timedelta

VAULT = "/Users/AhmedE/Ahmed/Trading Reports"
CONTAINER = "investor-agent-mcp"

# 1. Get existing predictions from DB (ticker+date combos)
check_code = (
    "from investor_agent.database import execute_query; import json; "
    "rows = execute_query(\\"SELECT ticker, CONVERT(VARCHAR(10), created_at, 120) as dt FROM predictions WHERE created_at > DATEADD(day, -30, GETDATE())\\"); "
    "print(json.dumps([(r['ticker'], r['dt']) for r in rows]))"
)
proc = subprocess.run(["docker", "exec", CONTAINER, "python", "-c", check_code],
                      capture_output=True, text=True, timeout=30)
existing = set()
if proc.returncode == 0 and proc.stdout.strip():
    try:
        existing = {(t, d) for t, d in json.loads(proc.stdout.strip())}
    except: pass

# 2. Scan vault JSON sidecars (last 7 days only)
cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
jsons = sorted(glob.glob(os.path.join(VAULT, "*_*_2026-*.json")))
ingested = 0
skipped = 0
errors = 0

for jpath in jsons:
    fname = os.path.basename(jpath)
    # Parse date from filename: TICKER_TYPE_YYYY-MM-DD.json
    parts = fname.replace(".json", "").rsplit("_", 1)
    if len(parts) < 2:
        continue
    date_str = parts[-1]
    if date_str < cutoff:
        skipped += 1
        continue

    try:
        with open(jpath) as f:
            data = json.load(f)
    except:
        errors += 1
        continue

    ticker = data.get("ticker", "")
    if not ticker or not data.get("signal") or not data.get("direction"):
        skipped += 1
        continue
    # Skip portfolio reviews and non-stock entries
    if ticker.upper() in ("PORTFOLIO", "MARKET", "SECTOR"):
        skipped += 1
        continue

    # Skip if already in DB
    if (ticker, date_str) in existing:
        skipped += 1
        continue

    # 3. Store via MCP tool (JSON-RPC to docker)
    direction = data.get("direction", "LONG")
    report_type = "comprehensive" if "COMPREHENSIVE" in fname else "scanner" if "SCAN" in fname else "deep_dive"

    init_req = json.dumps({"jsonrpc":"2.0","method":"initialize","id":0,
        "params":{"protocolVersion":"2024-11-05","capabilities":{},
        "clientInfo":{"name":"vault_ingest","version":"1.0"}}})
    notif = json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"})
    tool_req = json.dumps({"jsonrpc":"2.0","method":"tools/call","id":1,
        "params":{"name":"store_trading_prediction",
        "arguments":{"ticker": ticker, "direction": direction,
        "report_type": report_type, "trading_signal": data}}})
    stdin_data = init_req + "\\n" + notif + "\\n" + tool_req + "\\n"

    try:
        r = subprocess.run(
            ["docker", "exec", "-i", CONTAINER, "python", "-m", "investor_agent.server_modular"],
            input=stdin_data, capture_output=True, text=True, timeout=120)
        for line in r.stdout.splitlines():
            try:
                resp = json.loads(line)
                if resp.get("id") == 1:
                    content = resp.get("result", {}).get("content", [])
                    for c in content:
                        if c.get("type") == "text" and "stored" in c.get("text", ""):
                            ingested += 1
                            break
                    else:
                        errors += 1
            except: pass
    except Exception as e:
        errors += 1

print(json.dumps({"status": "ingested", "ingested": ingested, "skipped": skipped, "errors": errors, "total_scanned": len(jsons)}))
''',
    },
    "weekly_model_decay": {
        "interval_hours": 168,  # 7 days
        "description": "Rolling accuracy drop detection — early warning for strategy degradation",
        "python": (
            "from investor_agent.tools.statistical_validation import _detect_decay_impl; "
            "import json; print(json.dumps(_detect_decay_impl(days=60, threshold=0.55), default=str))"
        ),
    },
    "monthly_stop_optimization": {
        "interval_hours": 720,  # 30 days
        "description": "MFE/MAE stop/target optimization",
        "python": (
            "from investor_agent.prediction_tracker import StopTargetOptimizer; "
            "import json; o = StopTargetOptimizer(); "
            "print(json.dumps(o.optimize(), default=str))"
        ),
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("scheduler")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(console_handler)

# ─────────────────────────────────────────────────────────────────────────────
# Docker helpers
# ─────────────────────────────────────────────────────────────────────────────

def docker_exec_python(code: str, timeout: int = 600) -> tuple[bool, str]:
    """Run Python code inside the investor-agent-mcp container."""
    try:
        result = subprocess.run(
            ["docker", "exec", CONTAINER, "python", "-c", code],
            capture_output=True, text=True, timeout=timeout
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            error = result.stderr.strip()
            return False, error or f"Exit code {result.returncode}"
        return True, output
    except subprocess.TimeoutExpired:
        return False, f"Timeout after {timeout}s"
    except Exception as e:
        return False, str(e)


def host_exec_python(code: str, timeout: int = 600) -> tuple[bool, str]:
    """Run Python code on the host machine (not in Docker)."""
    try:
        result = subprocess.run(
            ["python3", "-c", code],
            capture_output=True, text=True, timeout=timeout
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            error = result.stderr.strip()
            return False, error or f"Exit code {result.returncode}"
        return True, output
    except subprocess.TimeoutExpired:
        return False, f"Timeout after {timeout}s"
    except Exception as e:
        return False, str(e)


def container_running() -> bool:
    """Check if the Docker container is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() == "true"
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Job checkpoint management (via MSSQL job_checkpoints table)
# ─────────────────────────────────────────────────────────────────────────────

def get_job_checkpoints() -> dict[str, dict]:
    """Read all job checkpoints from the database."""
    code = (
        "from investor_agent.database import execute_query; "
        "import json; "
        "rows = execute_query('SELECT job_name, last_run_at, last_status, "
        "last_duration_ms, consecutive_failures, last_error FROM job_checkpoints'); "
        "print(json.dumps([{k: str(v) if v is not None else None for k, v in r.items()} "
        "for r in rows], default=str))"
    )
    ok, output = docker_exec_python(code)
    if not ok:
        logger.error(f"Failed to read checkpoints: {output}")
        return {}

    try:
        rows = json.loads(output)
        return {r["job_name"]: r for r in rows}
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse checkpoints: {e}")
        return {}


def update_checkpoint(job_name: str, status: str, duration_ms: int, error: str | None = None):
    """Update a job checkpoint in the database."""
    error_escaped = error.replace("'", "''")[:450] if error else ""
    if status == "SUCCESS":
        code = (
            f"from investor_agent.database import execute_insert; "
            f"execute_insert(\""
            f"UPDATE job_checkpoints SET "
            f"last_run_at = GETDATE(), last_status = '{status}', "
            f"last_duration_ms = {duration_ms}, consecutive_failures = 0, "
            f"last_error = NULL, updated_at = GETDATE() "
            f"WHERE job_name = '{job_name}'"
            f"\")"
        )
    else:
        code = (
            f"from investor_agent.database import execute_insert; "
            f"execute_insert(\""
            f"UPDATE job_checkpoints SET "
            f"last_run_at = GETDATE(), last_status = '{status}', "
            f"last_duration_ms = {duration_ms}, "
            f"consecutive_failures = consecutive_failures + 1, "
            f"last_error = '{error_escaped}', updated_at = GETDATE() "
            f"WHERE job_name = '{job_name}'"
            f"\")"
        )
    ok, output = docker_exec_python(code)
    if not ok:
        logger.error(f"Failed to update checkpoint for {job_name}: {output}")


# ─────────────────────────────────────────────────────────────────────────────
# Job execution
# ─────────────────────────────────────────────────────────────────────────────

def run_job(job_name: str) -> bool:
    """Execute a single job and update its checkpoint."""
    job = JOBS.get(job_name)
    if not job:
        logger.error(f"Unknown job: {job_name}")
        return False

    logger.info(f"RUNNING: {job_name} — {job['description']}")

    # Mark as RUNNING
    update_checkpoint(job_name, "RUNNING", 0)

    start = time.time()
    if "host_python" in job:
        ok, output = host_exec_python(job["host_python"], timeout=600)
    else:
        ok, output = docker_exec_python(job["python"], timeout=600)
    duration_ms = int((time.time() - start) * 1000)

    if ok:
        logger.info(f"SUCCESS: {job_name} ({duration_ms}ms)")
        # Log first 500 chars of output
        if output:
            logger.info(f"  Result: {output[:500]}")
        update_checkpoint(job_name, "SUCCESS", duration_ms)
        return True
    else:
        logger.error(f"FAILED: {job_name} ({duration_ms}ms) — {output[:300]}")
        update_checkpoint(job_name, "FAILED", duration_ms, output[:450])
        return False


def is_job_due(job_name: str, checkpoints: dict) -> bool:
    """Check if a job is overdue based on its checkpoint and interval."""
    job = JOBS.get(job_name)
    if not job:
        return False

    checkpoint = checkpoints.get(job_name)
    if not checkpoint:
        return True  # Never ran

    last_status = checkpoint.get("last_status", "NEVER")
    if last_status == "NEVER":
        return True
    if last_status == "RUNNING":
        return False  # Don't double-run

    # Parse last_run_at
    last_run_str = checkpoint.get("last_run_at", "2000-01-01")
    try:
        # Handle various datetime formats from MSSQL
        last_run_str = last_run_str.split(".")[0]  # Strip microseconds
        last_run = datetime.strptime(last_run_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        try:
            last_run = datetime.strptime(last_run_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return True  # Can't parse → assume due

    interval = timedelta(hours=job["interval_hours"])
    return datetime.now() > last_run + interval


# ─────────────────────────────────────────────────────────────────────────────
# Startup catch-up
# ─────────────────────────────────────────────────────────────────────────────

def startup_catchup():
    """Run any overdue jobs on startup (handles server downtime)."""
    logger.info("=" * 60)
    logger.info("STARTUP CATCH-UP: Checking for overdue jobs...")
    logger.info("=" * 60)

    if not container_running():
        logger.error("Docker container not running — skipping catch-up")
        return

    checkpoints = get_job_checkpoints()
    if not checkpoints:
        logger.warning("No checkpoints found — running all jobs")
        for job_name in JOBS:
            run_job(job_name)
        return

    overdue = []
    for job_name in JOBS:
        if is_job_due(job_name, checkpoints):
            cp = checkpoints.get(job_name, {})
            logger.info(f"  OVERDUE: {job_name} (last: {cp.get('last_run_at', 'NEVER')}, "
                        f"status: {cp.get('last_status', 'NEVER')})")
            overdue.append(job_name)
        else:
            cp = checkpoints.get(job_name, {})
            logger.info(f"  OK: {job_name} (last: {cp.get('last_run_at', 'N/A')})")

    if not overdue:
        logger.info("All jobs are up to date — no catch-up needed")
        return

    logger.info(f"Running {len(overdue)} overdue jobs...")

    # Run daily jobs first, then weekly, then monthly
    priority = ["daily_outcomes", "weekly_calibration", "weekly_gate_effectiveness",
                 "weekly_efficiency_report", "monthly_stop_optimization"]
    for job_name in priority:
        if job_name in overdue:
            run_job(job_name)
            time.sleep(2)  # Brief pause between jobs


# ─────────────────────────────────────────────────────────────────────────────
# Main scheduler loop
# ─────────────────────────────────────────────────────────────────────────────

_running = True


def _signal_handler(signum, frame):
    global _running
    logger.info(f"Received signal {signum} — shutting down scheduler")
    _running = False


def scheduler_loop():
    """Main loop: check for due jobs every CHECK_INTERVAL_SECONDS."""
    global _running

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    logger.info("Scheduler loop started (checking every %ds)", CHECK_INTERVAL_SECONDS)

    while _running:
        try:
            if not container_running():
                logger.warning("Docker container not running — waiting...")
                time.sleep(CHECK_INTERVAL_SECONDS)
                continue

            checkpoints = get_job_checkpoints()
            for job_name in JOBS:
                if not _running:
                    break
                if is_job_due(job_name, checkpoints):
                    run_job(job_name)
                    time.sleep(2)

        except Exception as e:
            logger.error(f"Scheduler error: {e}")

        # Sleep in small increments so we can respond to signals
        for _ in range(CHECK_INTERVAL_SECONDS):
            if not _running:
                break
            time.sleep(1)

    logger.info("Scheduler stopped")


# ─────────────────────────────────────────────────────────────────────────────
# CLI commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_stop():
    """Stop the running scheduler daemon."""
    if not PID_FILE.exists():
        print("Scheduler not running (no PID file)")
        return

    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Stopped scheduler (PID {pid})")
    except ProcessLookupError:
        print(f"Scheduler not running (stale PID {pid})")
    PID_FILE.unlink(missing_ok=True)


def cmd_status():
    """Show job checkpoint status."""
    if not container_running():
        print("Docker container not running")
        return

    checkpoints = get_job_checkpoints()
    if not checkpoints:
        print("No checkpoint data available")
        return

    # Check if scheduler daemon is running
    scheduler_status = "NOT RUNNING"
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            scheduler_status = f"RUNNING (PID {pid})"
        except ProcessLookupError:
            scheduler_status = f"NOT RUNNING (stale PID {pid})"

    print(f"\nScheduler: {scheduler_status}")
    print(f"{'Job':<30} {'Last Run':<22} {'Status':<10} {'Duration':<10} {'Failures':<10} {'Due?':<5}")
    print("─" * 90)

    for job_name in JOBS:
        cp = checkpoints.get(job_name, {})
        last_run = cp.get("last_run_at", "NEVER")
        if last_run and len(last_run) > 19:
            last_run = last_run[:19]
        status = cp.get("last_status", "NEVER")
        duration = cp.get("last_duration_ms", "—")
        if duration and duration != "None" and duration != "—":
            duration = f"{int(duration)}ms"
        failures = cp.get("consecutive_failures", "0")
        due = "YES" if is_job_due(job_name, checkpoints) else "no"

        print(f"{job_name:<30} {str(last_run):<22} {str(status):<10} {str(duration):<10} {str(failures):<10} {due:<5}")

    print()


def cmd_run(job_name: str | None = None):
    """Run a specific job or all jobs immediately."""
    if not container_running():
        print("Docker container not running")
        return

    if job_name:
        if job_name not in JOBS:
            print(f"Unknown job: {job_name}")
            print(f"Available: {', '.join(JOBS.keys())}")
            return
        run_job(job_name)
    else:
        for name in JOBS:
            run_job(name)
            time.sleep(2)


def cmd_daemon():
    """Start scheduler as a background daemon."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"Scheduler already running (PID {pid})")
            return
        except ProcessLookupError:
            PID_FILE.unlink()

    # Fork to background
    pid = os.fork()
    if pid > 0:
        # Parent: wait for first child to exit, then read PID from file
        os.waitpid(pid, 0)
        time.sleep(0.3)  # Brief wait for grandchild to write PID file
        actual_pid = PID_FILE.read_text().strip() if PID_FILE.exists() else "?"
        print(f"Scheduler started (PID {actual_pid}, log: {LOG_FILE})")
        return

    # Child: fully detach from terminal
    os.setsid()

    # Double-fork to prevent zombie and fully detach from terminal
    if os.fork() > 0:
        os._exit(0)

    # Redirect all file descriptors to /dev/null
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)  # stdin
    os.dup2(devnull, 1)  # stdout
    os.dup2(devnull, 2)  # stderr
    os.close(devnull)

    # Remove console handler — only log to file in daemon mode
    logger.removeHandler(console_handler)

    # Write grandchild's actual PID
    PID_FILE.write_text(str(os.getpid()))

    startup_catchup()
    scheduler_loop()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--stop" in args:
        cmd_stop()
    elif "--status" in args:
        cmd_status()
    elif "--daemon" in args:
        cmd_daemon()
    elif "--run" in args:
        job = args[args.index("--run") + 1] if len(args) > args.index("--run") + 1 else None
        cmd_run(job)
    elif "--catchup" in args:
        startup_catchup()
    else:
        # Foreground mode
        print(f"Self-Improvement Scheduler (foreground, log: {LOG_FILE})")
        print("Press Ctrl+C to stop\n")
        startup_catchup()
        scheduler_loop()

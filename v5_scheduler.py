"""
NEXUS OS v5 — Evolution Scheduler
===================================
Schedules and runs evolution cycles automatically.
Uses Python stdlib subprocess + cron-style scheduling.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ─── Config ────────────────────────────────────────────────────────────────────

NEXUS_OS_PATH = Path.home() / "NEXUS_OS"
SCHEDULE_DB = Path.home() / ".hermes" / "nexus_v5_scheduler.json"
PID_FILE = Path.home() / ".hermes" / "nexus_v5_scheduler.pid"


# ─── Schedule Types ────────────────────────────────────────────────────────────

@dataclass
class ScheduledJob:
    id: str
    name: str
    schedule: str  # "hourly", "daily", "30m", "1h", "2h", or cron expression
    command: str
    enabled: bool = True
    last_run: float = 0
    next_run: float = 0
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_result: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        # Only serializable fields (exclude methods/computed)
        return {
            "id": self.id,
            "name": self.name,
            "schedule": self.schedule,
            "command": self.command,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_result": self.last_result,
            "created_at": self.created_at,
        }

    def next_run_relative(self) -> str:
        if self.next_run <= 0:
            return "not scheduled"
        delta = self.next_run - time.time()
        if delta <= 0:
            return "due now"
        if delta < 60:
            return f"in {int(delta)}s"
        if delta < 3600:
            return f"in {int(delta / 60)}m"
        if delta < 86400:
            return f"in {int(delta / 3600)}h"
        return f"in {int(delta / 86400)}d"


# ─── Schedule Parser ───────────────────────────────────────────────────────────

def parse_schedule(schedule: str) -> float:
    """
    Parse schedule string to next run timestamp.
    Returns Unix timestamp of next run.
    """
    schedule = schedule.strip().lower()

    # Cron format: "HH:MM"
    if ":" in schedule and not any(k in schedule for k in ["hourly", "daily", "m", "h", "d"]):
        try:
            hour, minute = schedule.split(":")
            now = datetime.now()
            next_dt = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
            if next_dt <= now:
                next_dt += timedelta(days=1)
            return next_dt.timestamp()
        except (ValueError, IndexError):
            pass

    # Interval format: "30m", "1h", "2h", "1d"
    interval_map = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    for unit, seconds in interval_map.items():
        if schedule.endswith(unit):
            try:
                value = int(schedule[:-1])
                return time.time() + (value * seconds)
            except ValueError:
                break

    # Keywords
    keyword_map = {
        "hourly": time.time() + 3600,
        "daily": time.time() + 86400,
        "weekly": time.time() + 604800,
        "monthly": time.time() + 2592000,
    }
    if schedule in keyword_map:
        return keyword_map[schedule]

    return 0


def format_schedule(schedule: str) -> str:
    """Human-readable schedule description."""
    s = schedule.strip().lower()
    if s == "hourly":
        return "Every hour"
    if s == "daily":
        return "Once a day"
    if s == "weekly":
        return "Once a week"
    if s.endswith("m"):
        return f"Every {s[:-1]} minutes"
    if s.endswith("h"):
        return f"Every {s[:-1]} hours"
    if s.endswith("d"):
        return f"Every {s[:-1]} days"
    return s


# ─── Scheduler ────────────────────────────────────────────────────────────────

class EvolutionScheduler:
    """
    Schedules and runs NEXUS OS evolution cycles.

    Features:
    - Cron-style scheduling (interval, hourly, daily, cron expr)
    - Runs evolution as subprocess
    - Tracks job history and results
    - Can run as daemon (background)
    - Non-blocking when running as subprocess
    - pid file for daemon management
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or SCHEDULE_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, ScheduledJob] = {}
        self._load()

        # Only init defaults if NO jobs loaded from JSON
        if not self.jobs:
            self._init_defaults()

    def _init_defaults(self):
        """Set up default evolution jobs."""
        defaults = [
            ScheduledJob(
                id="hourly_evolution",
                name="Hourly Evolution Cycle",
                schedule="1h",
                command="cd /Users/a/NEXUS_OS && python3 NEXUS_OS_v6.py evolve",
                enabled=True,
            ),
            ScheduledJob(
                id="daily_deep_evolution",
                name="Daily Deep Evolution",
                schedule="daily",
                command="cd /Users/a/NEXUS_OS && python3 NEXUS_OS_v6.py evolve --deep",
                enabled=True,
            ),
            ScheduledJob(
                id="health_check",
                name="System Health Check",
                schedule="30m",
                command="cd /Users/a/NEXUS_OS && python3 NEXUS_OS_v6.py status",
                enabled=True,
            ),
        ]
        for job in defaults:
            job.next_run = parse_schedule(job.schedule)
            self.jobs[job.id] = job
        self._save()

    # ─── Persistence ─────────────────────────────────────────────────────────

    def _load(self):
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text())
                self.jobs = {}
                for jid, jd in data.get("jobs", {}).items():
                    self.jobs[jid] = ScheduledJob(**jd)
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

    def _save(self):
        data = {"jobs": {jid: j.to_dict() for jid, j in self.jobs.items()},
                "saved_at": time.time()}
        self.db_path.write_text(json.dumps(data, indent=2))

    # ─── Job Management ───────────────────────────────────────────────────────

    def add_job(self, job: ScheduledJob) -> ScheduledJob:
        job.next_run = parse_schedule(job.schedule)
        self.jobs[job.id] = job
        self._save()
        return job

    def remove_job(self, job_id: str) -> bool:
        if job_id in self.jobs:
            del self.jobs[job_id]
            self._save()
            return True
        return False

    def enable_job(self, job_id: str) -> bool:
        if job_id in self.jobs:
            self.jobs[job_id].enabled = True
            self._save()
            return True
        return False

    def disable_job(self, job_id: str) -> bool:
        if job_id in self.jobs:
            self.jobs[job_id].enabled = False
            self._save()
            return True
        return False

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        return self.jobs.get(job_id)

    def list_jobs(self) -> List[ScheduledJob]:
        return sorted(self.jobs.values(), key=lambda j: j.next_run)

    def get_due_jobs(self) -> List[ScheduledJob]:
        """Get jobs that are due to run."""
        now = time.time()
        due = []
        for job in self.jobs.values():
            if job.enabled and job.next_run <= now:
                due.append(job)
        return sorted(due, key=lambda j: j.next_run)

    # ─── Execution ────────────────────────────────────────────────────────────

    def run_job(self, job: ScheduledJob,
                 workdir: Path = None,
                 timeout: int = 300) -> Dict[str, Any]:
        """
        Execute a single job.
        Returns dict with execution results.
        """
        now = time.time()
        job.last_run = now

        start = time.time()
        result = {
            "job_id": job.id,
            "name": job.name,
            "command": job.command,
            "started_at": datetime.fromtimestamp(start).isoformat(),
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "duration": 0,
            "success": False,
        }

        try:
            workdir = workdir or NEXUS_OS_PATH
            proc = subprocess.run(
                job.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(workdir),
                env={**os.environ, "NEXUS_SCHEDULED": "1"},
            )
            result["exit_code"] = proc.returncode
            result["stdout"] = proc.stdout[-5000:] if proc.stdout else ""
            result["stderr"] = proc.stderr[-2000:] if proc.stderr else ""
            result["success"] = proc.returncode == 0

            if result["success"]:
                job.success_count += 1
            else:
                job.failure_count += 1

        except subprocess.TimeoutExpired:
            result["stderr"] = f"Timeout after {timeout}s"
            result["success"] = False
            job.failure_count += 1
        except Exception as e:
            result["stderr"] = str(e)
            result["success"] = False
            job.failure_count += 1

        finally:
            result["duration"] = time.time() - start
            job.run_count += 1
            job.last_result = result["stdout"][:200] if result["stdout"] else result["stderr"][:200]
            job.next_run = parse_schedule(job.schedule)
            self._save()

        return result

    def run_due_jobs(self, workdir: Path = None,
                     timeout: int = 300,
                     max_jobs: int = 3) -> List[Dict[str, Any]]:
        """Run all due jobs. Returns list of results."""
        if isinstance(workdir, str):
            workdir = Path(workdir)
        due = self.get_due_jobs()[:max_jobs]
        results = []
        for job in due:
            result = self.run_job(job, workdir, timeout)
            results.append(result)
        return results

    # ─── Daemon Mode ─────────────────────────────────────────────────────────

    def is_running(self) -> bool:
        """Check if daemon is running."""
        if not PID_FILE.exists():
            return False
        try:
            pid = int(PID_FILE.read_text().strip())
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            PID_FILE.unlink(missing_ok=True)
            return False

    def start_daemon(self, workdir: Path = None, poll_interval: int = 30):
        """
        Start scheduler as background daemon using subprocess.
        Runs v5_scheduler_daemon.py as a background process.
        """
        daemon_script = NEXUS_OS_PATH / "v5_scheduler_daemon.py"
        workdir = workdir or NEXUS_OS_PATH

        # Write daemon runner script
        # Escape f-string braces with double {{}}
        script_content = f"""#!/usr/bin/env python3
import sys, time, os
from pathlib import Path
sys.path.insert(0, "{NEXUS_OS_PATH}")
os.chdir("{workdir}")
os.environ["NEXUS_SCHEDULED"] = "1"

LOG_FILE = Path.home() / ".hermes" / "nexus_scheduler.log"

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\\n")
        f.flush()
    print(msg, flush=True)

from v5_scheduler import EvolutionScheduler
sched = EvolutionScheduler()
poll = {poll_interval}

while True:
    results = sched.run_due_jobs(workdir="{workdir}", timeout=300, max_jobs=2)
    if results:
        log(f"[nexus-daemon] Ran {{len(results)}} jobs at {{time.strftime('%Y-%m-%d %H:%M')}}")
    time.sleep(poll)
"""
        daemon_script.write_text(script_content)

        # Start as background subprocess
        log_file = Path.home() / ".hermes" / "nexus_scheduler.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        proc = subprocess.Popen(
            [sys.executable, str(daemon_script)],
            stdout=open(log_file, "a"),
            stderr=subprocess.STDOUT,
            cwd=str(workdir),
            env={**os.environ, "NEXUS_SCHEDULED": "1"},
            start_new_session=True,  # Detach from parent on Unix
        )

        PID_FILE.write_text(str(proc.pid))
        return proc.pid

    def stop_daemon(self) -> bool:
        """Stop the scheduler daemon."""
        if not self.is_running():
            return False
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 15)  # SIGTERM
            time.sleep(1)
            PID_FILE.unlink(missing_ok=True)
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            PID_FILE.unlink(missing_ok=True)
            return False

    # ─── Status ───────────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        jobs = self.list_jobs()
        running = self.is_running()
        return {
            "daemon_running": running,
            "pid_file": str(PID_FILE) if running else None,
            "total_jobs": len(jobs),
            "enabled_jobs": sum(1 for j in jobs if j.enabled),
            "due_now": len(self.get_due_jobs()),
            "next_due": min((j.next_run for j in jobs if j.enabled and j.next_run > 0),
                           default=0),
            "jobs": [j.to_dict() for j in jobs],
        }


# ─── Cron Entry ───────────────────────────────────────────────────────────────

def install_cron_entry():
    """
    Install a cron entry to run the scheduler daemon.
    Uses crontab to run nexus_v5_scheduler.py every minute.
    """
    nexus_path = NEXUS_OS_PATH / "v5_scheduler_daemon.py"
    cron_line = f"* * * * * /usr/bin/python3 {nexus_path} --daemon >> ~/.hermes/nexus_scheduler.log 2>&1"

    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current = result.stdout or ""
    except Exception:
        current = ""

    if "nexus_v5_scheduler" not in current:
        new_crontab = current.strip() + "\n" + cron_line + "\n"
        proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True)
        return proc.returncode == 0
    return True


# ─── Daemon Entry Point ────────────────────────────────────────────────────────

def daemon_main():
    """Entry point for cron-started daemon."""
    import sys
    scheduler = EvolutionScheduler()

    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        # Poll-based daemon
        poll = 60
        while True:
            scheduler.run_due_jobs(timeout=300, max_jobs=2)
            time.sleep(poll)
    else:
        # Single run
        results = scheduler.run_due_jobs(timeout=300, max_jobs=3)
        print(json.dumps(results, indent=2, default=str))


# ─── Test ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== NEXUS Evolution Scheduler Test ===\n")

    sched = EvolutionScheduler()

    print(f"Daemon running: {sched.is_running()}")
    print(f"Status: {json.dumps(sched.status(), indent=2, default=str)[:500]}")

    print("\nDue jobs:", len(sched.get_due_jobs()))
    for j in sched.get_due_jobs():
        print(f"  {j.name} [{j.schedule}] — {j.next_run_relative()}")

    print("\nAll jobs:")
    for j in sched.list_jobs():
        print(f"  {j.name}: {format_schedule(j.schedule)}, "
              f"next: {j.next_run_relative()}, "
              f"runs: {j.run_count} ({j.success_count} ok, {j.failure_count} fail)")

    print("\n=== Scheduler test complete ===")

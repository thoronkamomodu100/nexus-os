#!/usr/bin/env python3
import sys, time, os
from pathlib import Path
sys.path.insert(0, "/Users/a/NEXUS_OS")
os.chdir("/Users/a/NEXUS_OS")
os.environ["NEXUS_SCHEDULED"] = "1"

LOG_FILE = Path.home() / ".hermes" / "nexus_scheduler.log"

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")
        f.flush()
    print(msg, flush=True)

from v5_scheduler import EvolutionScheduler
sched = EvolutionScheduler()
poll = 30

while True:
    results = sched.run_due_jobs(workdir="/Users/a/NEXUS_OS", timeout=300, max_jobs=2)
    if results:
        log(f"[nexus-daemon] Ran {len(results)} jobs at {time.strftime('%Y-%m-%d %H:%M')}")
    time.sleep(poll)

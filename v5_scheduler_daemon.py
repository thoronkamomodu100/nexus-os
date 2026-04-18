#!/usr/bin/env python3
import sys, time, os
sys.path.insert(0, "/Users/a/NEXUS_OS")
os.chdir("/Users/a/NEXUS_OS")
os.environ["NEXUS_SCHEDULED"] = "1"

from v5_scheduler import EvolutionScheduler
sched = EvolutionScheduler()
poll = 30

while True:
    results = sched.run_due_jobs(workdir="/Users/a/NEXUS_OS", timeout=300, max_jobs=2)
    if results:
        print(f"[nexus-daemon] Ran {len(results)} jobs at {time.strftime('%Y-%m-%d %H:%M')}", flush=True)
    time.sleep(poll)

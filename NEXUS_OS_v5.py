#!/usr/bin/env python3
"""
NEXUS OS v5 — Autonomous Operating System
==========================================
Combines all v5 modules:
- v5_persistence: SQLite-based persistent state
- v5_web_crawler: Real web search + crawl + summarize
- v5_git_evolution: Git-tracked evolution history
- v5_scheduler: Cron-based evolution scheduling

Plus connects to existing v3 components:
- Archive, KnowledgeGraph, Fleet, Healing, EvolutionLoop

Usage:
    python3 NEXUS_OS_v5.py status          # Full system dashboard
    python3 NEXUS_OS_v5.py evolve [--deep]  # Run evolution cycle
    python3 NEXUS_OS_v5.py research <query> # Web research
    python3 NEXUS_OS_v5.py schedule        # Scheduler status
    python3 NEXUS_OS_v5.py dashboard       # Web dashboard
    python3 NEXUS_OS_v5.py health          # System health check
    python3 NEXUS_OS_v5.py run-cycle       # Run one evolution cycle
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

# ─── Import v5 modules ─────────────────────────────────────────────────────────

# Add nexus OS path to sys.path
NEXUS_PATH = Path(__file__).parent.resolve()
sys.path.insert(0, str(NEXUS_PATH))

# Import v5 modules
from v5_persistence import (
    PersistentStore, PersistedTask, PersistedKnowledge,
    PersistedPattern, EvolutionLog, Metric, TaskStatus, Priority,
    get_store, NEXUS_V5_DB,
)
from v5_web_crawler import WebSearch, WebCrawler, ResearchPipeline, summarize_with_claude
from v5_git_evolution import GitEvolution, EvolutionCommit
from v5_scheduler import EvolutionScheduler, parse_schedule, format_schedule

# Import v3 core (if available)
try:
    from NEXUS_OS_v3 import (
        NEXUSCore, Archive, KnowledgeGraph, SelfHealing,
        MultiAgentFleet, SkillForge, AutonomousEvolutionLoop,
        AutonomousCodingAgent, NeuralMemoryGrid,
        AWESOME_SKILLS_DIR, AwesomeSkillLibrary,
    )
    HAS_V3 = True
except ImportError as e:
    print(f"Warning: NEXUS_OS_v3 not found: {e}", file=sys.stderr)
    HAS_V3 = False


# ─── Version ──────────────────────────────────────────────────────────────────

VERSION = "5.0.0"
BANNER = """
╔══════════════════════════════════════════════════════════════╗
║                    NEXUS OS v5.0.0                         ║
║          Autonomous Self-Evolving Operating System          ║
║                                                              ║
║  Components:                                                  ║
║  🧠 Knowledge Graph  │  📦 Archive  │  🔧 Self-Healing       ║
║  🚀 Fleet  │  🧬 Evolution  │  🌐 Web Crawler              ║
║  💾 SQLite Persistence  │  📊 Git Evolution  │  ⏰ Scheduler ║
╚══════════════════════════════════════════════════════════════╝
"""


# ─── NEXUS OS v5 Core ──────────────────────────────────────────────────────────

class NEXUS_OS_v5:
    """
    NEXUS OS v5 — Full autonomous operating system.

    Integrates v3 core systems with v5 infrastructure:
    - Persistent SQLite store (all state survives restarts)
    - Real web research (search + crawl + summarize)
    - Git-tracked evolution (commit history, rollback)
    - Scheduled evolution cycles (cron-based)
    - Metrics dashboard (track improvement over time)
    """

    def __init__(self):
        self.version = VERSION
        self.session_id = str(uuid.uuid4())[:8]
        self.started_at = time.time()
        self.nexus_path = NEXUS_PATH

        # ── v5 Systems ──────────────────────────────────────────────────────
        print("  Initializing v5 systems...")
        self.store = get_store()  # SQLite persistence
        self.scheduler = EvolutionScheduler()
        self.git = GitEvolution(self.nexus_path)
        self.researcher = ResearchPipeline()

        # Init git repo if needed
        if self.git.is_repo():
            print(f"  ✓ Git repo: {self.git.get_current_branch()}")
        else:
            self.git.init()
            self.git._run("add", ".")
            self.git._run("commit", "-m", "🎉 NEXUS OS v5 initialized")
            print("  ✓ Git repo initialized")

        # ── v3 Core (if available) ─────────────────────────────────────────
        self.v3: Optional[NEXUSCore] = None
        if HAS_V3:
            print("  Loading v3 core...")
            try:
                self.v3 = NEXUSCore()
                print(f"  ✓ v3 loaded: {len(self.v3.knowledge._nodes)} knowledge nodes")
            except Exception as e:
                print(f"  ⚠ v3 load failed: {e}")

        # ── Migrate v3 state to v5 if needed ───────────────────────────────
        self._migrate_v3_to_v5()

        # ── Metrics ────────────────────────────────────────────────────────
        self._record_metric("session_started", 1.0)

        print(f"\n  NEXUS OS v5.0.0 ready! Session: {self.session_id}\n")

    def _migrate_v3_to_v5(self):
        """Migrate v3 in-memory state to v5 SQLite if not already done."""
        if not HAS_V3 or not self.v3:
            return

        migrated = self.store.get_meta("v3_migrated")
        if migrated:
            return

        print("  Migrating v3 state to v5 SQLite...")

        # Migrate knowledge nodes
        for node_id, node_data in self.v3.knowledge._nodes.items():
            kn = PersistedKnowledge(
                id=node_id,
                title=node_data.get("title", ""),
                content=node_data.get("content", ""),
                tags=node_data.get("tags", []),
                source=node_data.get("source", ""),
                importance=node_data.get("importance", 0.5),
                created_at=node_data.get("created_at", time.time()),
            )
            self.store.add_knowledge(kn)

        # Migrate archive patterns
        patterns = self.v3.archive.get_patterns()
        for pdata in patterns.get("recent", []):
            p = PersistedPattern(
                id=str(uuid.uuid4())[:8],
                type=pdata.get("type", "success"),
                task_name=pdata.get("task_name", ""),
                approach=pdata.get("approach", ""),
                details=str(pdata.get("details", "")),
            )
            self.store.add_pattern(p)

        self.store.set_meta("v3_migrated", "true")
        print(f"  ✓ Migrated {len(self.v3.knowledge._nodes)} knowledge nodes")

    # ─── Metrics ──────────────────────────────────────────────────────────────

    def _record_metric(self, name: str, value: float, delta: float = 0):
        """Record a metric to SQLite."""
        m = Metric(
            id=str(uuid.uuid4())[:8],
            name=name,
            value=value,
            delta=delta,
        )
        self.store.record_metric(m)

    def _get_score(self) -> float:
        """Calculate current system score from metrics."""
        archive = self.store.get_archive_stats()
        ev_trend = self.store.get_evolution_trend(limit=10)
        state = self.store.get_full_state()

        score = 0.0
        score += archive.get("rate", 0.0) * 30  # 30% weight: success rate
        if ev_trend:
            score += (sum(ev_trend) / len(ev_trend)) * 30  # 30% weight: evolution score
        score += min(state["knowledge_nodes"] / 100, 1.0) * 20  # 20% weight: knowledge
        score += min(state["pending_tasks"] / 10, 1.0) * 20  # 20% weight: activity

        return min(score, 100.0)

    # ─── Research ─────────────────────────────────────────────────────────────

    def research(self, query: str, depth: str = "quick") -> Dict:
        """
        Fast research pipeline: search → extract → store.
        Uses DuckDuckGo snippets directly (no slow per-page Claude summarization).
        Returns structured research results in < 20 seconds.
        """
        print(f"\n  🌐 Researching: {query}")
        print(f"     Depth: {depth}")

        num = 10 if depth == "deep" else 5

        # Fast: just search and use snippets
        search_results = self.researcher.search.search(query, num_results=num)

        # Extract insights from snippets
        all_insights = []
        for sr in search_results:
            snippet = sr.snippet.strip()
            if snippet and len(snippet) > 20:
                all_insights.append(snippet[:300])

        # Also do quick crawl for top 2 results (fast, no Claude summarization)
        pages_crawled = 0
        for sr in search_results[:2]:
            try:
                cr = self.researcher.crawler.fetch(sr.url)
                if cr.status == 200 and cr.content:
                    # Extract first 500 chars of content as insight
                    content_preview = cr.content[:500].strip()
                    if content_preview:
                        all_insights.append(f"[{sr.title}] {content_preview}")
                    pages_crawled += 1
            except Exception:
                pass

        # Store insights
        stored = 0
        for insight in all_insights[:10]:
            kn = PersistedKnowledge(
                id=str(uuid.uuid4())[:8],
                title=f"Research: {query}",
                content=insight,
                tags=["research", query.split()[0].lower() if query.split() else "ai", depth],
                source="web_research",
                importance=0.7,
            )
            self.store.add_knowledge(kn)
            stored += 1

        # Record metric
        self._record_metric("research_completed", 1.0)

        return {
            "query": query,
            "search_results": [
                {"title": r.title, "url": r.url, "snippet": r.snippet}
                for r in search_results[:5]
            ],
            "pages_crawled": pages_crawled,
            "insights": all_insights[:10],
            "combined_summary": f"Research on '{query}': {len(search_results)} sources found, {stored} insights stored.",
            "stats": {"queries": 1, "pages_crawled": pages_crawled},
        }

    # ─── Evolution Cycle ───────────────────────────────────────────────────────

    def run_evolution_cycle(self, deep: bool = False) -> Dict:
        """
        Run one complete evolution cycle using v5 systems.

        Steps:
        1. Get current score
        2. Run v3 evolution (CRAWL_AND_LEARN, EVOLVE_SKILL, UPGRADE_CODE)
        3. Calculate new score
        4. Log to SQLite
        5. Commit to git if improvements
        6. Record metrics
        """
        cycle_num = self.store.increment_cycle()
        score_before = self._get_score()

        print(f"\n  🧬 Evolution Cycle #{cycle_num}")
        print(f"     Score before: {score_before:.2f}")

        # ── Step 1: Research (v5 web crawler) ──────────────────────────────
        print("     [1/4] Web research...")
        if HAS_V3 and self.v3:
            # Get topic from knowledge gaps
            gaps = []
            for topic, tags in [
                ("self-improving AI agent", ["autonomous", "self-evolution"]),
                ("Claude Code integration", ["claude", "claude-code"]),
                ("multi-agent orchestration", ["fleet", "multi-agent"]),
            ]:
                existing = self.store.search_knowledge(topic, limit=1)
                if not existing:
                    gaps.append(topic)
            if gaps:
                topic = gaps[0]
            else:
                topic = "autonomous AI agent patterns 2026"
        else:
            topic = "autonomous AI agent patterns 2026"

        research_result = self.researcher.research(topic, depth="deep" if deep else "quick")

        # ── Step 2: Evolve skills (v3 evolution loop) ──────────────────────
        print("     [2/4] Evolving skills...")
        evolve_result = {}
        if HAS_V3 and self.v3 and self.v3.loop:
            try:
                evo_types = ["CRAWL_AND_LEARN", "EVOLVE_SKILL", "UPGRADE_CODE"]
                evo_type = random.choice(evo_types)
                evolve_result = self.v3.loop.force_type(evo_type)
                print(f"     → {evo_type}: {evolve_result.get('topic', evolve_result.get('target', 'done'))}")
            except Exception as e:
                print(f"     ⚠ Evolution error: {e}")
                evolve_result = {"error": str(e)}

        # ── Step 3: Claude Code file modification (async — runs in background)
        # This is non-blocking; result is captured if/when complete
        print("     [3/4] Claude Code file modification (background)...")
        upgrade_result = {}
        if HAS_V3 and self.v3:
            import threading, queue
            result_queue: queue.Queue = queue.Queue()
            nexus_file = self.nexus_path / "NEXUS_OS_v3.py"

            def _async_modify():
                try:
                    if nexus_file.exists():
                        r = self.v3.claude_modify_file(
                            str(nexus_file),
                            focus_areas=["error_handling", "code_quality"],
                        )
                        result_queue.put(r)
                    else:
                        result_queue.put({"modified": False, "error": "file not found"})
                except Exception as e:
                    result_queue.put({"modified": False, "error": str(e)})

            t = threading.Thread(target=_async_modify, daemon=True)
            t.start()
            t.join(timeout=60)  # Wait max 60s, then proceed regardless
            if not result_queue.empty():
                upgrade_result = result_queue.get_nowait()
                modified = upgrade_result.get("modified", False)
                print(f"     → File {'modified ✓' if modified else 'analyzed'}")
            else:
                print("     → File modification pending (background)")
                upgrade_result = {"modified": False, "status": "pending"}

        # ── Step 4: Calculate score, log, commit ───────────────────────────
        score_after = self._get_score()
        delta = score_after - score_before

        print(f"     [4/4] Score: {score_before:.2f} → {score_after:.2f} ({delta:+.2f})")

        # Log to SQLite
        ev_entry = EvolutionLog(
            id=str(uuid.uuid4())[:8],
            cycle=cycle_num,
            type=evolve_result.get("type", "unknown"),
            target=evolve_result.get("target", evolve_result.get("topic", "")),
            improvements=str(evolve_result)[:500],
            score_before=score_before,
            score_after=score_after,
        )
        self.store.log_evolution(ev_entry)

        # Record metrics
        self._record_metric("evolution_score", score_after, delta=delta)
        self._record_metric("evolution_cycle", float(cycle_num))

        # Git commit if meaningful change
        if delta > 0 and upgrade_result.get("modified"):
            try:
                files = [str(self.nexus_path / "NEXUS_OS_v3.py")]
                commit = self.git.commit_evolution(
                    cycle=cycle_num,
                    evo_type=evolve_result.get("type", "unknown"),
                    target=evolve_result.get("target", ""),
                    score_before=score_before,
                    score_after=score_after,
                    files=files,
                )
                print(f"     ✓ Git commit: {commit.commit_hash[:8]}")
            except Exception as e:
                print(f"     ⚠ Git commit failed: {e}")

        return {
            "cycle": cycle_num,
            "score_before": score_before,
            "score_after": score_after,
            "delta": delta,
            "research": {
                "topic": topic,
                "pages_crawled": research_result.get("stats", {}).get("pages_crawled", 0),
                "insights": len(research_result.get("insights", [])),
            },
            "evolution": evolve_result,
            "upgrade": {k: v for k, v in upgrade_result.items()
                       if k in ("modified", "lines_changed", "syntax_valid", "error")},
        }

    # ─── Health Check ────────────────────────────────────────────────────────

    def health_check(self) -> Dict:
        """Run comprehensive system health check."""
        print("\n  🔍 System Health Check...")

        health = {
            "timestamp": datetime.now().isoformat(),
            "session": self.session_id,
            "uptime_seconds": time.time() - self.started_at,
            "systems": {},
            "overall": "healthy",
        }

        # Check v5 systems
        health["systems"]["persistence"] = {
            "status": "ok" if self.store else "error",
            "db_path": str(NEXUS_V5_DB),
            "db_exists": NEXUS_V5_DB.exists(),
        }

        health["systems"]["scheduler"] = {
            "status": "running" if self.scheduler.is_running() else "stopped",
            "due_jobs": len(self.scheduler.get_due_jobs()),
        }

        health["systems"]["git"] = {
            "status": "ok" if self.git.is_repo() else "not_initialized",
            "branch": self.git.get_current_branch() if self.git.is_repo() else "none",
            "pending_changes": len(self.git.get_status()),
        }

        if HAS_V3 and self.v3:
            health["systems"]["v3_core"] = {
                "status": "ok",
                "knowledge_nodes": len(self.v3.knowledge._nodes),
                "archive_patterns": self.store.get_archive_stats()["total"],
            }
        else:
            health["systems"]["v3_core"] = {"status": "v3_not_available"}

        # Check store
        try:
            state = self.store.get_full_state()
            health["systems"]["database"] = {
                "status": "ok",
                "knowledge_nodes": state["knowledge_nodes"],
                "evolution_cycles": state["cycle"],
                "pending_tasks": state["pending_tasks"],
            }
        except Exception as e:
            health["systems"]["database"] = {"status": "error", "error": str(e)}
            health["overall"] = "degraded"

        # Determine overall health
        critical = [s for s in health["systems"].values() if s.get("status") == "error"]
        if critical:
            health["overall"] = "unhealthy"
        elif len(health["systems"]) - len(critical) < len(health["systems"]) / 2:
            health["overall"] = "degraded"

        return health

    # ─── Dashboard ───────────────────────────────────────────────────────────

    def dashboard(self) -> str:
        """Generate full system dashboard."""
        state = self.store.get_full_state()
        git_stats = self.git.get_evolution_stats() if self.git.is_repo() else {}
        sched_status = self.scheduler.status()
        ev_trend = self.store.get_evolution_trend(limit=20)

        archive = self.store.get_archive_stats()
        uptime = time.time() - self.started_at

        # Build dashboard
        lines = []
        lines.append(BANNER)
        lines.append(f"\nSession: {self.session_id} | Uptime: {int(uptime/60)}m | Cycle: {state['cycle']}\n")

        # Archive
        ar = archive
        rate = ar.get("rate", 0) * 100
        lines.append(f"📦 Archive: {ar['total']} patterns | Success: {rate:.1f}%\n")

        # Evolution trend (ASCII chart)
        if ev_trend:
            lines.append("🧬 Evolution Trend (last 20 cycles):")
            min_v, max_v = min(ev_trend), max(ev_trend)
            rng = max_v - min_v if max_v > min_v else 1
            for i, v in enumerate(ev_trend[-20:]):
                bar_len = int((v - min_v) / rng * 30) if rng > 0 else 15
                bar = "█" * bar_len + "░" * (30 - bar_len)
                lines.append(f"  [{i+1:02d}] {bar} {v:.1f}")
            lines.append("")

        # Git stats
        if git_stats:
            lines.append(f"📊 Git Evolution:")
            lines.append(f"  Total cycles: {git_stats.get('total_cycles', 0)}")
            lines.append(f"  Avg delta: {git_stats.get('avg_delta_per_cycle', 0):+.3f}")
            lines.append(f"  Positive: {git_stats.get('positive_cycles', 0)} | "
                        f"Negative: {git_stats.get('negative_cycles', 0)}\n")

        # Scheduler
        lines.append(f"⏰ Scheduler: "
                    f"{'running' if sched_status['daemon_running'] else 'stopped'} | "
                    f"{sched_status['enabled_jobs']} jobs | "
                    f"{sched_status['due_now']} due now\n")

        # Recent evolution
        ev_history = self.store.get_evolution_history(limit=5)
        if ev_history:
            lines.append("🧬 Recent Evolution:")
            for e in ev_history[:5]:
                dt = datetime.fromtimestamp(e.timestamp).strftime("%m-%d %H:%M")
                lines.append(f"  [{e.cycle:03d}] {e.type:20s} {e.target:30s} "
                           f"{e.score_after:5.1f} ({e.delta:+.2f}) {dt}")
            lines.append("")

        # Recent metrics
        metrics = self.store.get_metrics(limit=5)
        if metrics:
            lines.append("📈 Recent Metrics:")
            for m in metrics[:5]:
                dt = datetime.fromtimestamp(m.timestamp).strftime("%H:%M")
                lines.append(f"  {m.name}: {m.value:.3f} ({m.delta:+.3f}) @ {dt}")
            lines.append("")

        # Knowledge gaps
        lines.append("🧠 Knowledge Gaps:")
        all_kn = self.store.get_all_knowledge(limit=100)
        topics = set()
        for kn in all_kn:
            topics.update(kn.tags)
        lines.append(f"  Total topics: {len(topics)}")
        lines.append(f"  Knowledge nodes: {len(all_kn)}")

        return "\n".join(lines)

    # ─── CLI ──────────────────────────────────────────────────────────────────

    def run_cli(self, argv: list = None):
        """Run CLI parser and execute command."""
        import argparse

        parser = argparse.ArgumentParser(
            prog="NEXUS_OS_v5",
            description="NEXUS OS v5 — Autonomous Self-Evolving Operating System",
        )
        parser.add_argument("--version", action="version", version=f"NEXUS OS v{VERSION}")
        sub = parser.add_subparsers(dest="command", required=True)

        # Status
        sub.add_parser("status", help="Full system status")

        # Evolve
        evolve = sub.add_parser("evolve", help="Run evolution cycle")
        evolve.add_argument("--deep", action="store_true", help="Deep research mode")

        # Research
        research = sub.add_parser("research", help="Web research on a topic")
        research.add_argument("query", help="Research query")
        research.add_argument("--deep", action="store_true", help="Deep research")

        # Schedule
        sub.add_parser("schedule", help="Show scheduler status")
        sched_start = sub.add_parser("schedule-start", help="Start scheduler daemon")
        sched_stop = sub.add_parser("schedule-stop", help="Stop scheduler daemon")

        # Dashboard
        sub.add_parser("dashboard", help="Full system dashboard")

        # Health
        sub.add_parser("health", help="System health check")

        # Run cycle
        sub.add_parser("run-cycle", help="Run one evolution cycle")

        # Stats
        sub.add_parser("stats", help="Evolution statistics")

        # Tasks
        task_list = sub.add_parser("tasks", help="List tasks")
        task_list.add_argument("--status", default=None, help="Filter by status")
        task_create = sub.add_parser("task-create", help="Create a task")
        task_create.add_argument("name", help="Task name")
        task_create.add_argument("--desc", default="", help="Description")
        task_create.add_argument("--priority", type=int, default=2, help="Priority 1-4")

        args = parser.parse_args(argv)

        if args.command == "status":
            state = self.store.get_full_state()
            print(json.dumps(state, indent=2, default=str))

        elif args.command == "evolve":
            result = self.run_evolution_cycle(deep=args.deep)
            print(f"\n🧬 Evolution Cycle #{result['cycle']} Complete")
            print(f"   Score: {result['score_before']:.2f} → {result['score_after']:.2f} "
                  f"({result['delta']:+.2f})")
            if result.get("research", {}).get("pages_crawled"):
                print(f"   Research: {result['research']['pages_crawled']} pages, "
                      f"{result['research']['insights']} insights")
            if result.get("upgrade", {}).get("modified"):
                print(f"   Upgrade: File modified ✓")
            print(f"\n   Full result: {json.dumps(result, indent=2, default=str)}")

        elif args.command == "research":
            result = self.research(args.query, depth="deep" if args.deep else "quick")
            print(f"\n🌐 Research: {args.query}")
            print(f"   Pages crawled: {result['stats']['pages_crawled']}")
            print(f"   Insights: {len(result['insights'])}")
            print(f"\n   Summary: {result.get('combined_summary', 'N/A')[:300]}")
            print(f"\n   Key points:")
            for i, insight in enumerate(result.get('insights', [])[:5], 1):
                print(f"   {i}. {insight[:200]}")

        elif args.command == "schedule":
            status = self.scheduler.status()
            print(f"\n⏰ NEXUS Scheduler v5")
            print(f"   Daemon: {'running' if status['daemon_running'] else 'stopped'}")
            print(f"   Jobs: {status['total_jobs']} total, "
                  f"{status['enabled_jobs']} enabled, "
                  f"{status['due_now']} due")
            for j in status["jobs"]:
                print(f"\n   📋 {j['name']}")
                print(f"      Schedule: {format_schedule(j['schedule'])}")
                print(f"      Next: {j['next_run_relative']}")
                print(f"      Runs: {j['run_count']} ({j['success_count']}✓ {j['failure_count']}✗)")

        elif args.command == "schedule-start":
            if self.scheduler.is_running():
                print("Scheduler already running.")
            else:
                pid = self.scheduler.start_daemon()
                print(f"Scheduler started as daemon (PID: {pid})")

        elif args.command == "schedule-stop":
            if self.scheduler.stop_daemon():
                print("Scheduler stopped.")
            else:
                print("Scheduler not running.")

        elif args.command == "dashboard":
            print(self.dashboard())

        elif args.command == "health":
            h = self.health_check()
            print(f"\n🔍 Health: {h['overall'].upper()}")
            print(f"   Session: {h['session']}")
            print(f"   Uptime: {int(h['uptime_seconds']/60)}m")
            for name, sys_info in h["systems"].items():
                status = sys_info.get("status", "unknown")
                icon = "✓" if status == "ok" else "⚠" if status in ("degraded", "running") else "✗"
                print(f"   {icon} {name}: {status}")
            if h["overall"] != "healthy":
                print(f"\n⚠ Overall: {h['overall']}")

        elif args.command == "run-cycle":
            result = self.run_evolution_cycle()
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "stats":
            stats = self.git.get_evolution_stats()
            print(json.dumps(stats, indent=2, default=str))

        elif args.command == "tasks":
            tasks = self.store.list_tasks(status=args.status)
            print(f"\n📋 Tasks ({len(tasks)}):")
            for t in tasks:
                print(f"  [{t.status:10s}] {t.name} (priority={t.priority})")

        elif args.command == "task-create":
            task = PersistedTask(
                id=str(uuid.uuid4())[:8],
                name=args.name,
                description=args.desc,
                priority=args.priority,
            )
            self.store.create_task(task)
            print(f"Task created: {task.id} — {task.name}")

        else:
            parser.print_help()


# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Import random here since it's used in run_evolution_cycle
    import random

    nexus = NEXUS_OS_v5()
    nexus.run_cli(sys.argv[1:])

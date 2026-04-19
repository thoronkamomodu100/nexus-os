#!/usr/bin/env python3
"""
Daily Standup — 매일 아침 Telegram으로 실제工作报告

무엇이 실제 작동하는지, 무엇이 고장났는지, 무엇이 바꿨는지.
가짜 metric 없이. 진짜 데이터만.

실행: python3 daily_standup.py
 Cron: 0 9 * * * cd ~/NEXUS_OS && python3 daily_standup.py
"""
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

NEXUS_OS_PATH = Path("/Users/a/NEXUS_OS")
HERMES_HOME = Path.home() / ".hermes"
TELEGRAM_APPROVED = HERMES_HOME / "config" / "telegram-approved.json"


def get_git_daily() -> list[dict]:
    """어제 이후 git commits 전부 가져오기."""
    try:
        since = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--format=%h|%ad|%s|%an", "--date=iso"],
            cwd=NEXUS_OS_PATH, capture_output=True, text=True, timeout=10,
        )
        commits = []
        for line in result.stdout.strip().split("\n"):
            if "|" in line:
                parts = line.split("|")
                if len(parts) == 4:
                    commits.append({
                        "hash": parts[0],
                        "date": parts[1][:16],
                        "subject": parts[2],
                        "author": parts[3],
                    })
        return commits
    except Exception as e:
        return [{"error": str(e)}]


def get_git_diff_summary(commit_hash: str) -> str:
    """Commit의 핵심 diff 내용만 요약."""
    try:
        result = subprocess.run(
            ["git", "diff", f"{commit_hash}^..{commit_hash}", "--stat"],
            cwd=NEXUS_OS_PATH, capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_evolution_stats() -> dict:
    """Evolution log 실제 통계."""
    try:
        db_path = HERMES_HOME / "nexus_v5.db"
        if not db_path.exists():
            return {"error": "DB not found"}

        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        #昨日のcycles
        since = time.time() - 86400
        c.execute("SELECT COUNT(*), MAX(cycle) FROM evolution_log WHERE timestamp > ?", (since,))
        row = c.fetchone()

        #種類別count（昨日のみ）
        c.execute(
            "SELECT type, COUNT(*) FROM evolution_log WHERE timestamp > ? GROUP BY type",
            (since,),
        )
        types = dict(c.fetchall())

        #直近のcycle
        c.execute("SELECT cycle, type, target, score_after FROM evolution_log ORDER BY rowid DESC LIMIT 1")
        last = c.fetchone()

        conn.close()

        return {
            "cycles_today": row[0] or 0,
            "max_cycle": row[1] or 0,
            "types": types,
            "last_type": last[1] if last else None,
            "last_target": last[2] if last else None,
            "last_score": last[3] if last else None,
        }
    except Exception as e:
        return {"error": str(e)}


def get_cron_failures() -> list[dict]:
    """昨日のcron失敗 내역."""
    failures = []
    cron_out = HERMES_HOME / "cron" / "output"
    if not cron_out.exists():
        return []

    since = time.time() - 86400
    for d in cron_out.iterdir():
        if not d.is_dir():
            continue
        mtime = d.stat().st_mtime
        if mtime < since:
            continue
        # Check for error indicators
        try:
            for f in d.iterdir():
                content = f.read_text(errors="ignore")[:500] if f.is_file() else ""
                if any(kw in content.lower() for kw in ["error", "failed", "exception", "traceback"]):
                    failures.append({
                        "session": d.name,
                        "file": f.name,
                        "preview": content[:100],
                    })
        except Exception:
            pass
    return failures[:5]  # Max 5


def get_scheduler_status() -> dict:
    """Scheduler daemon 실제 상태."""
    try:
        pid_file = HERMES_HOME / "nexus_v5_scheduler.pid"
        if not pid_file.exists():
            return {"running": False, "reason": "PID file not found"}

        pid = int(pid_file.read_text().strip())
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "pid,state,etime"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return {"running": True, "pid": pid, "uptime_line": result.stdout.strip()}
            else:
                return {"running": False, "reason": f"Process {pid} not running"}
        except Exception:
            return {"running": False, "reason": "ps command failed"}
    except Exception as e:
        return {"running": False, "reason": str(e)}


def send_telegram(text: str) -> bool:
    """Telegram으로 메시지 전송 via curl with URL encoding."""
    import subprocess, json, urllib.parse

    BOT_TOKEN = "8766665851:AAFmF0Dji4F1zojrGNYZ833bWF94l1wwQCE"
    CHAT_ID = "7124576642"

    # URL-encode the text for safe transmission
    encoded_text = urllib.parse.urlencode({'text': text})[5:]  # strip 'text=' prefix

    cmd = [
        'curl', '-s', '-X', 'POST',
        f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
        '-d', f'chat_id={CHAT_ID}',
        '-d', f'text={encoded_text}',
        '-d', 'parse_mode=Markdown',
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        data = json.loads(result.stdout)
        return data.get('ok', False)
    except Exception as e:
        print(f"[Telegram error: {e}]")
        return False


def build_report() -> str:
    """하루工作报告 생성. 진짜 데이터만."""
    lines = []
    lines.append(f"🌅 *Daily Standup — {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

    # ── Git Commits ────────────────────────────────────────
    commits = get_git_daily()
    if commits and "error" not in commits[0]:
        lines.append(f"📝 *Git Commits (어제 이후):* {len(commits)}개")
        for c in commits[:8]:  # Max 8
            diff = get_git_diff_summary(c["hash"])
            files = ""
            if diff:
                # Extract just the file count / additions / deletions
                stats = [l for l in diff.split("\n") if "/" in l or "file" in l.lower()]
                if stats:
                    files = f" `{stats[0].strip()}`"
            lines.append(f"  • `{c['hash']}` {c['subject'][:60]}{files}")
    else:
        lines.append("📝 *Git Commits:* 없음 (어제 이후)")

    lines.append("")

    # ── Evolution Stats ─────────────────────────────────────
    evo = get_evolution_stats()
    if "error" not in evo:
        lines.append(f"🔄 *Evolution:* {evo.get('cycles_today', 0)} cycle(s) 오늘")
        if evo.get("types"):
            type_str = ", ".join(f"{k}:{v}" for k, v in evo["types"].items())
            lines.append(f"   종류: {type_str}")
        if evo.get("last_type"):
            lines.append(f"   최근: {evo['last_type']} → {evo.get('last_target', 'N/A')}")
    else:
        lines.append(f"🔄 *Evolution:* 확인 불가 ({evo.get('error', '')})")

    lines.append("")

    # ── Scheduler ──────────────────────────────────────────
    sched = get_scheduler_status()
    if sched.get("running"):
        lines.append(f"✅ *Scheduler:* 실행중 (PID {sched['pid']})")
    else:
        lines.append(f"❌ *Scheduler:*停止 — {sched.get('reason', 'unknown')}")

    lines.append("")

    # ── Cron Failures ──────────────────────────────────────
    failures = get_cron_failures()
    if failures:
        lines.append(f"⚠️ *Cron Errors:* {len(failures)}개 발견")
        for f in failures[:3]:
            lines.append(f"  • `{f['session']}` — {f['preview'][:60]}")
    else:
        lines.append("✅ *Cron Errors:* 없음")

    lines.append("")
    lines.append("---")
    lines.append(f"_Generated: {datetime.now().strftime('%H:%M:%S')}_")

    return "\n".join(lines)


def main():
    report = build_report()
    print(report)
    sent = send_telegram(report)
    print(f"\nTelegram: {'✅Sent' if sent else '❌Failed/Printed'}")


if __name__ == "__main__":
    main()

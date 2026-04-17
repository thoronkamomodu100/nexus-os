# NEXUS OS — Autonomous AI Operating System

<div align="center">

![NEXUS](https://img.shields.io/badge/NEXUS-OS-v3.0.0-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10+-green?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)
![Tests](https://img.shields.io/badge/Tests-11%2F11%20%F0%9F%9A%80-brightgreen?style=for-the-badge)

**"The system that improves itself."**

*Autonomous AI operating system with HyperAgents 3-Layer architecture, self-healing, and continuous evolution.*

[Features](#features) • [Quick Start](#quick-start) • [Architecture](#architecture) • [Documentation](#documentation) • [Contributing](#contributing)

</div>

**Self-Evolving • Self-Healing • Self-Aware • Claude Code Powered**

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Claude Code Integration** | Real AI-powered code generation — any language, any framework |
| **Smart Routing** | Templates for common patterns (instant), Claude Code for complex tasks (powerful) |
| **HyperAgents 3-Layer** | Task → Meta → Meta-Meta improvement architecture |
| **Stepping Stones Archive** | Every success/failure stored as reusable experience |
| **Bias Detection** | Auto-detect 80%+ approach collapse, force alternatives |
| **Self-Healing** | Auto-diagnosis and recovery for 12+ error types |
| **Multi-Agent Fleet** | 6 specialized agents for parallel orchestration |
| **Skill Forge** | Dynamic skill creation from usage patterns |
| **Neural Memory Grid** | 3-tier memory (hot/warm/cold) with fluid forgetting |
| **Twenty CRM** | Full task & activity sync with Twenty CRM |
| **Autonomous Coding** | Natural language → working code |
| **Auto-Evolution** | Event-driven self-improvement cycles |

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/nexus-os/nexus.git
cd nexus
pip install -e .   # or: pip install .
```

Or run directly:

```bash
python NEXUS_OS_v3.py --help
```

### First Run

```bash
# View full status
python NEXUS_OS_v3.py status

# Run test suite
python NEXUS_OS_v3.py test

# Generate code from description
python NEXUS_OS_v3.py code --desc "web scraper for news headlines"

# Trigger evolution cycle
python NEXUS_OS_v3.py evolve

# Search knowledge base
python NEXUS_OS_v3.py knowledge --query "bias detection"

# Show fleet status
python NEXUS_OS_v3.py fleet
```

---

## 🏗️ Architecture

```
NEXUS OS — 8-Layer Autonomous AI Operating System
═══════════════════════════════════════════════════════

Layer 1: ════════════════════════════════════════════════
        Twenty CRM Client
        Full API integration — tasks, activities, pipeline
        Modes: live (real API) or mock (development)
───────────────────────────────────────────────────────

Layer 2: ════════════════════════════════════════════════
        Autonomous Coding Agent
        Natural language → working code → execution
        Templates: REST API, web scraper, CLI tool, data processor
───────────────────────────────────────────────────────

Layer 3: ════════════════════════════════════════════════
        Archive (Stepping Stones)
        Every action archived — success/failure with lessons
        Pattern detection, root cause analysis, approach routing
───────────────────────────────────────────────────────

Layer 4: ════════════════════════════════════════════════
        Knowledge Graph
        Connected nodes with cross-references
        Search, link, traverse, priority-based retrieval
───────────────────────────────────────────────────────

Layer 5: ════════════════════════════════════════════════
        Skill Forge
        Dynamic skill creation, evolution, lifecycle
        Usage tracking, success rate, auto-improvement
───────────────────────────────────────────────────────

Layer 6: ════════════════════════════════════════════════
        Multi-Agent Fleet
        6 agents: Code, Research, Builder, Debug, Plan, Evolve
        Capability-based routing, parallel execution
───────────────────────────────────────────────────────

Layer 7: ════════════════════════════════════════════════
        Self-Healing Engine
        12 error types auto-diagnosed
        Recovery strategies: auto-fix, suggest, config
───────────────────────────────────────────────────────

Layer 8: ════════════════════════════════════════════════
        Meta-Meta Layer (HyperAgents Layer 3)
        "Is our METHOD of improvement optimal?"
        • Bias Detection (80%+ collapse → force alternatives)
        • Cross-Domain Transfer
        • Self-Acceleration Detection
        • Emergent Capability Discovery
        • 5 improvement methods auto-selected
───────────────────────────────────────────────────────

        Evolution Engine
        Event-driven: 3+ failures / bias detected / 10+ entries
        Layer 2 (analysis) + Layer 3 (reflection) → action

        Neural Memory Grid
        HOT (5min) → WARM (1hr) → COLD (24hr) → discard
        Priority-based, fluid forgetting, adaptive compression
```

### Evolution Loop

```
┌─────────┐    ┌──────────┐    ┌────────────────┐
│  Sense  │───▶│ Meta     │───▶│ Meta-Meta      │
│         │    │ Analyze  │    │ Reflect        │
│ Archive │    │ Layer 2  │    │ "Is our METHOD │
│ Patterns│    │ Root     │    │  optimal?"     │
│         │    │ Cause    │    │ Layer 3        │
└─────────┘    └──────────┘    └────────────────┘
     ▲                              │
     │                              ▼
┌─────────┐    ┌──────────┐    ┌────────────────┐
│ Archive │◀───│ Evolve   │◀───│ Select Best   │
│ Stepping│    │ Action   │    │ Method         │
│ Stones  │    │ Take It  │    │                │
└─────────┘    └──────────┘    └────────────────┘
```

---

## 📋 Twenty CRM Setup

```bash
export TWENTY_BASE_URL=https://your-instance.twenty.com
export TWENTY_ACCESS_TOKEN=your_token_here

# Or edit config
python NEXUS_OS_v3.py config
```

Without credentials, it runs in mock mode for development.

---

## ⚙️ Configuration

Config file: `~/.nexus/config.json`

```json
{
  "twenty_base_url": "",
  "twenty_access_token": "",
  "evolution_auto": true,
  "evolution_failure_threshold": 3,
  "evolution_cycle_interval": 300,
  "bias_threshold": 0.80,
  "memory_hot_ttl": 300,
  "memory_warm_ttl": 3600,
  "memory_cold_ttl": 86400,
  "log_level": "INFO"
}
```

---

## 📁 Data Locations

| Data | Location |
|------|----------|
| Archive | `~/.nexus/archive/` |
| Skills | `~/.nexus/skills/` |
| Evolution | `~/.nexus/archive/evolution/` |
| Config | `~/.nexus/config.json` |
| Workspace | `~/.nexus/workspace/` |

---

## 🔧 Development

```bash
# Run all tests
python NEXUS_OS_v3.py test

# View status as JSON
python NEXUS_OS_v3.py status --json

# Create a task and execute
python NEXUS_OS_v3.py task --name "fix bug" --desc "API returns 500"

# View CRM status
python NEXUS_OS_v3.py crm

# Check healing stats
python NEXUS_OS_v3.py heal
```

### Running as a Daemon

```bash
# Auto-evolution every hour
0 * * * * cd ~/NEXUS_OS && python3 NEXUS_OS_v3.py evolve >> ~/.nexus/archive/evolution.log 2>&1
```

---

## 📖 Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — Deep dive into each layer
- [API.md](API.md) — Programmatic API reference
- [CONTRIBUTING.md](CONTRIBUTING.md) — How to contribute
- [CHANGELOG.md](CHANGELOG.md) — Version history

---

## 🧪 Testing

```bash
python NEXUS_OS_v3.py test

# Tests cover:
# ✅ Archive (logging + patterns)
# ✅ Knowledge Graph (add + search)
# ✅ Self-Healing (diagnose + strategies)
# ✅ Autonomous Coding (generate)
# ✅ Evolution Engine (cycles)
# ✅ Meta-Meta Layer (bias detection)
# ✅ Multi-Agent Fleet (select + status)
# ✅ Neural Memory Grid (store + retrieve)
# ✅ Twenty CRM (create + get tasks)
# ✅ Skill Forge (create + find)
# ✅ Full Status Report
```

---

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Run tests: `python NEXUS_OS_v3.py test`
4. Commit: `git commit -m 'feat: add amazing feature'`
5. Push: `git push origin feature/amazing-feature`
6. Open a Pull Request

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🧠 Philosophy

NEXUS OS is built on the **HyperAgents** principle:

> *"The improvement target is not just the Agent — the improvement METHOD itself can be improved."*

Every success and failure becomes a **stepping stone**. The system learns not just from what worked, but from *why* it worked and whether the way it chose that approach was optimal.

---

<div align="center">

**Built with curiosity, powered by self-improvement.**

*NEXUS OS — The system that improves itself.*

</div>

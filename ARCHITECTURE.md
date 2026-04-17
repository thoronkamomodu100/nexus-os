# NEXUS OS Architecture

## Overview

NEXUS OS is built on 8 interconnected layers, each responsible for a specific aspect of autonomous AI operation. The system is designed around the **HyperAgents** principle: every layer can observe, analyze, and improve itself.

## The 8 Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEXUS CORE (Orchestrator)                     │
├─────────────────┬──────────────────┬───────────────────────────┤
│   Layer 1       │  Layer 2         │  Layer 3                  │
│   Twenty CRM    │  Autonomous Code  │  Archive (Stepping Stones)│
├─────────────────┼──────────────────┼───────────────────────────┤
│   Layer 4       │  Layer 5         │  Layer 6                  │
│   Knowledge     │  Skill Forge     │  Multi-Agent Fleet        │
├─────────────────┴──────────────────┴───────────────────────────┤
│                    Layer 7: Self-Healing                        │
├─────────────────────────────────────────────────────────────────┤
│                    Layer 8: Meta-Meta (HyperAgents L3)         │
├─────────────────────────────────────────────────────────────────┤
│              Evolution Engine + Neural Memory Grid               │
└─────────────────────────────────────────────────────────────────┘
```

## Layer 1: Twenty CRM Client

Full API integration with Twenty CRM — tasks, activities, pipeline.

**Modes:** `live` (real API) or `mock` (development)

```python
task = crm.create_task("Build feature X", status="IN_PROGRESS")
activities = crm.get_activities(task_id="xxx")
metrics = crm.get_metrics()
```

## Layer 2: Autonomous Coding Agent

Natural language → working code → execution.

**Templates:**
| Template | Use Case | Dependencies |
|----------|----------|-------------|
| `web_scraper` | Data extraction | requests, beautifulsoup4 |
| `rest_api` | API endpoints | flask |
| `cli_tool` | Command-line tools | argparse |
| `data_processor` | ETL | csv, json |

## Layer 3: Archive (Stepping Stones)

Every action is archived as a **stepping stone**.

**Root Cause Taxonomy (12 types):**
permission_issue, resource_missing, timeout, memory_issue, network_issue, syntax_error, import_error, encoding_error, null_reference, invalid_input, unknown

## Layer 4: Knowledge Graph

In-memory graph database. Operations: add, search (keyword + tag scoring), link, get_related (BFS).

## Layer 5: Skill Forge

Dynamic skill lifecycle: create → use → track_stats → evolve → use_v2

## Layer 6: Multi-Agent Fleet

6 specialized agents with capability-based routing:
Code Agent, Research Agent, Builder Agent, Debug Agent, Planner Agent, Evolution Agent.

## Layer 7: Self-Healing

Error → Diagnosis → Recovery strategy.

**Strategy types:** auto, command, suggest, config

## Layer 8: Meta-Meta Layer (HyperAgents L3)

**Core Question:** "Is our METHOD of improvement optimal?"

- **Bias Detection:** 80%+ → SEVERE, 95%+ → COLLAPSED
- **Self-Acceleration:** Compares recent vs older quality scores
- **Cross-Domain Transfer:** Approach overlap across domains

**5 Improvement Methods:** archive_based, knowledge_based, analogy_transfer, random_exploration, meta_learning

## Evolution Engine

**Trigger Conditions:**
- 3+ consecutive failures
- Bias detected (≥80%)
- 10+ new archive entries
- 5+ minutes since last cycle

**Cycle Steps:** Load patterns → Layer 2 analysis → Layer 3 reflection → Generate actions → Archive → Update knowledge

## Neural Memory Grid

| Tier | TTL | Criteria |
|------|-----|---------|
| HOT | 5 min | Working memory |
| WARM | 1 hour | Frequently accessed |
| COLD | 24 hours | Recent but unused |
| DISCARD | — | Low priority + old |

## Data Flow

```
User/Cron → NEXUSCore → Archive ← Knowledge ← Fleet
                │          ↑           │
                ▼          │           ▼
           Twenty CRM    Evolution    Coding
                │          │           │
                ▼          ▼           ▼
            Activities   Meta-Meta   Execution
```

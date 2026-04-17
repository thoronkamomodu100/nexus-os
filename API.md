# NEXUS OS API Reference

## Quick Start

```python
from NEXUS_OS_v3 import NEXUSCore

nx = NEXUSCore()
```

## NEXUSCore

Main entry point. Initializes all 8 layers.

```python
nx = NEXUSCore(config: NEXUSConfig = None)
```

### Methods

#### `status() → Dict`
Returns comprehensive system status including archive, knowledge, fleet, evolution, and more.

#### `code(description: str) → Dict`
Generate code from natural language description.
```python
result = nx.code("REST API with health endpoint")
# → {"project_name": "...", "project_dir": "...", "files": [...], "template_used": "rest_api"}
```

#### `create_task(name: str, description: str, priority: Priority) → Task`
Create a new task.

#### `execute_task(task: Dict, executor: Callable) → Any`
Execute a task with full monitoring, archiving, and evolution.

#### `evolve(manual: bool = True) → Dict`
Trigger an evolution cycle.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `archive` | Archive | Stepping stones |
| `knowledge` | KnowledgeGraph | Knowledge graph |
| `evolution` | EvolutionEngine | Evolution engine |
| `meta_meta` | MetaMetaLayer | Meta-Meta layer |
| `fleet` | MultiAgentFleet | Agent fleet |
| `skill_forge` | SkillForge | Skill management |
| `memory` | NeuralMemoryGrid | Memory system |
| `healing` | SelfHealing | Self-healing |
| `crm` | TwentyCRM | CRM client |
| `coding` | AutonomousCodingAgent | Code generator |

## Archive

```python
nx.archive.log_success(task_name, approach, result, duration)
nx.archive.log_failure(task_name, approach, error, duration)
patterns = nx.archive.get_patterns()
```

## KnowledgeGraph

```python
node = nx.knowledge.add("Title", "Content", tags=["tag1"])
results = nx.knowledge.search("query", limit=5)
nx.knowledge.link(node_id_a, node_id_b)
stats = nx.knowledge.stats()
```

## MultiAgentFleet

```python
fleet.status()
best = fleet.select_best("write code for me")
fleet.assign(agent_id, task_id)
fleet.complete(agent_id, score=0.85)
```

## SkillForge

```python
skill = nx.skill_forge.create("my_skill", "desc", "print('hello')", ["hello"])
nx.skill_forge.record_usage("my_skill", success=True, duration=2.5)
found = nx.skill_forge.find("hello")
```

## NeuralMemoryGrid

```python
nx.memory.store("key", value, priority=0.8, tier="hot")
val = nx.memory.retrieve("key")
nx.memory.compress()
context = nx.memory.get_context(max_items=20)
```

## SelfHealing

```python
diagnosis = nx.healing.diagnose("Permission denied: /root/file.txt")
recovery = nx.healing.apply_recovery(diagnosis)
```

## MetaMetaLayer

```python
reflection = nx.meta_meta.reflect(patterns)
# Returns: layer, bias_assessment, cross_domain_transfer,
#          self_acceleration, method_scores, selected_method, recommendations
```

## CLI

```bash
python NEXUS_OS_v3.py status [--json]
python NEXUS_OS_v3.py evolve
python NEXUS_OS_v3.py code --desc "description"
python NEXUS_OS_v3.py task --name "taskname" [--desc "description"]
python NEXUS_OS_v3.py knowledge [--query "query"] [-n 10]
python NEXUS_OS_v3.py crm
python NEXUS_OS_v3.py fleet
python NEXUS_OS_v3.py archive
python NEXUS_OS_v3.py heal
python NEXUS_OS_v3.py test
```

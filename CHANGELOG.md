# Changelog

All notable changes to NEXUS OS are documented here.

## [3.0.0] — 2026-04-18

### Added
- **HyperAgents 3-Layer Architecture** — Complete Layer 1 (Task), Layer 2 (Meta), Layer 3 (Meta-Meta) implementation
- **Bias Detection** — Auto-detect 80%+ approach collapse with forced alternatives
- **Self-Acceleration Detection** — Track if improvement rate is increasing over time
- **Cross-Domain Transfer** — Find transferable patterns across different task domains
- **5 Improvement Methods** — archive_based, knowledge_based, analogy_transfer, random_exploration, meta_learning
- **Twelve Error Types** — permission_issue, resource_missing, timeout, memory_issue, network_issue, syntax_error, import_error, encoding_error, null_reference, invalid_input + unknown
- **Neural Memory Grid** — 3-tier memory (HOT/WARM/COLD) with fluid forgetting
- **Skill Forge** — Dynamic skill creation, tracking, and evolution
- **Autonomous Coding Agent** — 4 templates (web_scraper, rest_api, cli_tool, data_processor)
- **Multi-Agent Fleet** — 6 specialized agents with capability-based routing
- **Twenty CRM Client** — Full task/activity management with live + mock modes
- **Event-Driven Evolution** — Auto-evolution triggered by failures/bias/time
- **Python 3.10-3.14 Support** — Compatible dataclass implementation

### Changed
- Complete rewrite from v2.x
- Unified single-file architecture (was multi-file)
- CLI interface redesigned with colorized output
- Archive now uses file-based JSON with caching

### Fixed
- Python 3.14 dataclass compatibility (mutable defaults)
- Race conditions in multi-threaded operations
- Archive pattern caching

## [2.0.0] — 2026-04-16

### Added
- Initial multi-file architecture
- Basic archive system
- Knowledge graph prototype
- Twenty CRM integration prototype
- Multi-agent fleet prototype

### Known Issues
- Some dataclass definitions incompatible with Python 3.14
- Archive not thread-safe under heavy load
- No bias detection

## [1.0.0] — 2026-04-12

### Added
- Core engine prototype
- Task planning and execution
- Basic CLI
- Archive stub

---

*Format: [Version] — Date*

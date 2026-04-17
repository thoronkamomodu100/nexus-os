# Contributing to NEXUS OS

## Code of Conduct

Be respectful, constructive, and curious. We welcome all contributions regardless of experience level.

## How to Contribute

### Reporting Bugs

1. Check existing issues first
2. Create issue with: clear title, steps to reproduce, expected vs actual behavior, Python version, error traceback

### Suggesting Features

1. Check existing issues/discussions
2. Open a feature request with: clear use case, proposed implementation, how it fits NEXUS philosophy

### Pull Requests

#### Development Setup
```bash
git clone https://github.com/nexus-os/nexus.git
cd nexus
pip install -e ".[dev]"
python NEXUS_OS_v3.py test
```

#### Making Changes
1. Branch: `git checkout -b feature/your-feature`
2. Make changes + add tests
3. Run tests: `python NEXUS_OS_v3.py test`
4. Commit: `git commit -m 'feat: add your feature'`
5. Push: `git push origin feature/your-feature`
6. Open a Pull Request

#### Commit Format
```
<type>(<scope>): <description>
Types: feat, fix, docs, style, refactor, test, chore
Examples:
  feat(evolution): add self-acceleration detection
  fix(archive): resolve race condition in logging
  test(meta): add bias detection tests
```

#### PR Checklist
- [ ] Tests pass: `python NEXUS_OS_v3.py test`
- [ ] New tests for new functionality
- [ ] Documentation updated if needed

## Areas for Contribution

**High Priority:**
- Twenty CRM API coverage improvements
- Additional code generation templates
- Self-healing strategy expansions

**Medium Priority:**
- CLI improvements
- Performance optimizations
- Visualization tools

**Exploratory:**
- New Meta-Meta analysis methods
- Advanced bias detection
- Cross-domain transfer improvements

---

*Thank you for making NEXUS OS better!*

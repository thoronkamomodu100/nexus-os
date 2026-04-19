"""
CodeFlow-inspired dependency analyzer for NEXUS_OS.
Analyzes codebase architecture: dependency graph, blast radius, code ownership.
Pure Python — no external dependencies beyond stdlib + git.
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any, Optional


# ── Language Parsers ──────────────────────────────────────────────────────────

LANG_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
}


def get_language(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return LANG_EXTENSIONS.get(ext, "unknown")


def extract_imports_python(content: str) -> List[str]:
    """Extract imported modules/variables from Python source."""
    imports = []
    
    # from X import Y
    for match in re.finditer(r'^from\s+([\w.]+)', content, re.MULTILINE):
        imports.append(match.group(1))
    
    # import X / import X as Y
    for match in re.finditer(r'^import\s+([\w.]+)', content, re.MULTILINE):
        imports.append(match.group(1))
    
    # from X import (Y, Z)
    for match in re.finditer(r'^from\s+([\w.]+)\s+import\s+\(', content, re.MULTILINE):
        imports.append(match.group(1))
    
    return list(set(imports))


def extract_imports_js(content: str) -> List[str]:
    """Extract require()/import() from JavaScript/TypeScript."""
    imports = []
    
    # require('X') or require("X")
    for match in re.finditer(r"require\s*\(\s*['\"]([^'\"]+)['\"]", content):
        imports.append(match.group(1))
    
    # import X from 'Y' / import 'Y'
    for match in re.finditer(r"import\s+(?:[\w*{}\s,]+\s+from\s+)?['\"]([^'\"]+)['\"]", content):
        imports.append(match.group(1))
    
    # dynamic import()
    for match in re.finditer(r"import\s*\(\s*['\"]([^'\"]+)['\"]", content):
        imports.append(match.group(1))
    
    return list(set(imports))


def extract_imports_go(content: str) -> List[str]:
    """Extract imports from Go source."""
    imports = []
    
    # import "X" or import ( "X" )
    for match in re.finditer(r'import\s*(?:\(\s*)?["\']([^"\']+)["\']', content):
        imports.append(match.group(1))
    
    return list(set(imports))


def extract_imports_rust(content: str) -> List[str]:
    """Extract use statements from Rust source."""
    imports = []
    
    # use X::Y::Z;
    for match in re.finditer(r'^use\s+([\w:]+)', content, re.MULTILINE):
        imports.append(match.group(1))
    
    return list(set(imports))


def extract_functions_python(content: str, file_path: str) -> Dict[str, Dict]:
    """Extract function and class definitions from Python."""
    funcs = {}
    
    # class Foo:
    for match in re.finditer(r'^class\s+(\w+)', content, re.MULTILINE):
        name = match.group(1)
        funcs[name] = {
            "name": name,
            "type": "class",
            "file": file_path,
            "line": content[:match.start()].count('\n') + 1,
        }
    
    # def foo(): / async def foo():
    for match in re.finditer(r'^(?:async\s+)?def\s+(\w+)\s*\(', content, re.MULTILINE):
        name = match.group(1)
        funcs[name] = {
            "name": name,
            "type": "function",
            "file": file_path,
            "line": content[:match.start()].count('\n') + 1,
        }
    
    return funcs


def extract_functions_js(content: str, file_path: str) -> Dict[str, Dict]:
    """Extract function definitions from JavaScript/TypeScript."""
    funcs = {}
    
    # function foo() { ... }
    for match in re.finditer(r'function\s+(\w+)\s*\(', content):
        name = match.group(1)
        funcs[name] = {
            "name": name,
            "type": "function",
            "file": file_path,
            "line": content[:match.start()].count('\n') + 1,
        }
    
    # const foo = () => { ... }
    for match in re.finditer(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>', content):
        name = match.group(1)
        funcs[name] = {
            "name": name,
            "type": "arrow_function",
            "file": file_path,
            "line": content[:match.start()].count('\n') + 1,
        }
    
    # class Foo { ... }
    for match in re.finditer(r'class\s+(\w+)', content):
        name = match.group(1)
        funcs[name] = {
            "name": name,
            "type": "class",
            "file": file_path,
            "line": content[:match.start()].count('\n') + 1,
        }
    
    return funcs


EXTRACTORS = {
    "python": (extract_imports_python, extract_functions_python),
    "javascript": (extract_imports_js, extract_functions_js),
    "typescript": (extract_imports_js, extract_functions_js),
    "go": (extract_imports_go, lambda c, f: {}),
    "rust": (extract_imports_rust, lambda c, f: {}),
}


def analyze_file(file_path: str, content: str) -> Dict[str, Any]:
    """Analyze a single file — returns imports, functions, etc."""
    lang = get_language(file_path)
    extractor = EXTRACTORS.get(lang)
    
    if extractor:
        import_fn, func_fn = extractor
        imports = import_fn(content)
        funcs = func_fn(content, file_path)
    else:
        imports = []
        funcs = {}
    
    return {
        "path": file_path,
        "language": lang,
        "imports": imports,
        "functions": funcs,
        "lines": content.count('\n') + 1,
    }


def analyze_directory(root_path: str, exclude_patterns: List[str] = None) -> Dict[str, Any]:
    """
    Analyze a directory and build dependency graph.
    Returns CodeFlow-style data structure.
    """
    exclude_patterns = exclude_patterns or [
        "__pycache__", ".git", ".venv", "node_modules",
        ".pytest_cache", ".mypy_cache", "dist", "build",
        ".egg-info", ".tox", "vendor", "tmp", "temp",
    ]
    
    root = Path(root_path).resolve()
    files = {}
    connections = []
    all_funcs = {}  # name -> {file, line, type}
    
    # ── Step 1: Parse all files ──────────────────────────────────────────────
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        
        # Skip excluded patterns
        path_str = str(path)
        if any(ex in path_str for ex in exclude_patterns):
            continue
        
        ext = path.suffix.lower()
        if ext not in LANG_EXTENSIONS:
            continue
        
        try:
            content = path.read_text(errors="ignore")
        except Exception:
            continue
        
        rel_path = str(path.relative_to(root))
        result = analyze_file(rel_path, content)
        files[rel_path] = result
        
        # Index all functions globally
        for fname, finfo in result["functions"].items():
            all_funcs[fname] = finfo
    
    # ── Step 2: Build intra-repository connections ───────────────────────────
    # If file A imports from file B (by module name), connect them
    for fpath, finfo in files.items():
        for imp in finfo["imports"]:
            # Try to resolve import to a file path in our repo
            resolved = _resolve_import(imp, fpath, files, root)
            if resolved and resolved != fpath:
                connections.append({
                    "source": resolved,
                    "target": fpath,
                    "type": "import",
                    "count": 1,
                })
    
    # ── Step 3: Build function-level connections ─────────────────────────────
    # (function defined in file X, called in file Y)
    fn_connections = []
    for fpath, finfo in files.items():
        content = Path(root / fpath).read_text(errors="ignore")
        for fname in all_funcs:
            # Count references to this function in the file
            pattern = r'\b' + re.escape(fname) + r'\b'
            count = len(re.findall(pattern, content))
            if count > 0:
                def_file = all_funcs[fname]["file"]
                if def_file != fpath:
                    fn_connections.append({
                        "source": def_file,
                        "target": fpath,
                        "fn": fname,
                        "count": count,
                    })
    
    # Deduplicate function connections
    seen = {}
    for conn in fn_connections:
        key = (conn["source"], conn["target"], conn.get("fn", ""))
        if key not in seen or seen[key] < conn["count"]:
            seen[key] = conn["count"]
    connections.extend({"source": s, "target": t, "fn": fn, "count": c, "type": "call"}
                       for (s, t, fn), c in seen.items())
    
    # ── Step 4: Build folder structure ──────────────────────────────────────
    folders = list(set(str(Path(f).parent) for f in files))
    
    # ── Step 5: Blast radius for each file ──────────────────────────────────
    blast_radius = {}
    for fpath in files:
        affected = _calc_blast(fpath, connections)
        blast_radius[fpath] = {
            "file": fpath,
            "direct_deps": len([c for c in connections if c["source"] == fpath]),
            "direct_dependents": len([c for c in connections if c["target"] == fpath]),
            "total_affected": len(affected),
            "affected_files": list(affected),
        }
    
    return {
        "files": [{"path": f, **files[f]} for f in sorted(files)],
        "connections": connections,
        "functions": all_funcs,
        "folders": sorted(folders),
        "blast_radius": blast_radius,
        "stats": {
            "total_files": len(files),
            "total_connections": len(connections),
            "total_functions": len(all_funcs),
            "total_folders": len(folders),
        }
    }


def _resolve_import(imp: str, from_file: str, files: Dict, root: Path) -> Optional[str]:
    """
    Try to resolve a Python/JS import to an actual file path in the repo.
    E.g. 'from mypackage.utils import foo' -> 'mypackage/utils.py'
    """
    parts = imp.split(".")
    from_dir = str(Path(from_file).parent).replace("\\", "/")
    
    for f in files:
        f_clean = f.replace("\\", "/")
        
        # Direct match
        if f_clean == imp.replace("\\", "/") or f_clean == imp.replace("\\", "/") + ".py":
            return f
        
        # File is in a subdir matching the import prefix
        import_prefix = "/".join(parts[:-1]) if len(parts) > 1 else parts[0]
        if f_clean.startswith(from_dir) and import_prefix in f_clean:
            return f
    
    return None


def _calc_blast(file_path: str, connections: List[Dict]) -> Set[str]:
    """
    Calculate blast radius — all files affected by changes to file_path.
    Includes direct dependents and transitive dependents.
    """
    # Build adjacency: file -> files that depend on it
    dependents: Dict[str, Set[str]] = defaultdict(set)
    for conn in connections:
        if conn["type"] == "import":
            dependents[conn["source"]].add(conn["target"])
    
    # BFS to find all transitive dependents
    visited = set()
    queue = [file_path]
    
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        
        for dep in dependents.get(current, []):
            if dep not in visited:
                queue.append(dep)
    
    visited.discard(file_path)  # Don't count self
    return visited


def blast_radius_for_file(file_path: str, repo_path: str) -> Dict[str, Any]:
    """Analyze blast radius for a specific file in a repo."""
    result = analyze_directory(repo_path)
    return result["blast_radius"].get(file_path, {
        "file": file_path,
        "error": "file not found in repository",
    })


if __name__ == "__main__":
    # Quick test
    import sys
    if len(sys.argv) > 1:
        repo = sys.argv[1]
        result = analyze_directory(repo)
        print(json.dumps(result["stats"], indent=2))
        print(f"\nTop 5 highest blast radius files:")
        by_blast = sorted(
            result["blast_radius"].items(),
            key=lambda x: x[1]["total_affected"],
            reverse=True
        )[:5]
        for fpath, info in by_blast:
            print(f"  {info['total_affected']} files: {fpath}")
    else:
        print("Usage: python codeflow_analyzer.py <repo_path>")

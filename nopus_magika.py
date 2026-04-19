#!/usr/bin/env python3
r"""
nopus_magika.py — Pure Python AI-less file type detector (Magika-style)

A zero-dependency, ML-free file type detector inspired by Google's Magika.
Detects file types using four layered strategies, applied in strict priority:

  Priority 1 — Extension
      Map filename suffixes (e.g. ".py", "Dockerfile") and exact filenames
      to MIME types.  Highest reliability: an extension is definitive
      unless the file is malformed or deliberately misnamed.
      Confidence: 0.7–0.99.

  Priority 2 — Shebang
      Inspect the first line of a text file for a "#!" interpreter
      directive (e.g. "#!/usr/bin/env python3").  Essential for
      extensionless scripts.  Confidence: 0.99.

  Priority 3 — Magic Bytes
      Compare the first few bytes of the file against a registry of
      binary signatures (PNG, PDF, ELF, ZIP, SQLite, Mach-O, …).
      Only consulted when the file contains a null byte (binary indicator).
      Confidence: 0.95.

  Priority 4 — Content Heuristics
      Scan the decoded text for structural patterns:
        - HTML/XML DOCTYPE / opening tags
        - JSON top-level braces ("{" or "[")
        - Language keywords ("package", "use", "fn", "import")
        - Markdown heading syntax ("# ", "## ")
        - SQL DML/DDL verbs
      Confidence: 0.7–0.99.

  Fallback
      No pattern matched:
        - Null byte found → binary / application/octet-stream
        - Otherwise       → text/plain

Result fields (FileTypeResult):
    mime             RFC 2045 MIME type string
    label            Human-readable description ("Python source", "ZIP archive")
    category         High-level group (code | image | archive | data | …)
    confidence       0.0–1.0 certainty score
    is_binary        True when the content contains a null byte
    is_text          True for text content
    language         Programming language name when applicable, else None
    detection_method One of: extension | shebang | magic | content | none

No external dependencies — pure Python 3 stdlib only.

Based on google/magika principles but reimplemented in pure Python.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Optional, Pattern

# ---------------------------------------------------------------------------
# Type aliases — documented so complex tuple shapes are self-explanatory
# ---------------------------------------------------------------------------

# (magic_bytes, byte_offset, mime_type, label)
MagicSignature = tuple[bytes, int, str, str]

# (mime, label, category, confidence)
ExtEntry = tuple[str, str, str, float]

# Compiled content pattern: (compiled_regex, mime, label, category, confidence)
ContentPattern = tuple[Pattern[str], str, str, str, float]


# ---------------------------------------------------------------------------
# Magic Bytes Registry
# Format: (magic_bytes, offset_from_start, mime_type, label)
# ---------------------------------------------------------------------------

BINARY_SIGNATURES: Final[list[MagicSignature]] = [
    # Images
    (b"\x89PNG\r\n\x1a\n",        0, "image/png",                         "PNG image"),
    (b"\xff\xd8\xff",              0, "image/jpeg",                        "JPEG image"),
    (b"\x47\x49\x46\x38\x37\x61", 0, "image/gif",                         "GIF87a image"),
    (b"\x47\x49\x46\x38\x39\x61", 0, "image/gif",                         "GIF89a image"),
    (b"\x00\x00\x01\x00",          0, "image/x-icon",                      "ICO icon"),
    (b"AT&T",                       0, "image/x-djvu",                      "DjVu document"),
    # Video
    (b"\x1aE\xdf\xa3",              0, "video/webm",                        "WebM video"),
    (b"\x00\x00\x00\x14ftyp",      4, "video/mp4",                          "MP4 video"),
    (b"\x00\x00\x00\x18ftyp",      4, "video/mp4",                          "MP4 video"),
    (b"\x00\x00\x00\x08",          4, "video/mp4",                          "MP4 video (alt)"),
    # Audio
    (b"RIFF",                       0, "audio/wav",                         "WAV audio"),
    (b"OggS",                       0, "audio/ogg",                         "OGG audio"),
    (b"fLaC",                       0, "audio/flac",                         "FLAC audio"),
    (b"ID3",                        0, "audio/mpeg",                         "MP3 audio (ID3)"),
    (b"\xff\xfb",                   0, "audio/mpeg",                         "MP3 audio"),
    (b"\xff\xfa",                   0, "audio/mpeg",                         "MP3 audio"),
    (b"\xff\xf3",                   0, "audio/mpeg",                         "MP3 audio"),
    (b"\xff\xf2",                   0, "audio/mpeg",                         "MP3 audio"),
    # Documents
    (b"%PDF",                       0, "application/pdf",                    "PDF document"),
    (b"{\\rtf",                     0, "text/rtf",                           "RTF document"),
    (b"%!",                         0, "application/postscript",             "PostScript"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0, "application/x-msoffice",   "MS Office (old)"),
    # Archives
    (b"PK\x03\x04",                0, "application/zip",                    "ZIP archive"),
    (b"PK\x05\x06",                0, "application/zip",                   "ZIP archive (empty)"),
    (b"PK\x07\x08",                0, "application/zip",                    "ZIP archive (spanned)"),
    (b"Rar!\x1a\x07\x00",          0, "application/vnd.rar",               "RAR archive"),
    (b"Rar!\x1a\x07\x01\x00",     0, "application/vnd.rar",               "RAR archive v1.1"),
    (b"\x37\x7a\xbc\xaf\x27\x1c", 0, "application/x-7z-compressed",      "7z archive"),
    (b"\x1f\x8b",                  0, "application/gzip",                   "GZIP archive"),
    (b"BZh",                        0, "application/x-bzip2",                "BZIP2 archive"),
    (b"\xfd7zXZ\x00",              0, "application/x-xz",                  "XZ archive"),
    (b"zstd",                       0, "application/zstd",                  "Zstandard archive"),
    (b"\x04\x22\x4d\x18",          0, "application/zstd",                  "Zstandard archive (alt)"),
    (b"\x1f\x9d",                  0, "application/x-compress",             "Compress archive"),
    (b"\x1f\xb8",                  0, "application/x-lzh",                  "LZH archive"),
    # Executables / Binaries
    (b"\xca\xfe\xba\xbe",          0, "application/x-mach-binary",         "Mach-O binary (BE)"),
    (b"\xfe\xed\xfa\xce",          0, "application/x-mach-binary",         "Mach-O binary (LE)"),
    (b"\xfe\xed\xfa\xcf",          0, "application/x-mach-binary",         "Mach-O binary (LE64)"),
    (b"\xcf\xfa\xed\xfe",          0, "application/x-mach-binary",         "Mach-O binary (LE64 alt)"),
    (b"\x7fELF",                    0, "application/x-executable",            "ELF executable"),
    (b"MZ",                         0, "application/x-msdownload",          "Windows executable"),
    # Special / Filesystem images
    (b"SQLite format 3",            0, "application/vnd.sqlite3",            "SQLite database"),
    (b"hsqs",                       0, "application/x-squashfs",             "SquashFS"),
    (b"sqsh",                       0, "application/x-squashfs",             "SquashFS (alt)"),
    (b"\x28\xcd\x15\x9e",          0, "application/x-cramfs",              "CramFS"),
    (b"\x53\xef",               0x438, "application/x-ext2",                 "EXT2/3/4 filesystem"),
    (b"NTFS",                   0x03, "application/x-ntfs",                  "NTFS filesystem"),
    # Packet captures
    (b"\xa1\xb2\xc3\xd4",         0, "application/vnd.tcpdump.capture",    "pcap capture (LE)"),
    (b"\xd4\xc3\xb2\xa1",         0, "application/vnd.tcpdump.capture",    "pcap capture (BE)"),
    # Other binaries
    (b"idPkg",                      0, "application/x-itc",                  "Apple ITC package"),
    (b"dex\n",                      0, "application/vnd.android.dex",         "Android DEX"),
    (b"\x00asm",                    0, "application/wasm",                    "WebAssembly"),
    (b"\x00\x61\x73\x6d",          0, "application/wasm",                   "WebAssembly (alt)"),
]

# ─── Extension Map (highest priority — most reliable) ───────────────────────

EXT_MAP: dict[str, tuple[str, str, str, float]] = {
    # Binary images
    ".png":  ("image/png",                         "PNG image",          "image", 0.99),
    ".jpg":  ("image/jpeg",                        "JPEG image",         "image", 0.99),
    ".jpeg": ("image/jpeg",                        "JPEG image",         "image", 0.99),
    ".gif":  ("image/gif",                         "GIF image",          "image", 0.99),
    ".webp": ("image/webp",                        "WebP image",         "image", 0.99),
    ".bmp":  ("image/bmp",                         "BMP image",          "image", 0.99),
    ".ico":  ("image/x-icon",                       "ICO icon",           "image", 0.99),
    ".tiff": ("image/tiff",                        "TIFF image",         "image", 0.95),
    ".tif":  ("image/tiff",                        "TIFF image",         "image", 0.95),
    ".svg":  ("image/svg+xml",                      "SVG image",          "image", 0.95),
    ".jxr":  ("image/x-jxr",                        "JPEG XR",            "image", 0.9),
    # Binary video/audio
    ".mp4":  ("video/mp4",                         "MP4 video",          "video", 0.99),
    ".mov":  ("video/quicktime",                    "QuickTime video",    "video", 0.99),
    ".avi":  ("video/x-msvideo",                    "AVI video",          "video", 0.95),
    ".mkv":  ("video/x-matroska",                   "MKV video",          "video", 0.95),
    ".webm": ("video/webm",                         "WebM video",         "video", 0.95),
    ".flv":  ("video/x-flv",                        "FLV video",          "video", 0.9),
    ".wmv":  ("video/x-ms-wmv",                     "WMV video",          "video", 0.9),
    ".mp3":  ("audio/mpeg",                         "MP3 audio",          "audio", 0.99),
    ".flac": ("audio/flac",                         "FLAC audio",         "audio", 0.99),
    ".wav":  ("audio/wav",                         "WAV audio",          "audio", 0.99),
    ".ogg":  ("audio/ogg",                         "OGG audio",          "audio", 0.95),
    ".opus": ("audio/opus",                         "Opus audio",         "audio", 0.95),
    ".aac":  ("audio/aac",                         "AAC audio",          "audio", 0.95),
    ".m4a":  ("audio/mp4",                         "M4A audio",          "audio", 0.95),
    ".amr":  ("audio/amr",                         "AMR audio",          "audio", 0.9),
    # Archives
    ".zip":  ("application/zip",                    "ZIP archive",        "archive", 0.99),
    ".tar":  ("application/x-tar",                  "TAR archive",        "archive", 0.99),
    ".gz":   ("application/gzip",                   "GZIP archive",       "archive", 0.99),
    ".tgz":  ("application/gzip",                   "GZIP tar archive",   "archive", 0.99),
    ".bz2":  ("application/x-bzip2",                 "BZIP2 archive",      "archive", 0.95),
    ".xz":   ("application/x-xz",                   "XZ archive",         "archive", 0.95),
    ".7z":   ("application/x-7z-compressed",         "7z archive",         "archive", 0.95),
    ".rar":  ("application/vnd.rar",                "RAR archive",        "archive", 0.95),
    ".zst":  ("application/zstd",                   "Zstandard archive",  "archive", 0.95),
    ".lz4":  ("application/x-lz4",                  "LZ4 archive",       "archive", 0.9),
    # Documents
    ".pdf":  ("application/pdf",                    "PDF document",       "document", 0.99),
    ".doc":  ("application/msword",                 "MS Word document",   "document", 0.95),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Word document", "document", 0.99),
    ".xls":  ("application/vnd.ms-excel",           "MS Excel spreadsheet","document", 0.95),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Excel document", "document", 0.99),
    ".ppt":  ("application/vnd.ms-powerpoint",      "MS PowerPoint",     "document", 0.95),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "PowerPoint document", "document", 0.99),
    ".rtf":  ("text/rtf",                          "RTF document",       "document", 0.9),
    ".odt":  ("application/vnd.oasis.opendocument.text", "ODT document",  "document", 0.9),
    ".ods":  ("application/vnd.oasis.opendocument.spreadsheet", "ODS spreadsheet", "document", 0.9),
    ".odp":  ("application/vnd.oasis.opendocument.presentation", "ODP presentation", "document", 0.9),
    # Notebooks / data
    ".ipynb":("application/x-ipynb+json",            "Jupyter Notebook",  "notebook", 0.99),
    ".json": ("application/json",                    "JSON data",         "data", 0.99),
    ".jsonc":("application/json",                    "JSON (with comments)","data", 0.9),
    ".jsonl":("application/jsonl",                   "JSON Lines",       "data", 0.99),
    ".ndjson":("application/jsonl",                  "NDJSON",            "data", 0.99),
    ".yaml": ("text/x-yaml",                        "YAML",              "data", 0.99),
    ".yml":  ("text/x-yaml",                        "YAML",              "data", 0.99),
    ".toml": ("application/toml",                   "TOML",              "data", 0.99),
    ".xml":  ("application/xml",                    "XML",               "data", 0.99),
    ".csv":  ("text/csv",                           "CSV",               "data", 0.99),
    ".tsv":  ("text/tab-separated-values",          "TSV",               "data", 0.99),
    ".sql":  ("text/x-sql",                         "SQL",               "data", 0.99),
    ".graphql":("application/graphql",               "GraphQL",           "data", 0.99),
    # Code — Python
    ".py":   ("text/x-python",                      "Python source",     "code", 0.99),
    ".pyi":  ("text/x-python",                      "Python stub",       "code", 0.99),
    ".pyw":  ("text/x-python",                      "Python (Windows)", "code", 0.99),
    # Code — JavaScript/TypeScript
    ".js":   ("text/x-javascript",                  "JavaScript",        "code", 0.99),
    ".mjs":  ("text/x-javascript",                  "ES Module JS",       "code", 0.99),
    ".cjs":  ("text/x-javascript",                  "CommonJS JS",       "code", 0.99),
    ".jsx":  ("text/x-jsx",                         "JSX",               "code", 0.99),
    ".ts":   ("text/x-typescript",                  "TypeScript",        "code", 0.99),
    ".tsx":  ("text/x-tsx",                         "TSX",               "code", 0.99),
    # Code — Web
    ".html": ("text/html",                          "HTML",              "markup", 0.99),
    ".htm":  ("text/html",                          "HTML",              "markup", 0.99),
    ".css":  ("text/css",                           "CSS",               "style", 0.99),
    ".scss": ("text/x-scss",                        "SCSS",              "style", 0.99),
    ".sass": ("text/x-sass",                        "Sass",              "style", 0.99),
    ".less": ("text/x-less",                        "Less",              "style", 0.99),
    # Code — Systems
    ".c":    ("text/x-c",                           "C source",          "code", 0.99),
    ".h":    ("text/x-c-header",                     "C header",          "code", 0.99),
    ".cpp":  ("text/x-cpp",                         "C++ source",        "code", 0.99),
    ".cc":   ("text/x-cpp",                         "C++ source",        "code", 0.99),
    ".cxx":  ("text/x-cpp",                         "C++ source",        "code", 0.99),
    ".hpp":  ("text/x-cpp-header",                  "C++ header",        "code", 0.99),
    ".hh":   ("text/x-cpp-header",                  "C++ header",        "code", 0.99),
    ".cs":   ("text/x-csharp",                      "C# source",         "code", 0.99),
    ".java": ("text/x-java",                        "Java source",       "code", 0.99),
    ".kt":   ("text/x-kotlin",                      "Kotlin source",     "code", 0.99),
    ".kts":  ("text/x-kotlin",                      "Kotlin script",     "code", 0.99),
    ".scala":("text/x-scala",                       "Scala source",      "code", 0.99),
    ".swift":("text/x-swift",                       "Swift source",      "code", 0.99),
    ".go":   ("text/x-go",                          "Go source",         "code", 0.99),
    ".rs":   ("text/x-rust",                        "Rust source",       "code", 0.99),
    ".rb":   ("text/x-ruby",                        "Ruby source",       "code", 0.99),
    ".erb":  ("text/x-ruby",                        "Ruby ERB",          "code", 0.99),
    ".php":  ("text/x-php",                         "PHP source",        "code", 0.99),
    ".pl":   ("text/x-perl",                        "Perl source",       "code", 0.99),
    ".pm":   ("text/x-perl",                        "Perl module",       "code", 0.99),
    ".lua":  ("text/x-lua",                         "Lua source",        "code", 0.99),
    ".r":    ("text/x-r",                           "R source",          "code", 0.99),
    ".R":    ("text/x-r",                           "R source",          "code", 0.99),
    ".dart": ("text/x-dart",                        "Dart source",       "code", 0.99),
    ".clj":  ("text/x-clojure",                     "Clojure source",    "code", 0.99),
    ".cljs": ("text/x-clojure",                     "ClojureScript",     "code", 0.99),
    ".ex":   ("text/x-elixir",                      "Elixir source",     "code", 0.99),
    ".exs":  ("text/x-elixir",                      "Elixir script",     "code", 0.99),
    ".erl":  ("text/x-erlang",                      "Erlang source",     "code", 0.99),
    ".hrl":  ("text/x-erlang",                      "Erlang header",     "code", 0.99),
    ".hs":   ("text/x-haskell",                     "Haskell source",    "code", 0.99),
    ".ml":   ("text/x-ocaml",                       "OCaml source",      "code", 0.99),
    ".mli":  ("text/x-ocaml",                       "OCaml interface",  "code", 0.99),
    ".nim":  ("text/x-nim",                         "Nim source",        "code", 0.99),
    ".v":    ("text/x-verilog",                      "Verilog source",    "code", 0.99),
    ".vhdl": ("text/x-vhdl",                        "VHDL source",       "code", 0.99),
    ".jl":   ("text/x-julia",                       "Julia source",      "code", 0.99),
    ".f90":  ("text/x-fortran",                     "Fortran source",    "code", 0.99),
    ".f":    ("text/x-fortran",                     "Fortran source",    "code", 0.99),
    ".m":    ("text/x-objectivec",                   "Objective-C",      "code", 0.99),
    ".mm":   ("text/x-objectivec",                  "Objective-C++",     "code", 0.99),
    ".s":    ("text/x-asm",                         "Assembly",          "code", 0.99),
    ".asm":  ("text/x-asm",                         "Assembly",          "code", 0.99),
    ".a":    ("application/x-archive",               "Static library",    "binary", 0.95),
    ".o":    ("application/x-object",                "Object file",       "binary", 0.95),
    ".so":   ("application/x-sharedlib",             "Shared library",    "binary", 0.95),
    ".dylib":("application/x-sharedlib",             "Dynamic library",   "binary", 0.95),
    ".dll":  ("application/x-msdownload",           "Windows DLL",       "binary", 0.95),
    ".exe":  ("application/x-msdownload",           "Windows executable","binary", 0.99),
    # Config / DevOps
    ".sh":   ("text/x-shellscript",                 "Shell script",      "code", 0.99),
    ".bash": ("text/x-shellscript",                 "Bash script",       "code", 0.99),
    ".zsh":  ("text/x-shellscript",                 "Zsh script",        "code", 0.99),
    ".fish": ("text/x-shellscript",                 "Fish script",       "code", 0.99),
    ".ps1":  ("text/x-powershell",                   "PowerShell",        "code", 0.99),
    ".psm1": ("text/x-powershell",                   "PowerShell module", "code", 0.99),
    ".bat":  ("text/x-batch",                       "Windows batch",     "code", 0.99),
    ".cmd":  ("text/x-batch",                       "Windows batch",     "code", 0.99),
    ".cmake":("text/x-cmake",                       "CMake",             "code", 0.99),
    "CMakeLists.txt": ("text/x-cmake",              "CMake config",      "code", 0.99),
    ".dockerfile":("text/x-dockerfile",             "Dockerfile",        "code", 0.99),
    "dockerfile":("text/x-dockerfile",             "Dockerfile",        "code", 0.99),
    "Dockerfile":("text/x-dockerfile",             "Dockerfile",        "code", 0.99),
    "makefile":  ("text/x-makefile",              "Makefile",          "config", 0.99),
    "Makefile":  ("text/x-makefile",              "Makefile",          "config", 0.99),
    ".gitignore":    ("text/plain",                 "Gitignore",         "text", 0.95),
    ".dockerignore": ("text/plain",                 "Dockerignore",      "text", 0.95),
    ".gitattributes":("text/plain",                 "Git attributes",    "text", 0.95),
    ".editorconfig": ("text/plain",                 "EditorConfig",      "text", 0.95),
    ".bashrc":       ("text/x-shellscript",        "Bashrc",           "code", 0.95),
    ".zshrc":        ("text/x-shellscript",        "Zshrc",            "code", 0.95),
    ".profile":      ("text/x-shellscript",        "Shell profile",    "code", 0.9),
    ".env":          ("text/x-shellscript",        "Env file",         "config", 0.8),
    ".toml": ("application/toml",                   "TOML config",       "data", 0.99),
    ".ini":  ("text/x-ini",                         "INI config",        "config", 0.95),
    ".cfg":  ("text/x-ini",                         "Config file",       "config", 0.8),
    ".conf": ("text/plain",                         "Config file",       "config", 0.7),
    ".env":  ("text/x-shellscript",                 "Env file",          "config", 0.8),
    ".properties": ("text/x-properties",            "Java properties",  "config", 0.95),
    ".tf":   ("text/x-hcl",                         "Terraform",         "config", 0.99),
    ".tfvars": ("text/x-hcl",                       "Terraform vars",    "config", 0.99),
    ".hcl":  ("text/x-hcl",                         "HCL",               "config", 0.99),
    ".proto":("application/x-protobuf",              "Protobuf",          "code", 0.99),
    # Text / Docs
    ".md":   ("text/markdown",                      "Markdown",          "text", 0.99),
    ".rst":  ("text/x-rst",                         "reStructuredText",  "text", 0.99),
    ".tex":  ("text/x-tex",                         "LaTeX",             "text", 0.99),
    ".txt":  ("text/plain",                         "Plain text",        "text", 0.99),
    ".log":  ("text/plain",                         "Log file",          "text", 0.9),
    ".diff": ("text/x-diff",                        "Diff/patch",        "text", 0.99),
    ".patch":("text/x-diff",                        "Patch file",        "text", 0.99),
    ".man":  ("text/troff",                         "Man page",          "text", 0.9),
    # Special filenames
    "makefile":      ("text/x-makefile",            "Makefile",          "config", 0.99),
    "Makefile":      ("text/x-makefile",            "Makefile",          "config", 0.99),
    ".gitignore":    ("text/plain",                 "Gitignore",         "text", 0.95),
    ".dockerignore": ("text/plain",                 "Dockerignore",      "text", 0.95),
    ".gitattributes":("text/plain",                 "Git attributes",    "text", 0.95),
    ".editorconfig": ("text/plain",                 "EditorConfig",      "text", 0.95),
    "license":       ("text/plain",                 "License file",      "text", 0.95),
    "license.txt":   ("text/plain",                 "License file",      "text", 0.95),
    ".lock":         ("application/json",           "Lock file",         "data", 0.9),
    ".map":          ("application/json",           "Source map",        "data", 0.8),
    "package.json":  ("application/json",           "npm package.json",  "data", 0.99),
    "tsconfig.json": ("application/json",           "TypeScript config", "data", 0.99),
    ".prettierrc":   ("application/json",           "Prettier config",  "data", 0.9),
    ".eslintrc":     ("application/json",           "ESLint config",     "data", 0.9),
    ".flake8":       ("text/plain",                 "Flake8 config",     "config", 0.9),
    "setup.py":      ("text/x-python",             "Python setup",      "code", 0.99),
    "pyproject.toml":("text/x-python",             "Python project config","data", 0.99),
    "poetry.lock":   ("application/json",           "Poetry lock",       "data", 0.9),
    "requirements.txt": ("text/x-python",          "Python requirements","text", 0.95),
    "pipfile":       ("text/x-toml",               "Pipfile",           "data", 0.9),
    "pipfile.lock":  ("application/json",           "Pipfile.lock",      "data", 0.9),
    # Databases
    ".db":   ("application/vnd.sqlite3",            "SQLite database",   "database", 0.95),
    ".sqlite":("application/vnd.sqlite3",            "SQLite database",   "database", 0.95),
    ".sqlite3":("application/vnd.sqlite3",           "SQLite database",   "database", 0.95),
    # Other
    ".iso":  ("application/x-iso9660-image",         "ISO image",         "disk", 0.95),
    ".img":  ("application/x-disk-image",            "Disk image",        "disk", 0.9),
    ".vdi":  ("application/x-vdi",                  "VirtualBox disk",   "disk", 0.95),
    ".vmdk": ("application/x-vmdk",                  "VMware disk",       "disk", 0.95),
    ".qcow2":("application/x-qcow2",                 "QEMU disk",         "disk", 0.95),
    ".dmg":  ("application/x-apple-diskimage",       "Apple DMG",         "disk", 0.95),
    ".pcap": ("application/vnd.tcpdump.capture",    "Packet capture",    "data", 0.99),
    ".pcapng":("application/vnd.tcpdump.capture",  "Packet capture (ng)","data", 0.99),
    ".wasm": ("application/wasm",                    "WebAssembly",       "binary", 0.99),
    ".wat":  ("application/wat",                     "WebAssembly text",  "code", 0.95),
    ".dex":  ("application/vnd.android.dex",          "Android DEX",       "binary", 0.99),
}


# ─── Shebang Patterns (higher confidence than content heuristics) ───────────

SHEBANG_MAP: dict[str, tuple[str, str, str, float]] = {
    "#!/bin/bash":           ("text/x-shellscript", "Bash script",      "code", 0.99),
    "#!/bin/sh":             ("text/x-shellscript", "POSIX shell",     "code", 0.99),
    "#!/usr/bin/bash":       ("text/x-shellscript", "Bash script",      "code", 0.99),
    "#!/usr/bin/env python": ("text/x-python",      "Python script",   "code", 0.99),
    "#!/usr/bin/env python3":("text/x-python",      "Python 3 script", "code", 0.99),
    "#!/usr/bin/python":    ("text/x-python",      "Python script",   "code", 0.99),
    "#!/usr/bin/python3":   ("text/x-python",      "Python 3 script", "code", 0.99),
    "#!/usr/bin/env node":   ("text/x-javascript",  "Node.js script", "code", 0.99),
    "#!/usr/bin/node":       ("text/x-javascript",  "Node.js script", "code", 0.99),
    "#!/usr/bin/env ruby":   ("text/x-ruby",        "Ruby script",     "code", 0.99),
    "#!/usr/bin/ruby":       ("text/x-ruby",        "Ruby script",     "code", 0.99),
    "#!/usr/bin/env perl":   ("text/x-perl",        "Perl script",     "code", 0.99),
    "#!/usr/bin/perl":       ("text/x-perl",        "Perl script",     "code", 0.99),
    "#!/usr/bin/env php":    ("text/x-php",         "PHP script",      "code", 0.99),
    "#!/usr/bin/php":        ("text/x-php",         "PHP script",      "code", 0.99),
    "#!/usr/bin/env lua":    ("text/x-lua",         "Lua script",      "code", 0.99),
    "#!/usr/bin/lua":        ("text/x-lua",         "Lua script",      "code", 0.99),
    "#!/usr/bin/env nodejs": ("text/x-javascript",  "Node.js script", "code", 0.99),
    "#!/bin/fish":           ("text/x-shellscript", "Fish script",     "code", 0.99),
    "#!/usr/bin/fish":       ("text/x-shellscript", "Fish script",     "code", 0.99),
    "#!/usr/bin/env zsh":    ("text/x-shellscript", "Zsh script",      "code", 0.99),
    "#!/usr/bin/env powershell": ("text/x-powershell","PowerShell",    "code", 0.99),
    "#!/usr/bin/pwsh":       ("text/x-powershell",  "PowerShell Core", "code", 0.99),
    "#!/usr/bin/python":     ("text/x-python",      "Python script",  "code", 0.99),
    "#!/bin/python":         ("text/x-python",      "Python script",  "code", 0.99),
    "#!/bin/python3":        ("text/x-python",      "Python 3 script", "code", 0.99),
    "#!/usr/local/bin/python":("text/x-python",     "Python script",   "code", 0.99),
}


# ─── Content Patterns (lowest priority — only when no extension or shebang) ─

CONTENT_PATTERNS: list[tuple[str, str, str, str, float]] = [
    # (regex, mime, label, category, confidence)

    # Markdown — must check before HTML since MD can contain <>
    (r"^# .+$",                    "text/markdown", "Markdown (H1)",   "text", 0.85),
    (r"^## .+$",                   "text/markdown", "Markdown (H2+)",  "text", 0.85),
    (r"^\*\*[^*]+\*\*",          "text/markdown", "Markdown (bold)",  "text", 0.8),

    # HTML — must check before JSON (since < looks like JSX)
    (r"^<!DOCTYPE html>",          "text/html",      "HTML (DOCTYPE)",  "markup", 0.99),
    (r"^<html",                    "text/html",      "HTML",            "markup", 0.95),
    (r"^<head",                    "text/html",      "HTML",            "markup", 0.95),
    (r"^<body",                    "text/html",      "HTML",            "markup", 0.95),
    (r"^<div",                     "text/html",      "HTML",            "markup", 0.9),
    (r"^<span",                    "text/html",      "HTML",            "markup", 0.9),
    (r"^<p ",                      "text/html",      "HTML",            "markup", 0.9),
    (r"^<script",                  "text/html",      "HTML+JS",         "markup", 0.9),

    # JSON — check after HTML and Markdown
    (r"^\s*\{\s*\"",               "application/json", "JSON (object)", "data", 0.9),
    (r"^\s*\[\s*\{",               "application/json", "JSON (array)",  "data", 0.9),

    # Jupyter
    (r'"cells":',                  "application/x-ipynb+json", "Jupyter Notebook", "notebook", 0.95),
    (r'"cell_type":',              "application/x-ipynb+json", "Jupyter Notebook", "notebook", 0.95),

    # SQL
    (r"^SELECT\s+",                "text/x-sql",     "SQL",             "data", 0.9),
    (r"^INSERT\s+INTO",            "text/x-sql",     "SQL",             "data", 0.9),
    (r"^UPDATE\s+",                "text/x-sql",     "SQL",             "data", 0.9),
    (r"^DELETE\s+FROM",           "text/x-sql",     "SQL",             "data", 0.9),
    (r"^CREATE\s+TABLE",          "text/x-sql",     "SQL DDL",         "data", 0.9),
    (r"^ALTER\s+TABLE",          "text/x-sql",     "SQL DDL",         "data", 0.9),

    # XML
    (r"^\s*<\?xml\s",             "application/xml", "XML",            "data", 0.99),

    # Rust
    (r"^use \w+;",                 "text/x-rust",    "Rust",           "code", 0.85),
    (r"^fn \w+\(",                 "text/x-rust",    "Rust",           "code", 0.85),
    (r"^impl\s+\w+",               "text/x-rust",    "Rust",           "code", 0.85),
    (r"^struct \w+",               "text/x-rust",    "Rust",           "code", 0.85),
    (r"^enum \w+",                 "text/x-rust",    "Rust",           "code", 0.85),

    # Go
    (r"^package \w+",             "text/x-go",      "Go",             "code", 0.95),
    (r"^import\s+\(",              "text/x-go",      "Go",             "code", 0.9),

    # Java / C# namespace
    (r"^package \w+;",             "text/x-java",    "Java package",   "code", 0.9),

    # Python (module-level)
    (r"^import \w+",               "text/x-python",  "Python import",  "code", 0.85),
    (r"^from \w+ import",          "text/x-python",  "Python import",  "code", 0.85),

    # JS/TS
    (r"^const \w+\s*=",            "text/x-javascript", "JavaScript",   "code", 0.85),
    (r"^let \w+\s*=",              "text/x-javascript", "JavaScript",   "code", 0.85),
    (r"^export\s+(default|const|function|class)",
                                     "text/x-javascript", "JS/TS module", "code", 0.85),

    # CSS
    (r"^[.#]\w+\s*\{",             "text/css",       "CSS",            "style", 0.9),
    (r"^@import\s+",              "text/css",       "CSS",            "style", 0.9),
    (r"^@media\s+",               "text/css",       "CSS",            "style", 0.9),
    (r"^@keyframes\s+",           "text/css",       "CSS",            "style", 0.9),
]


# ─── Category Map ──────────────────────────────────────────────────────────

CATEGORY_MAP: dict[str, str] = {
    "image/": "image",
    "video/": "video",
    "audio/": "audio",
    "text/markdown": "text",
    "text/plain": "text",
    "text/x-rst": "text",
    "text/x-tex": "text",
    "application/json": "data",
    "application/xml": "data",
    "text/x-yaml": "data",
    "application/toml": "data",
    "application/graphql": "data",
    "application/x-ipynb+json": "notebook",
    "application/pdf": "document",
    "application/msword": "document",
    "application/vnd.openxmlformats": "document",
    "application/vnd.ms-excel": "document",
    "application/vnd.ms-powerpoint": "document",
    "application/x-msoffice": "document",
    "text/rtf": "document",
    "application/zip": "archive",
    "application/x-7z-compressed": "archive",
    "application/x-bzip2": "archive",
    "application/gzip": "archive",
    "application/x-rar": "archive",
    "application/x-tar": "archive",
    "application/x-xz": "archive",
    "application/zstd": "archive",
    "application/x-compress": "archive",
    "application/x-lzh": "archive",
    "application/vnd.sqlite3": "database",
    "application/x-executable": "binary",
    "application/x-msdownload": "binary",
    "application/x-mach-binary": "binary",
    "application/x-shellscript": "code",
    "text/x-python": "code",
    "text/x-javascript": "code",
    "text/x-typescript": "code",
    "text/x-jsx": "code",
    "text/x-tsx": "code",
    "text/x-rust": "code",
    "text/x-go": "code",
    "text/x-java": "code",
    "text/x-c": "code",
    "text/x-cpp": "code",
    "text/x-swift": "code",
    "text/x-kotlin": "code",
    "text/x-scala": "code",
    "text/x-ruby": "code",
    "text/x-php": "code",
    "text/x-perl": "code",
    "text/x-lua": "code",
    "text/x-r": "code",
    "text/x-dart": "code",
    "text/x-clojure": "code",
    "text/x-haskell": "code",
    "text/x-elixir": "code",
    "text/x-erlang": "code",
    "text/x-ocaml": "code",
    "text/x-nim": "code",
    "text/x-fortran": "code",
    "text/x-objectivec": "code",
    "text/x-julia": "code",
    "text/x-asm": "code",
    "text/x-verilog": "code",
    "text/x-vhdl": "code",
    "application/x-protobuf": "code",
    "text/x-dockerfile": "code",
    "text/x-cmake": "code",
    "text/x-hcl": "code",
    "text/html": "markup",
    "text/css": "style",
    "text/x-scss": "style",
    "text/x-sass": "style",
    "text/x-less": "style",
}


@dataclass
class FileTypeResult:
    mime: str
    label: str
    category: str
    confidence: float
    is_binary: bool
    is_text: bool
    language: Optional[str] = None
    detection_method: str = "unknown"  # 'extension' | 'shebang' | 'magic' | 'content'

    def to_dict(self) -> dict:
        return {
            "mime": self.mime,
            "label": self.label,
            "category": self.category,
            "confidence": round(self.confidence, 3),
            "is_binary": self.is_binary,
            "is_text": self.is_text,
            "language": self.language,
            "detection_method": self.detection_method,
        }


class MagikaLite:
    """
    Pure-Python Magika-style file type detector.
    
    Detection order (priority):
      1. Extension (highest reliability)
      2. Shebang line (for scripts)
      3. Magic bytes (binary signatures)
      4. Content heuristics (last resort)
    
    Usage:
        m = MagikaLite()
        result = m.identify_path("/path/to/file.py")
        result = m.identify_bytes(data, filename="script.sh")
    """

    def __init__(self) -> None:
        # Pre-compile content patterns
        self._compiled_content: list[tuple[re.Pattern, str, str, str, float]] = [
            (re.compile(p, re.MULTILINE), mime, label, cat, conf)
            for p, mime, label, cat, conf in CONTENT_PATTERNS
        ]

    # ── Public API ─────────────────────────────────────────────────────────

    def identify_bytes(
        self, data: bytes, filename: str = ""
    ) -> FileTypeResult:
        """Detect file type from raw bytes."""
        if not data:
            return self._unknown(is_binary=True)

        # 1. Magic bytes (binary signatures) — only check if data looks binary
        magic_result = self._check_magic(data)
        if magic_result:
            return magic_result

        # 2. Extension — highest priority, most reliable
        ext_result = self._check_extension(filename)
        if ext_result:
            # Also check shebang in content for scripts
            shebang_result = self._check_shebang(data)
            if shebang_result and shebang_result.confidence > ext_result.confidence:
                return shebang_result
            return ext_result

        # 3. Shebang (no extension or extension unknown)
        shebang_result = self._check_shebang(data)
        if shebang_result:
            return shebang_result

        # 4. Content heuristics (last resort)
        content_result = self._check_content(data, filename)
        if content_result:
            return content_result

        # Fallback: check if binary
        if self._looks_binary(data):
            return self._unknown(is_binary=True)

        return self._unknown(is_binary=False)

    def identify_path(self, path: str | Path) -> FileTypeResult:
        """Detect file type from a file path."""
        p = Path(path)
        if not p.exists():
            return self._unknown(is_binary=True, label="not found")

        try:
            with open(p, "rb") as f:
                header = f.read(8192)
        except PermissionError:
            return self._unknown(is_binary=True, label="permission denied")

        return self.identify_bytes(header, p.name)

    def identify_batch(
        self, paths: list[str | Path]
    ) -> dict[str, FileTypeResult]:
        """Detect file types for multiple files."""
        return {str(p): self.identify_path(p) for p in paths}

    # ── Internal Detection Methods ────────────────────────────────────────

    def _check_extension(self, filename: str) -> Optional[FileTypeResult]:
        """Check by file extension (highest priority)."""
        name = filename.lower()
        
        # Try full filename match first (e.g. Dockerfile, Makefile, .gitignore)
        basename = Path(name).name  # Get the actual filename without directory
        if basename in EXT_MAP:
            mime, label, cat, conf = EXT_MAP[basename]
            return FileTypeResult(
                mime=mime, label=label, category=cat,
                confidence=conf, is_binary=False,
                is_text=cat not in ("binary", "image", "video", "audio", "archive", "database", "disk"),
                language=self._extract_language(mime),
                detection_method="extension",
            )
        
        # Try single/double extensions
        suffixes = list(Path(name).suffixes)
        for suffix in reversed(suffixes):
            if suffix in EXT_MAP:
                mime, label, cat, conf = EXT_MAP[suffix]
                return FileTypeResult(
                    mime=mime, label=label, category=cat,
                    confidence=conf, is_binary=False,
                    is_text=cat not in ("binary", "image", "video", "audio", "archive", "database", "disk"),
                    language=self._extract_language(mime),
                    detection_method="extension",
                )
        return None

    def _check_shebang(self, data: bytes) -> Optional[FileTypeResult]:
        """Check for shebang line."""
        try:
            text = data[:256].decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return None

        for shebang, (mime, label, cat, conf) in SHEBANG_MAP.items():
            if text.startswith(shebang):
                return FileTypeResult(
                    mime=mime, label=label, category=cat,
                    confidence=conf, is_binary=False, is_text=True,
                    language=self._extract_language(mime),
                    detection_method="shebang",
                )
        return None

    def _check_magic(self, data: bytes) -> Optional[FileTypeResult]:
        """Check binary magic bytes."""
        for magic, offset, mime, label in BINARY_SIGNATURES:
            if len(data) > offset + len(magic):
                if data[offset:offset + len(magic)] == magic:
                    cat = self._mime_to_category(mime)
                    return FileTypeResult(
                        mime=mime, label=label, category=cat,
                        confidence=0.95, is_binary=True, is_text=False,
                        detection_method="magic",
                    )
        return None

    def _check_content(
        self, data: bytes, filename: str
    ) -> Optional[FileTypeResult]:
        """Content-based heuristics (last resort)."""
        if not data:
            return None

        # Check if it looks like text at all
        if self._looks_binary(data):
            return None

        try:
            text = data[:4096].decode("utf-8", errors="ignore")
        except Exception:
            return None

        best: tuple[float, str, str, str, str] = (0.0, "", "", "", "")

        for pat, mime, label, cat, conf in self._compiled_content:
            if pat.search(text):
                if conf > best[0]:
                    best = (conf, mime, label, cat, mime)

        if best[0] > 0:
            mime = best[4]
            return FileTypeResult(
                mime=mime, label=best[2], category=best[3],
                confidence=best[0], is_binary=False, is_text=True,
                language=self._extract_language(mime),
                detection_method="content",
            )

        return None

    def _looks_binary(self, data: bytes) -> bool:
        """Check if bytes appear to be binary (contain null bytes)."""
        return b"\x00" in data[:512]

    def _mime_to_category(self, mime: str) -> str:
        """Map MIME type to category."""
        for prefix, cat in CATEGORY_MAP.items():
            if mime.startswith(prefix) or prefix in mime:
                return cat
        return "binary"

    def _extract_language(self, mime: str) -> Optional[str]:
        """Extract language name from MIME type."""
        lang_map: dict[str, str] = {
            "text/x-python": "python",
            "text/x-javascript": "javascript",
            "text/x-typescript": "typescript",
            "text/x-tsx": "typescript",
            "text/x-jsx": "javascript",
            "text/x-rust": "rust",
            "text/x-go": "go",
            "text/x-java": "java",
            "text/x-c": "c",
            "text/x-cpp": "cpp",
            "text/x-swift": "swift",
            "text/x-kotlin": "kotlin",
            "text/x-scala": "scala",
            "text/x-ruby": "ruby",
            "text/x-php": "php",
            "text/x-perl": "perl",
            "text/x-lua": "lua",
            "text/x-r": "r",
            "text/x-dart": "dart",
            "text/x-clojure": "clojure",
            "text/x-haskell": "haskell",
            "text/x-elixir": "elixir",
            "text/x-erlang": "erlang",
            "text/x-shellscript": "shell",
            "text/x-ocaml": "ocaml",
            "text/x-nim": "nim",
            "text/x-fortran": "fortran",
            "text/x-objectivec": "objective-c",
            "text/x-julia": "julia",
            "text/x-asm": "assembly",
            "text/x-sql": "sql",
            "text/x-dockerfile": "dockerfile",
            "text/x-hcl": "hcl",
            "text/x-cmake": "cmake",
            "application/x-protobuf": "protobuf",
            "application/graphql": "graphql",
            "text/x-powershell": "powershell",
            "text/x-batch": "batch",
        }
        return lang_map.get(mime)

    def _unknown(
        self, is_binary: bool, label: str = "unknown"
    ) -> FileTypeResult:
        return FileTypeResult(
            mime="application/octet-stream",
            label=label,
            category="binary" if is_binary else "text",
            confidence=0.0,
            is_binary=is_binary,
            is_text=not is_binary,
            detection_method="none",
        )


# ─── CLI ──────────────────────────────────────────────────────────────────

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: nopus_magika.py <file> [file ...]")
        print("       nopus_magika.py --batch <dir>")
        print("       nopus_magika.py --stdin < file")
        sys.exit(1)

    m = MagikaLite()

    if sys.argv[1] == "--stdin":
        data = sys.stdin.buffer.read()
        import os
        r = m.identify_bytes(data)
        print(json.dumps(r.to_dict(), indent=2))
        return

    if sys.argv[1] == "--batch" and len(sys.argv) >= 3:
        d = sys.argv[2]
        for p in sorted(Path(d).rglob("*")):
            if p.is_file():
                r = m.identify_path(p)
                p_str = str(p)
                r_mime = r.mime
                r_dm = r.detection_method
                r_label = r.label
                r_cat = r.category
                print(f"{p_str}: {r_mime} [{r_dm}] -- {r_label} ({r_cat})")
        return

    for path in sys.argv[1:]:
        r = m.identify_path(path)
        print(f"{path}: {r.mime} [{r.detection_method}] -- {r.label} ({r.category})")


if __name__ == "__main__":
    main()

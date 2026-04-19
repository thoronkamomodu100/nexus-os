#!/usr/bin/env python3
"""
Apply large file fix to NEXUS_OS_v3.py claude_modify_file method.
Changes: for files >50KB, use 400-char snippet + 60s timeout + targeted instruction.
"""
import re

bak_path = "/Users/a/NEXUS_OS/NEXUS_OS_v3.py.bak2"
bak2_path = "/Users/a/NEXUS_OS/NEXUS_OS_v3.py.bak"
output_path = "/Users/a/NEXUS_OS/NEXUS_OS_v3.py"

# Use bak2 if bak has been overwritten, else bak
source = bak2_path if __import__("pathlib").Path(bak2_path).exists() else bak_path
content = open(source).read()

# Find the claude_modify_file method and replace the large file handling
old_block = '''        timeout = 120
        snippet = original_content

        # For large files, send only first 800 chars (enough to identify the code structure)
        if file_size > 50000:
            snippet = original_content[:800]
            timeout = 180

        prompt = f"""You are improving: {file_name} ({file_size} chars total)

INSTRUCTION: {improvement_instruction}

FOCUS AREAS: {focus_str}

CODE TO IMPROVE (first {len(snippet)} chars):
```
{snippet}
```

RULES:
1. Return the improved code in a ```python code block
2. Preserve all existing functionality
3. Make specific improvements in the focus areas
4. Keep the code runnable

Return format:
```python
# {file_name}
[improved code]
```
"""'''

new_block = '''        timeout = 120
        snippet = original_content

        # For large files (>50KB): use targeted 400-char snippet + shorter timeout
        # Avoids Claude Code timeout on large files like NEXUS_OS_v3.py (200KB+)
        if file_size > 50000:
            improvement_instruction = instruction or (
                f"Improve this Python code. Focus on: {focus_str}. "
                "Make ONE targeted improvement. Return ONLY the improved section "
                "in a python code block. Keep the rest unchanged."
            )
            snippet = original_content[:400]
            timeout = 60

            prompt = f"""You are improving: {file_name} ({file_size} chars total)

INSTRUCTION: {improvement_instruction}

FOCUS AREAS: {focus_str}

CODE TO IMPROVE (first {len(snippet)} chars):
```
{snippet}
```

RULES:
1. Return the improved code in a ```python code block
2. Preserve all existing functionality
3. Make ONE targeted improvement
4. Keep the code runnable

Return format:
```python
# {file_name}
[improved code]
```
"""
        else:
            prompt = f"""You are improving: {file_name} ({file_size} chars total)

INSTRUCTION: {improvement_instruction}

FOCUS AREAS: {focus_str}

CODE TO IMPROVE (first {len(snippet)} chars):
```
{snippet}
```

RULES:
1. Return the improved code in a ```python code block
2. Preserve all existing functionality
3. Make specific improvements in the focus areas
4. Keep the code runnable

Return format:
```python
# {file_name}
[improved code]
```
"""'''

if old_block in content:
    new_content = content.replace(old_block, new_block, 1)
    print(f"✓ Found and replaced old block ({len(old_block)} chars → {len(new_block)} chars)")
else:
    print("✗ Old block not found. Searching...")
    # Try to find the method
    idx = content.find("def claude_modify_file")
    if idx >= 0:
        print(f"  Method found at index {idx}")
        # Find the relevant section
        snippet_area = content[idx:idx+2000]
        print(f"  Method start (first 500 chars): {snippet_area[:500]}")
    print("ERROR: Could not apply fix automatically")
    exit(1)

# Verify syntax
import ast
try:
    ast.parse(new_content)
    print("✓ New content has valid Python syntax")
except SyntaxError as e:
    print(f"✗ SyntaxError at line {e.lineno}: {e.msg}")
    exit(1)

open(output_path, "w").write(new_content)
print(f"✓ Written to {output_path}")
print(f"  File size: {len(new_content)} bytes ({new_content.count(chr(10))} lines)")

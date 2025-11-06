---
Description: Analyze core_logic.py to identify functions performing file I/O operations (reading/writing files, checking existence, moving files) that could potentially be moved to utils.py. Document the findings.
Implementation File: N/A
Test File: N/A
Output File: docs/core_logic_io_analysis.txt
Status: pending
---

# Task: Identify File I/O in core_logic.py

1. Read the contents of `autotype_mcp_server/src/core_logic.py`.
2. Identify all functions that perform file system operations such as:
    - `open()`
    - `os.path.exists()`
    - `os.makedirs()`
    - `os.listdir()`
    - `shutil.move()`
    - `json.load()`, `json.dump()` (when used with file handles)
    - `yaml.safe_load()`, `yaml.dump()` (when used with file handles)
3. List the names of these functions and a brief description of the file operation they perform.
4. Write this list to a new file: `docs/core_logic_io_analysis.txt`. 
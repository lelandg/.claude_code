# Working with Files Across Directories

Reference for file operations and cross-directory workflows.

## Core Principles
- Never use `cd` commands: Stay in the current working directory and use absolute paths
- Always use full paths: Specify complete paths like `/path/to/project/file.py`
- Batch operations: Call multiple tools in parallel when searching different locations

## Tool-Specific Guidelines

### For File Searches
- Use `Grep` with the `path` parameter: `Grep(pattern="TODO", path="/path/to/project")`
- Use `Glob` with the `path` parameter: `Glob(pattern="*.py", path="/path/to/project/src")`
- Combine patterns for efficiency: `Glob(pattern="**/*.{py,js,ts}", path="/absolute/path")`

### For File Operations
- Reading: Always provide full path: `Read(file_path="/path/to/project/src/main.py")`
- Listing: Use absolute paths: `LS(path="/path/to/project/src")`
- Editing: Full paths required: `Edit(file_path="/full/path/to/file.py", ...)`

### For Bash Commands
- Use absolute paths in commands: `python3 /path/to/project/script.py`
- For wildcards: `ls -la /path/to/repos/*/README.md`
- For git operations: `git -C /path/to/project status`

## Efficiency Tips
1. **Parallel searches**: When searching multiple directories, batch the tool calls in a single message
2. **Path variables**: When working repeatedly with a directory, note its absolute path at the start
3. **Avoid path traversal**: Use direct absolute paths instead of `../../../` constructions
4. **Git repository operations**: Use `git -C /absolute/path` to run git commands in other directories

## Examples
```bash
# Good - uses absolute path
Grep(pattern="class.*Controller", path="/path/to/project")

# Bad - requires changing directory
cd /path/to/project && grep -r "class.*Controller"

# Good - parallel operations with absolute paths
[
  Glob(pattern="*.md", path="/path/to/project1"),
  Glob(pattern="*.md", path="/path/to/project2")
]

# Good - git operation without changing directory
git -C /path/to/project log --oneline -5
```

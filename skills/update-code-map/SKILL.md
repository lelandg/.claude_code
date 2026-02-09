---
name: update-code-map
description: Update or maintain the CodeMap.md file based on recent code changes. Use this skill when users ask to update the code map, refresh documentation line numbers, document new files, or keep the codebase navigation guide current. Triggers on requests like "update the code map", "refresh CodeMap", "the code map is outdated", or "update line numbers in documentation".
---

# Update Code Map

Update or create a comprehensive CodeMap.md file for navigating the codebase.

## What This Skill Does

This skill creates or updates the `Docs/CodeMap.md` file, which serves as the definitive navigation guide for the codebase. It provides:
- Exact line numbers for all classes, methods, and functions
- Visual architecture diagrams
- Cross-module dependencies
- Quick navigation to primary entry points

## Process Overview

### 1. Check Current State

First, determine what needs to be done:

```bash
# Check if CodeMap exists and when it was last updated
if [ -f Docs/CodeMap.md ]; then
    head -5 Docs/CodeMap.md
    echo "CodeMap exists. Checking for updates needed..."
else
    echo "No CodeMap found. Will create new one."
fi

# Get current timestamp for the update
date +"%Y-%m-%d %H:%M:%S"
```

### 2. Analyze Recent Changes

If updating an existing CodeMap:

```bash
# Get the last update timestamp from CodeMap
# Then check git history since that date
git log --since="YYYY-MM-DD HH:MM:SS" --name-status --oneline

# Get summary of changes
git diff --stat HEAD~10
```

Identify:
- New files added
- Files deleted or renamed
- Files with significant changes (structure, classes, methods)

### 3. Detect Programming Languages

Scan the project to identify primary languages:

```bash
# Find language distribution
find . -type f -name "*.py" | wc -l    # Python
find . -type f -name "*.cs" | wc -l    # C#
find . -type f -name "*.xaml" | wc -l  # XAML
find . -type f -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" | wc -l  # JavaScript/TypeScript
```

### 4. Apply Language-Specific Guidelines

Based on detected languages, reference the appropriate guideline files:

**Available Language Guidelines:**
- `@update-code-map/python-guidelines.md` - For Python projects
- `@update-code-map/csharp-guidelines.md` - For C# projects
- `@update-code-map/xaml-guidelines.md` - For XAML files
- `@update-code-map/javascript-guidelines.md` - For JavaScript/TypeScript

**How to use these guidelines:**
1. Read the relevant language guideline file(s) based on project languages
2. Follow the table structures and documentation patterns specified
3. Use the language-specific sections (properties, methods, etc.) as defined
4. Document language-specific patterns (async, generics, LINQ, etc.)

### 5. Follow Base Specification

**CRITICAL**: Always adhere to the base specification at:
- `@~/.claude/agents/specs/CLAUDE_CodeMap.md`

This specification defines:
- Required structure and section order
- Table of contents with line numbers
- Visual architecture diagrams
- Quality standards

### 6. Generate Visual Architecture Diagram

**MANDATORY BOX ALIGNMENT ALGORITHM:**

When creating ASCII diagrams, follow this EXACT algorithm:

```python
def create_box(lines):
    # Step 1: Find maximum line length
    max_length = max(len(line) for line in lines)

    # Step 2: Calculate box width (add 4 for borders and padding)
    box_width = max_length + 4

    # Step 3: Create borders
    top = "┌" + "─" * (box_width - 2) + "┐"
    bottom = "└" + "─" * (box_width - 2) + "┘"

    # Step 4: Create padded lines
    middle = []
    for line in lines:
        padding = " " * (box_width - len(line) - 4)
        middle.append("│ " + line + padding + " │")

    return [top] + middle + [bottom]
```

**Verification checklist:**
- [ ] All lines in a box have EXACT same character count
- [ ] Closing `│` aligns perfectly in same column
- [ ] Top and bottom borders have same length
- [ ] Boxes in same row have identical widths
- [ ] Used mathematical padding calculation, not visual estimation

### 7. Extract Code Elements with Line Numbers

For each significant file, extract:

**For Python:**
- Module-level: imports, constants, variables
- Classes: properties, methods (regular, @classmethod, @staticmethod, @property)
- Functions: module-level functions
- Data structures: @dataclass, NamedTuple, TypedDict

**For C#:**
- Namespaces, classes, interfaces, structs, enums, records
- Properties (auto, computed, init-only)
- Methods (regular, async, generic, extension)
- Events, delegates, constructors

**For XAML:**
- Root element properties
- Named elements (x:Name)
- Data bindings
- Resources (styles, templates, brushes)
- Event handlers

**For JavaScript/TypeScript:**
- Imports/exports
- Classes, interfaces, types, enums
- Functions (regular, async, arrow)
- React: components, hooks, props, state
- Node.js: routes, middleware, controllers

### 8. Document Cross-File Dependencies

Track how modules/classes interact:

```markdown
## Cross-File Dependencies

### Authentication State
**Managed by**: `core/auth.py:45` (AuthManager class)
**Consumed by**:
- `gui/main_window.py:120` - Shows user info
- `api/endpoints.py:30` - Validates requests
- `middleware/auth.py:15` - JWT middleware
```

### 9. Update Line Number Tables of Contents

**CRITICAL TWO-PASS APPROACH:**

**Pass 1:** Generate all content
**Pass 2:** Count actual line numbers and update TOCs

```bash
# After writing Docs/CodeMap.md
# Read it back and count line numbers where ## sections appear
grep -n "^## " Docs/CodeMap.md

# Update the main TOC with these actual line numbers
```

**NEVER leave placeholder values** like `[ACTUAL_LINE]` in the final document.

### 10. Quality Assurance

Before finalizing, verify:

- [ ] Timestamp updated: `*Last Updated: YYYY-MM-DD HH:MM:SS*` (use `date +"%Y-%m-%d %H:%M:%S"`)
- [ ] All line numbers verified and accurate
- [ ] New files documented with line numbers
- [ ] Deleted files removed
- [ ] Cross-references validated
- [ ] Visual diagrams follow box alignment algorithm
- [ ] TOC has real line numbers (not placeholders)
- [ ] Language-specific patterns documented per guidelines
- [ ] Every public method/function has line number
- [ ] File sizes (line counts) included

## Required CodeMap Structure

Follow this exact order:

1. **Header** - Title and timestamp
2. **Table of Contents** - Main TOC with line numbers
3. **Quick Navigation** - Primary entry points
4. **Visual Architecture Overview** - ASCII diagram
5. **Project Structure** - Directory tree
6. **Core Configuration Files** - Config file listings
7. **Detailed Component Documentation** - File-by-file breakdown
8. **Cross-File Dependencies** - Module relationships
9. **Configuration Files** - Build/package configs
10. **Architecture Patterns** - Design patterns used
11. **Development Guidelines** - How to extend
12. **Performance Considerations** - Optimization notes

## Example Workflow

```bash
# 1. Get current timestamp
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

# 2. Check existing CodeMap
if [ -f Docs/CodeMap.md ]; then
    LAST_UPDATE=$(grep "Last Updated:" Docs/CodeMap.md | head -1)
    echo "Last updated: $LAST_UPDATE"
fi

# 3. Scan for languages
echo "Detecting languages..."
PY_COUNT=$(find . -name "*.py" -type f | wc -l)
CS_COUNT=$(find . -name "*.cs" -type f | wc -l)
XAML_COUNT=$(find . -name "*.xaml" -type f | wc -l)
JS_COUNT=$(find . -name "*.js" -o -name "*.ts" -type f | wc -l)

echo "Python files: $PY_COUNT"
echo "C# files: $CS_COUNT"
echo "XAML files: $XAML_COUNT"
echo "JS/TS files: $JS_COUNT"

# 4. Read appropriate language guidelines
# (Based on detected languages, read the corresponding guideline files)

# 5. Extract file structure
tree -L 3 -I '__pycache__|node_modules|.venv*|bin|obj'

# 6. Generate CodeMap content
# (Follow base spec + language-specific guidelines)

# 7. Verify line numbers
grep -n "^## " Docs/CodeMap.md

# 8. Present to user for review
```

## Important Notes

- **Never guess dates** - Always use `date +"%Y-%m-%d %H:%M:%S"`
- **Verify line numbers** - Use `grep -n` or editor line counts
- **Mathematical box padding** - Calculate, don't estimate visually
- **Language-specific tables** - Use appropriate columns for each language
- **Two-pass TOC** - Generate content first, then update line numbers
- **Quality over speed** - Completeness and accuracy are critical

## Output

Present a summary when done:

```
Code Map Update Complete
========================

✓ Updated timestamp: YYYY-MM-DD HH:MM:SS
✓ Analyzed N files across M languages
✓ Documented X classes, Y methods, Z functions
✓ Created/updated visual architecture diagram
✓ Updated all line numbers in TOCs
✓ Verified all cross-references

Languages detected and documented:
- Python: N files
- C#: M files
- XAML: P files

CodeMap location: Docs/CodeMap.md
Total lines: NNNN
```

Ready for review!

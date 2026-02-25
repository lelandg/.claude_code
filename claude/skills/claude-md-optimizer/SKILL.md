---
name: claude-md-optimizer
description: Optimize CLAUDE.md files to reduce context loading and improve /resume times. Use when users mention slow /resume, CLAUDE.md being too long, reducing token usage, context optimization, or want to slim down their Claude Code instructions. Triggers on requests like "optimize CLAUDE.md", "my resume is slow", "CLAUDE.md is too big", "reduce context loading", or "slim down my instructions".
---

# CLAUDE.md Optimizer

Reduce always-loaded context by extracting rarely-used sections to on-demand reference files.

## Optimization Workflow

### 1. Analyze Current State

Count lines in existing CLAUDE.md files:
```bash
wc -l ~/.claude/CLAUDE.md ./CLAUDE.md
```

Read both files and identify sections by size and usage frequency.

### 2. Identify Extraction Candidates

See `references/extraction-checklist.md` for the full checklist.

**Quick heuristics:**
- Sections >50 lines used in <50% of sessions → Extract
- AWS/Cloud infrastructure details → Extract to `instructions/aws-{project}.md`
- Plan/template formats → Extract to `instructions/plan-templates.md`
- Credential management patterns → Extract to `instructions/credentials.md`
- Command reference that duplicates existing docs → Replace with pointer

### 3. Create Reference Directory

```bash
mkdir -p ~/.claude/instructions
```

### 4. Extract Sections

For each extraction candidate:
1. Create `~/.claude/instructions/{topic}.md` with the full content
2. Replace the section in CLAUDE.md with a brief pointer:
   ```markdown
   ## Topic Name
   For detailed {topic} documentation, see `~/.claude/instructions/{topic}.md`
   ```

### 5. Slim Project CLAUDE.md

For project-level files, also:
- Replace command lists with pointers to existing docs (e.g., `Scripts/*.md`)
- Remove deployment details that duplicate `Docs/*.md` files
- Keep: Overview, architecture, dev commands, key implementation details

### 6. Verify Results

```bash
wc -l ~/.claude/CLAUDE.md ~/.claude/instructions/*.md ./CLAUDE.md
```

**Target:** Core files under 200-300 lines each.

## Structure After Optimization

```
~/.claude/
├── CLAUDE.md                    # Core rules only (~200 lines)
└── instructions/                # Reference docs (loaded when needed)
    ├── aws-{project}.md         # AWS infrastructure
    ├── plan-templates.md        # Plan file format
    ├── credentials.md           # Secrets management
    └── file-operations.md       # File operation guidelines

project/
├── CLAUDE.md                    # Core project info (~200 lines)
└── (existing docs referenced, not duplicated)
```

## What to Keep in Core CLAUDE.md

**Always keep (high usage, critical):**
- User/contact info
- Date handling rules (CRITICAL)
- Security rules (condensed)
- Work procedures
- Local project conventions
- Development environment basics
- Brief references to instruction files

**Extract (low usage, high token cost):**
- Full AWS/cloud infrastructure details
- Complete plan file templates
- Detailed credential management patterns
- Extensive file operation examples
- Long command references

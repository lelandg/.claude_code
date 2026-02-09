# CLAUDE.md Extraction Checklist

Use this checklist to identify sections that should be extracted to reference files.

## High-Value Extraction Candidates

These section types typically have high token cost but low usage frequency:

| Section Type | Typical Size | Extract When... |
|--------------|--------------|-----------------|
| AWS/Cloud Infrastructure | 200-400 lines | Only needed for cloud work |
| API Reference | 100-300 lines | Only needed for API integration |
| Database Schemas | 50-200 lines | Only needed for DB work |
| Deployment Commands | 50-150 lines | Only needed for deploys |
| Plan/Template Formats | 100-200 lines | Reference material, rarely modified |
| Credential Management | 50-100 lines | Reference patterns, not daily use |
| Platform-Specific Notes | 50-100 lines | Only applies to subset of work |

## What to Keep in Core CLAUDE.md

Always keep these in the main file (high usage, critical):

- **Identity/Contact Info** - Always relevant, small
- **Date Handling Rules** - Critical, prevents errors
- **Security Rules (condensed)** - Safety-critical, brief version
- **Work Procedures** - Daily workflow guidance
- **Local Conventions** - Every file operation uses this
- **Development Environment** - Every session needs this
- **Project Locations** - Frequently referenced

## Extraction Decision Matrix

```
Is this section used in >50% of sessions?
├─ YES → Keep in core CLAUDE.md
└─ NO → Is it >50 lines?
         ├─ YES → Extract to references/
         └─ NO → Keep (low token cost)
```

## Reference File Naming

Use descriptive names matching the content:

| Content | Suggested Filename |
|---------|-------------------|
| AWS Infrastructure | `aws-{project}.md` |
| Plan Templates | `plan-templates.md` |
| Credential Patterns | `credentials.md` |
| File Operations | `file-operations.md` |
| API Documentation | `api-{service}.md` |
| Deployment Guide | `deployment.md` |

## Reference Pointer Format

After extraction, add a reference pointer in the core file:

```markdown
## AWS Infrastructure
For AWS ChameleonLabs infrastructure (Amplify, RDS, SES), see `~/.claude/instructions/aws-chameleonlabs.md`
```

Keep the pointer brief (1-2 lines) with just enough context to know when to read the full reference.

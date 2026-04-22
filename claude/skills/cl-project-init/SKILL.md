---
name: cl-project-init
description: >-
  Initialize a new company project from scratch. Use when creating any new project for
  YourCompany — SaaS web apps (Next.js), Python scripts/tools, or standalone libraries. Sets
  up directory structure, CLAUDE.md, .gitignore, .env.example, JetBrains IDE support, brand
  conventions, and gets you coding immediately. Triggers on "start a new project", "create a
  new CL project", "initialize a project", "new SaaS app", "set up a Python tool for CL",
  "scaffold a project".
---

# YourCompany Project Initializer

Spins up any YourCompany project with consistent structure, brand conventions, and tooling.

## Workflow

### Step 1: Gather Project Info

Ask for ONLY what's missing. If the user's message already provides it, skip asking.

**Required:**
- **Project name** (e.g., "QuickSort", "MarketWatch")
- **Project type**: `nextjs-saas` | `python` | `library`

**Infer these (only ask if genuinely ambiguous):**
- Short description → default to "A company [type] project"
- Needs database → default yes for SaaS, no for Python
- GitHub repo name → kebab-case of project name

Never ask about brand colors, fonts, or standard tooling — always the same.

### Step 2: Load the Reference

Read the relevant reference based on project type before creating files:
- **Next.js SaaS** → read `references/saas-nextjs.md`
- **Python** → read `references/python.md`
- **UI/frontend work** → also read `references/brand.md`

### Step 3: Create the Project

Run the project creation script to scaffold everything:

```bash
python3 ~/.claude/skills/cl-project-init/scripts/create_project.py \
  --name "PROJECT_NAME" \
  --type nextjs-saas|python|library \
  --description "SHORT DESCRIPTION" \
  [--path /target/directory]
```

The script creates the base structure. Then apply type-specific content from the reference file.

### Step 4: Finalize & Commit

```bash
cd [project-dir]
git init
git add .
git commit -m "chore: initialize [project-name] project"
```

### Step 5: Report Results

Give the user:
- List of created files/dirs
- Next steps (install deps, set env vars, GitHub repo creation, AWS Amplify setup)
- Any manual steps (e.g., creating GitHub repo, provisioning RDS, configuring Amplify)

## Quick Decisions

| Decision | Answer |
|----------|--------|
| Package manager | `npm` (consistent with CL main project) |
| Language | TypeScript, strict mode |
| CSS framework | Tailwind CSS with CL brand colors |
| Auth | NextAuth v5 |
| ORM | Prisma + PostgreSQL |
| Python version | 3.12 |
| `.env` | Always `.env.example`, never commit `.env` |
| IDE | JetBrains — covered by .gitignore, no extra files needed |

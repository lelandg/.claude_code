---
name: project-documenter
description: "Generate user-facing feature documentation, Google sitemap, and navigational site map for any project. Writes markdown docs to the project's docs directory, generates sitemap.xml for SEO, and updates .raginclude for RAG indexing. Uses parallel agents to document multiple feature areas simultaneously. For developer/technical docs (API endpoints, data models, error handling), use the technical-documenter skill instead. Triggers on: 'document this project', 'generate feature docs', 'write support documentation', 'create product docs', 'document all features', 'update project documentation', 'generate sitemap'."
---

# Project Documenter

Generate user-facing feature documentation, a Google sitemap, and a navigational site map for any project using parallel agents. Docs are written for end users — no technical/developer details. New docs are appended to `.raginclude` for RAG indexing. For developer documentation (API endpoints, data models, error handling), use the `technical-documenter` skill.

## Process

### Phase 1: Scout

Scan the project to build a feature map and establish conventions.

#### Step 1a: Detect Project Conventions

Before writing anything, determine the project's directory conventions:

1. **List the project root** — run `ls -la` at the project root
2. **Check for existing doc directories** — look for `docs/`, `Docs/`, `documentation/`, `doc/`
3. **Set `$DOCS_DIR`** — use whatever the project already has. If none exists, default to `Docs/`
4. **Check for existing feature docs** — list contents of `$DOCS_DIR/Features/` (or equivalent) to identify docs that already exist and will be overwritten

If existing docs are found, note them and inform the user which files will be replaced during the approval step.

#### Step 1b: Scan Source Files

Read these files (adapt to project structure):

1. **package.json** (or equivalent) — project name, description, dependencies
2. **Route/page files** — `app/**/page.tsx`, `pages/**/*.tsx`, `src/routes/**`
3. **API routes** — `app/api/**/route.ts`, `pages/api/**`
4. **Layouts & middleware** — `app/layout.tsx`, `middleware.ts`, `src/layouts/**`
5. **Context providers** — `src/context/**`, `app/providers.tsx`, `lib/providers/**`
6. **Schema** — `prisma/schema.prisma`, `**/models/**`, `src/services/db.ts`
7. **Existing docs** — `$DOCS_DIR/**/*.md`, `README.md`
8. **Product config** — `lib/products.ts`, `lib/config.ts`, `src/config/**`

#### Step 1c: Build Feature Map

From the scanned files, identify **feature areas** — groups of related user-facing functionality. Typical areas:

| Area | What to look for |
|------|-----------------|
| Authentication | Auth routes, sign-in/sign-up pages, password reset, OAuth providers |
| User Account | Profile, settings, preferences pages |
| Billing | Stripe routes, subscription pages, pricing |
| Products/Apps | Product pages, app dashboards, feature pages |
| Chat/AI | Chat components, AI routes, model config |
| Admin | Admin pages, admin API routes |
| API/Integrations | OAuth, webhooks, external API routes |

Also build a **route inventory** for sitemap generation — a list of every public route with:
- Path (e.g., `/dashboard`, `/inventory`)
- Page title or description
- Whether it requires authentication
- Associated source file

Present the feature map, route inventory, and any files that will be overwritten to the user for approval before proceeding.

### Phase 2: Document (parallel agents)

Spawn one `general-purpose` agent per feature area using the **Task tool**. Each agent:

1. **Reads** the relevant source files for its area
2. **Writes** one markdown file to `$DOCS_DIR/Features/` following the template in `references/doc-template.md`
3. Reports back with the file path written

**Dispatch pattern:**

```
Task tool call:
  subagent_type: "general-purpose"
  name: "doc-{area-slug}"
  description: "Document {area name} features"
  mode: "bypassPermissions"
  prompt: |
    You are documenting the {area name} features of {project name}.

    Read these files to understand the feature:
    {list of files for this area}

    Write a markdown documentation file to: {$DOCS_DIR/Features/area-name.md}
    Follow this structure exactly:

    # {Area Name}

    ## Overview
    Brief description of what this feature area does.

    ## Features
    ### {Feature 1}
    - What it does
    - How to use it
    - Available options/settings

    ### {Feature 2}
    ...

    ## Common Questions
    Q&A format — anticipate what users would ask.
```

Launch up to 4 agents in parallel. If more than 4 areas, batch them.

### Phase 3: Sitemap & Navigation

After all documentation agents complete, generate two outputs:

#### 3a: Google Sitemap

Generate a sitemap for search engine crawling. Auto-detect the framework:

**Next.js (App Router)** — Create `app/sitemap.ts`:
```typescript
import type { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://example.com';
  return [
    { url: baseUrl, lastModified: new Date(), changeFrequency: 'weekly', priority: 1.0 },
    // ... one entry per public route from the route inventory
  ];
}
```

**Static / other frameworks** — Create `public/sitemap.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{baseUrl}/</loc><lastmod>{date}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>
  <!-- one entry per public route -->
</urlset>
```

**Sitemap rules:**
- Only include public (non-authenticated) routes. Auth-required pages get lower priority (0.3) or are omitted depending on user preference.
- Use `NEXT_PUBLIC_SITE_URL` or equivalent env var for the base URL. If not set, leave a placeholder and warn the user.
- Set `lastModified` from git timestamps when available: `git log -1 --format="%cI" -- {source-file}`
- Landing/home page = priority 1.0, core feature pages = 0.8, secondary pages = 0.5

#### 3b: Site Navigation Doc (for RAG)

Generate `$DOCS_DIR/Features/site-navigation.md` — a human-readable navigational guide:

```markdown
# Site Navigation

> A guide to every page in {project name} and how to find what you need.

## Public Pages (no sign-in required)

### Home (`/`)
{What the landing page shows. Key actions available.}

### Pricing (`/pricing`)
{What's on this page.}

## App Pages (sign-in required)

### Dashboard (`/dashboard`)
{What users see here. Key widgets/actions. How to get here: sign in → lands here automatically.}

### Inventory (`/inventory`)
{What this page does. How to navigate here: bottom nav → Items.}

...

## Navigation Reference

| Page | Path | Access | Nav Location |
|------|------|--------|-------------|
| Dashboard | `/dashboard` | Signed in | Bottom nav → Home |
| Inventory | `/inventory` | Signed in | Bottom nav → Items |
| ... | ... | ... | ... |
```

This doc helps RAG-powered chat answer "where do I find X?" and "how do I get to Y?" questions.

### Phase 4: Index & RAG Integration

After all outputs are generated:

1. **Create index file** — Write `$DOCS_DIR/Features/README.md` listing all generated docs with one-line descriptions
2. **Update .raginclude** — Read the existing `.raginclude` file (or create one if it doesn't exist). Ensure glob patterns cover all generated docs:
   ```
   # Feature documentation
   $DOCS_DIR/Features/**/*.md
   ```
   - If the pattern already exists, skip.
   - If `.raginclude` exists but lacks the pattern, append it.
   - If `.raginclude` doesn't exist, create it with the pattern plus a header comment.
   - Also add any other doc output files (e.g., `$DOCS_DIR/Environment-Variables.md`).
3. **Prompt for RAG indexing** — If the project has a RAG indexing script (e.g., `scripts/index-rag.ts`), remind the user to run it so the new docs are embedded and searchable:
   ```
   New docs are in .raginclude. To make them searchable in chat, run the indexing script:
     DATABASE_URL="..." OPENAI_API_KEY="..." npx tsx scripts/index-rag.ts --clean
   ```
   If no indexing script exists, note that the docs are ready for manual indexing.
4. **Report** — List all files created and their sizes, noting which were new vs replaced

## Output Structure

```
$DOCS_DIR/Features/
├── README.md                  (index of all feature docs)
├── site-navigation.md         (navigational guide for RAG)
├── authentication.md
├── user-account.md
├── billing-subscriptions.md
├── products.md
├── ai-chat.md
├── admin-panel.md
└── api-integrations.md

app/sitemap.ts                 (Next.js App Router)
  — OR —
public/sitemap.xml             (static/other frameworks)
```

## Doc Quality Rules

- **Write for end users** — as if explaining to a customer. No jargon, no API details.
- **Concrete over abstract** — "Click Settings > Profile" not "navigate to the profile management interface"
- **Include current behavior** — read the actual code, don't guess. If a feature has limits (e.g., "5 messages per hour for free tier"), state them.
- **No trade secrets** — omit internal pricing formulas, proprietary algorithms, security infrastructure details
- **Respect existing work** — when replacing existing docs, preserve any manually-added content that isn't auto-generated (look for markers like `<!-- manual -->` or sections not matching the template)

## Doc Template

See `references/doc-template.md` for the full template each agent should follow.

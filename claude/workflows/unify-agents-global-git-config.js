export const meta = {
  name: 'unify-agents-global-git-config',
  description: 'Scan repos for git/SCM rules, diff them against one source of truth, and apply the approved unified rules',
  whenToUse: 'Driven by the /unify-agents-global-git-config command. Run with args.mode "scan" first, then "apply" with the user-approved plan.',
  phases: [
    { title: 'Canon', detail: 'extract the canonical git ruleset from the source' },
    { title: 'Scan', detail: 'one agent per repo: collect every git/SCM rule, following links' },
    { title: 'Compare', detail: 'diff each repo against the canon' },
    { title: 'Unify', detail: 'merge cross-repo conflicts into the fewest questions' },
    { title: 'Apply', detail: 'one agent per repo: edit, commit, push, PR/merge as its rules allow' },
    { title: 'Verify', detail: 'independent re-read: does each repo now match the canon?' },
  ],
}

// ---------------------------------------------------------------------------
// args (passed by the command; see claude/skills/unify-agents-global-git-config/SKILL.md)
//   mode:        'scan' | 'apply'
//   date:        'YYYY-MM-DD HH:MM'  (scripts cannot read the clock)
//   source:      { kind: 'global'|'local'|'dir', path, files: [abs paths] }
//   repos:       [abs repo paths]                       (scan)
//   canon:       canon object returned by a previous scan (apply)
//   plans:       [{ repo, target_file, strategy, block, removals, exceptions, notes }] (apply)
//   quiet:       boolean
// ---------------------------------------------------------------------------

const A = args || {}
const MODE = A.mode || 'scan'
const DATE = A.date || 'unknown-date'
const BLOCK_BEGIN = '<!-- BEGIN unified-git-rules -->'
const BLOCK_END = '<!-- END unified-git-rules -->'

const TOPICS = [
  'branching', 'commit-messages', 'attribution', 'direct-to-main', 'pull-requests',
  'review', 'merging', 'force-push', 'hooks', 'secrets-scanning', 'versioning',
  'changelog', 'tags-releases', 'ci-gates', 'working-tree-hygiene', 'other',
]

const RULE = {
  type: 'object',
  properties: {
    topic: { type: 'string', enum: TOPICS },
    statement: { type: 'string', description: 'The rule, normalized to one imperative sentence' },
    verbatim: { type: 'string', description: 'Exact source text (trimmed, <= 600 chars)' },
    file: { type: 'string' },
    line: { type: 'integer' },
  },
  required: ['topic', 'statement', 'verbatim', 'file', 'line'],
}

const CANON_SCHEMA = {
  type: 'object',
  properties: {
    rules: {
      type: 'array',
      items: {
        type: 'object',
        properties: { id: { type: 'string', description: 'stable slug, e.g. git-branch-from-origin-main' }, ...RULE.properties },
        required: ['id', ...RULE.required],
      },
    },
    files_read: { type: 'array', items: { type: 'string' } },
    internal_conflicts: { type: 'array', items: { type: 'string' }, description: 'Contradictions inside the source itself' },
    block_markdown: { type: 'string', description: 'The canonical rules rendered as the managed block body (no BEGIN/END markers)' },
  },
  required: ['rules', 'files_read', 'internal_conflicts', 'block_markdown'],
}

const SCAN_SCHEMA = {
  type: 'object',
  properties: {
    repo: { type: 'string' },
    skip_reason: { type: 'string', description: 'Empty unless the repo must be skipped (not a git repo, third-party/fork, archived, no write access)' },
    remote: { type: 'string' },
    default_branch: { type: 'string' },
    current_branch: { type: 'string' },
    dirty: { type: 'boolean' },
    ahead_of_origin: { type: 'integer', description: 'commits on local default branch not on origin' },
    local_hooks_path: { type: 'string', description: 'git config --local core.hooksPath, or empty' },
    has_pre_commit_gate: { type: 'boolean', description: 'a pre-commit hook actually runs in this repo' },
    instruction_files: { type: 'array', items: { type: 'string' } },
    canonical_file: { type: 'string', description: 'AGENTS.md if present, else CLAUDE.md, else empty' },
    managed_block: { type: 'string', enum: ['absent', 'present', 'malformed'] },
    rules: { type: 'array', items: RULE },
    files_followed: { type: 'array', items: { type: 'string' } },
  },
  required: ['repo', 'skip_reason', 'remote', 'default_branch', 'current_branch', 'dirty', 'ahead_of_origin',
    'local_hooks_path', 'has_pre_commit_gate', 'instruction_files', 'canonical_file', 'managed_block', 'rules', 'files_followed'],
}

const COMPARE_SCHEMA = {
  type: 'object',
  properties: {
    repo: { type: 'string' },
    items: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          rule_id: { type: 'string', description: 'canon id, or empty for repo-only rules' },
          topic: { type: 'string', enum: TOPICS },
          kind: { type: 'string', enum: ['missing', 'conflict', 'drifted_copy', 'repo_only', 'stale_block', 'matches'] },
          repo_text: { type: 'string' },
          canonical_text: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'integer' },
          proposed_action: { type: 'string', description: 'concrete edit, e.g. "replace lines 40-52 with the managed block"' },
          needs_decision: { type: 'boolean', description: 'true only for conflict / repo_only items a human must choose on' },
        },
        required: ['rule_id', 'topic', 'kind', 'repo_text', 'canonical_text', 'file', 'line', 'proposed_action', 'needs_decision'],
      },
    },
    route: { type: 'string', enum: ['direct-main', 'pr', 'blocked'], description: 'how this repo\'s own rules say an instruction-file-only change lands' },
    route_reason: { type: 'string' },
  },
  required: ['repo', 'items', 'route', 'route_reason'],
}

const UNIFY_SCHEMA = {
  type: 'object',
  properties: {
    questions: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          header: { type: 'string', description: '<= 12 chars' },
          question: { type: 'string', description: 'Stands alone: names the rule, both variants, and how many repos are affected' },
          options: {
            type: 'array', minItems: 2, maxItems: 4,
            items: { type: 'object', properties: { label: { type: 'string' }, description: { type: 'string' } }, required: ['label', 'description'] },
          },
          affects: { type: 'array', items: { type: 'object', properties: { repo: { type: 'string' }, file: { type: 'string' }, line: { type: 'integer' } }, required: ['repo', 'file', 'line'] } },
        },
        required: ['id', 'header', 'question', 'options', 'affects'],
      },
    },
    auto: { type: 'array', items: { type: 'string' }, description: 'Changes needing no decision, one line each: "<repo>: <action>"' },
    skipped: { type: 'array', items: { type: 'string' }, description: '"<repo>: <reason>"' },
    summary: { type: 'string' },
  },
  required: ['questions', 'auto', 'skipped', 'summary'],
}

const APPLY_SCHEMA = {
  type: 'object',
  properties: {
    repo: { type: 'string' },
    status: { type: 'string', enum: ['committed-main', 'pr-open', 'pr-merged', 'pr-auto-merge', 'no-change', 'blocked', 'failed'] },
    files_changed: { type: 'array', items: { type: 'string' } },
    backups: { type: 'array', items: { type: 'string' } },
    commit: { type: 'string' },
    branch: { type: 'string' },
    pr_url: { type: 'string' },
    notes: { type: 'string' },
  },
  required: ['repo', 'status', 'files_changed', 'backups', 'commit', 'branch', 'pr_url', 'notes'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    repo: { type: 'string' },
    matches: { type: 'boolean' },
    problems: { type: 'array', items: { type: 'string' } },
  },
  required: ['repo', 'matches', 'problems'],
}

const HOW_TO_READ_RULES = `
How to find git/SCM rules (follow every link, depth-first, each file once):
- Instruction files: AGENTS.md (root and nested), CLAUDE.md, GEMINI.md, .github/copilot-instructions.md,
  CONTRIBUTING*, .github/pull_request_template.md / PULL_REQUEST_TEMPLATE*, .gitmessage, docs referenced from them.
- Follow @imports (\`@path\` on its own line), markdown links and backticked paths to other .md files
  (e.g. ~/.claude/instructions/*.md, Docs/*.md). Resolve ~ to the user's home.
- Machine config that encodes commit rules: commitlint/.czrc, .pre-commit-config.yaml, lefthook.yml, .husky/,
  \`git config --local --get-regexp '^(commit|core\\.hooksPath|hook)\\.'\`.
- A "git rule" is anything about branching, commit messages, attribution trailers, direct-to-main vs PR,
  review, merging, force-push, hooks/scanning on commit, versioning/changelog on PR, tags/releases,
  CI gates, or working-tree hygiene. Also rules for other SCMs (hg, svn, jj) if present.
- Text between ${BLOCK_BEGIN} and ${BLOCK_END} is a previously synced copy: report it, tagged with that file/line.
Read only. Never edit, never run anything that writes.`

// ---------------------------------------------------------------------------
if (MODE === 'scan') {
  if (!A.source || !Array.isArray(A.repos)) throw new Error('scan needs args.source and args.repos')

  phase('Canon')
  const canon = await agent(
    `Extract the canonical git/SCM ruleset (the single source of truth) from:
kind=${A.source.kind}, root=${A.source.path}
start files: ${JSON.stringify(A.source.files || [])}
${HOW_TO_READ_RULES}
Give each rule a stable id slug. List contradictions inside the source as internal_conflicts.
Then render block_markdown: a self-contained, tool-agnostic "## Git & commit rules" section that any agent CLI
can follow without the source files present (inline the rules; you may add "Detail: <path>" pointers but the
rule itself must be in the block). First line under the heading: "_Synced from ${A.source.kind} source on ${DATE} by /unify-agents-global-git-config. Edit the source, not this block._"`,
    { label: 'canon', phase: 'Canon', schema: CANON_SCHEMA, effort: 'high' })
  if (!canon) throw new Error('canon extraction failed')
  log(`canon: ${canon.rules.length} rules from ${canon.files_read.length} files`)

  phase('Scan')
  const compared = await pipeline(
    A.repos,
    repo => agent(
      `Inventory git/SCM rules and git state for the repository at ${repo}.
${HOW_TO_READ_RULES}
Git state (read-only commands): remote URL, default branch (origin/HEAD), current branch, dirty?, commits on the
local default branch missing from origin, local core.hooksPath, and whether a pre-commit hook actually runs here
(global hooksPath hook not shadowed by a local one, or a local framework that calls it).
Set skip_reason if: not a git repo; the remote owner is not the user or their org (third-party, upstream, fork
of someone else's project); archived; or under a 3rdParty directory.`,
      { label: `scan:${repo.split('/').pop()}`, phase: 'Scan', schema: SCAN_SCHEMA, effort: 'low' }),
    (scan, repo) => {
      if (!scan) return null
      if (scan.skip_reason) return { scan, cmp: null }
      return agent(
        `Compare this repository's git rules with the canonical ruleset.
REPO SCAN: ${JSON.stringify(scan)}
CANON RULES: ${JSON.stringify(canon.rules)}
For every canon rule: matches / missing / conflict (repo says something incompatible) / drifted_copy (same intent,
different wording or detail that could diverge) / stale_block (the managed block exists but differs from canon).
For every repo rule with no canon counterpart: repo_only. needs_decision=true only for conflict and repo_only.
proposed_action: the default plan is ONE managed block (${BLOCK_BEGIN} ... ${BLOCK_END}) in the canonical file,
plus removing or rewording duplicated/conflicting git statements elsewhere in that repo so no second copy can drift.
route: read THIS repo's own rules (and the canon) to decide how an instruction-file-only change lands here —
"direct-main" only if those rules allow non-functional commits to main AND has_pre_commit_gate is true AND
local_hooks_path does not shadow it; "pr" otherwise; "blocked" if the repo cannot be changed safely (explain).`,
        { label: `compare:${repo.split('/').pop()}`, phase: 'Compare', schema: COMPARE_SCHEMA })
        .then(cmp => ({ scan, cmp }))
    },
  )

  const results = compared.filter(Boolean)
  const lost = A.repos.length - results.length
  if (lost) log(`WARNING: ${lost} repo(s) returned no result and are NOT covered`)
  const active = results.filter(r => r.cmp)
  const pending = active.flatMap(r => r.cmp.items.filter(i => i.needs_decision).map(i => ({ repo: r.scan.repo, ...i })))

  phase('Unify')
  let unify = { questions: [], auto: [], skipped: [], summary: 'nothing to unify' }
  if (active.length) {
    unify = await agent(
      `You are merging per-repo rule differences into the FEWEST possible questions for the user.
CANON: ${JSON.stringify(canon.rules.map(r => ({ id: r.id, topic: r.topic, statement: r.statement })))}
CANON INTERNAL CONFLICTS: ${JSON.stringify(canon.internal_conflicts)}
ITEMS NEEDING A DECISION: ${JSON.stringify(pending)}
ALL REPOS: ${JSON.stringify(results.map(r => ({ repo: r.scan.repo, skip: r.scan.skip_reason, route: r.cmp && r.cmp.route, route_reason: r.cmp && r.cmp.route_reason, nonDecision: r.cmp ? r.cmp.items.filter(i => !i.needs_decision && i.kind !== 'matches').map(i => i.proposed_action) : [] })))}
Rules for questions:
- One question per distinct rule disagreement, NOT per repo: if 7 repos say "squash merge" and canon says "merge
  commit", that is one question listing all 7 in affects.
- Every canon internal conflict becomes a question first (the source must be consistent before it is copied).
- repo_only rules with the same intent across repos collapse into one question.
- Options (2-4), first is your recommendation with " (Recommended)" appended:
  "Use canon everywhere" / "Promote repo rule to the source" (source gets edited, then every repo gets it) /
  "Keep as a per-repo exception" (kept outside the managed block under "Repo-specific git exceptions") / "Remove".
- header <= 12 chars. question must stand alone (name the rule, both texts briefly, repo count).
- Order questions by blast radius (most repos first).
auto: one line per non-decision change. skipped: one line per skipped repo with reason.`,
      { label: 'unify', phase: 'Unify', schema: UNIFY_SCHEMA, effort: 'high' })
  }

  return { mode: 'scan', date: DATE, source: A.source, canon, repos: results, unify, uncovered: lost }
}

// ---------------------------------------------------------------------------
if (MODE === 'apply') {
  if (!A.canon || !Array.isArray(A.plans)) throw new Error('apply needs args.canon and args.plans')

  phase('Apply')
  const applied = await pipeline(
    A.plans,
    plan => agent(
      `Apply the approved unified git rules to the repository at ${plan.repo}.
PLAN (already approved by the user — do exactly this, nothing more): ${JSON.stringify(plan)}
MANAGED BLOCK BODY: ${JSON.stringify(plan.block || A.canon.block_markdown)}
Procedure:
1. git fetch. Work in a throwaway worktree cut from origin/<default-branch> so local WIP and unpushed local commits
   never leak (git worktree add ../.ugr-<repo>-${DATE.replace(/[^0-9]/g, '')} origin/<default>). Never touch the
   user's working tree.
2. Before editing, back up each target file from the user's original checkout to
   <original-checkout>/<file>.bak-<YYYYmmdd-HHMMSS> with cp -n (never clobber an existing backup). Backups are
   not committed. List them.
3. Write/replace the block between ${BLOCK_BEGIN} and ${BLOCK_END} in plan.target_file (create the markers if
   absent, at the end of the file or replacing the existing git section). Apply plan.removals (delete/reword
   duplicate or conflicting git statements elsewhere) and put plan.exceptions under "## Repo-specific git
   exceptions" right after the block. Keep every non-git line intact. @imports stay on line 1.
4. Commit following the commit-message and attribution rules in the managed block (they are now this repo's rules).
   Route: ${plan.route} (from the plan) —
   direct-main: commit on the worktree (based on origin/<default>), verify \`git log origin/<default>..HEAD\` shows
   only your commit, push to <default>. Never force-push, never --admin, never bypass a failed check.
   pr: branch docs/unify-git-rules-${DATE.slice(0, 10)}, push, open a PR (mirror the repo's PR template headings),
   follow the repo's versioning rule if it requires a bump on PRs. Merge only if the repo's rules allow autonomous
   merging and every required check is green now; if checks are pending and auto-merge is allowed, enable it;
   otherwise leave the PR open and report its URL.
   blocked: change nothing, report why.
5. Remove the worktree. Report status, files, backups, commit sha, branch, PR URL.`,
      { label: `apply:${plan.repo.split('/').pop()}`, phase: 'Apply', schema: APPLY_SCHEMA }),
    (res, plan) => res && res.status !== 'blocked' && res.status !== 'failed' && res.status !== 'no-change'
      ? agent(
        `Independently verify the git-rules sync for ${plan.repo}. Try to find a problem; default matches=false if unsure.
Read the repo AS PUSHED (origin/<default> or the PR branch ${res.branch || ''}), not the local working tree.
${HOW_TO_READ_RULES}
Check: exactly one managed block; its body equals the approved block; no git statement elsewhere in the repo
contradicts or duplicates a canon rule unless it is a listed exception (${JSON.stringify(plan.exceptions || [])});
non-git content was not lost (compare against the backups ${JSON.stringify(res.backups)}); @imports still on line 1;
the commit message follows the canon's commit rules.`,
        { label: `verify:${plan.repo.split('/').pop()}`, phase: 'Verify', schema: VERIFY_SCHEMA, effort: 'high' })
        .then(v => ({ ...res, verify: v }))
      : res,
  )

  const out = applied.filter(Boolean)
  if (out.length < A.plans.length) log(`WARNING: ${A.plans.length - out.length} repo(s) returned no result`)
  return { mode: 'apply', date: DATE, results: out }
}

throw new Error(`unknown mode: ${MODE}`)

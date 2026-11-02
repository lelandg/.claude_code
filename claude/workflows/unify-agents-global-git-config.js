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
//   plans:       [{ repo, scanned_commit, default_branch, target_file, route, block, removals, exceptions, notes }] (apply)
//   quiet:       boolean
// ---------------------------------------------------------------------------

// Workflow may hand args over as a JSON string (see update-code-map's workflow template).
const A = (typeof args === 'string' ? JSON.parse(args) : args) || {}
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
    scanned_commit: { type: 'string', description: 'sha of origin/<default> that was read (after git fetch)' },
    local_divergence: { type: 'string', description: 'How the local checkout\'s instruction files differ from origin/<default> (branch, uncommitted, unpushed), or empty' },
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
  required: ['repo', 'skip_reason', 'remote', 'default_branch', 'scanned_commit', 'local_divergence', 'current_branch', 'dirty', 'ahead_of_origin',
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
    status: { type: 'string', enum: ['committed-main', 'pr-open', 'pr-merged', 'pr-auto-merge', 'no-change', 'stale', 'blocked', 'failed'] },
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

// Model inputs: instructions and supplied data go in separate XML-style tags (AGENTS.md "Prompt formatting").
const tag = (name, body) => `<${name}>\n${typeof body === 'string' ? body : JSON.stringify(body, null, 1)}\n</${name}>`
const short = repo => repo.split('/').filter(Boolean).pop()

// ---------------------------------------------------------------------------
if (MODE === 'scan') {
  if (!A.source || !Array.isArray(A.repos)) throw new Error('scan needs args.source and args.repos')

  phase('Canon')
  const canon = await agent([
    tag('instructions', `Extract the canonical git/SCM ruleset (the single source of truth) from the source in <source>.
Read the files as they are on disk; the command already confirmed they are committed.
Give each rule a stable id slug. List contradictions inside the source as internal_conflicts.
Then render block_markdown: a self-contained, tool-agnostic "## Git & commit rules" section that any agent CLI
can follow without the source files present (inline the rules; you may add "Detail: <path>" pointers but the
rule itself must be in the block). First line under the heading:
"_Synced from ${A.source.kind} source on ${DATE} by /unify-agents-global-git-config. Edit the source, not this block._"`),
    tag('how_to_read_rules', HOW_TO_READ_RULES),
    tag('source', { kind: A.source.kind, root: A.source.path, start_files: A.source.files || [] }),
  ].join('\n\n'), { label: 'canon', phase: 'Canon', schema: CANON_SCHEMA, effort: 'high' })
  if (!canon) throw new Error('canon extraction failed')
  log(`canon: ${canon.rules.length} rules from ${canon.files_read.length} files`)

  phase('Scan')
  const compared = await pipeline(
    A.repos,
    repo => agent([
      tag('instructions', `Inventory git/SCM rules and git state for the repository in <repo>.
Read the rules AT THE REVISION THE APPLY STEP WILL EDIT, not the working tree: run \`git fetch\` (it only updates
remote-tracking refs), resolve the default branch from origin/HEAD, record \`git rev-parse origin/<default>\` as
scanned_commit, and read every file with \`git show <scanned_commit>:<path>\` / \`git ls-tree -r <scanned_commit>\`.
Then compare the local checkout's instruction files against that revision and describe any difference (other
branch checked out, uncommitted or unpushed rule edits) in local_divergence, so the user sees it before approving.
Git state (read-only commands besides the fetch): remote URL, current branch, dirty?, commits on the local default
branch missing from origin, local core.hooksPath, and whether a pre-commit hook actually runs here (global
hooksPath hook not shadowed by a local one, or a local framework that calls it).
Set skip_reason if: not a git repo; no origin remote; the remote owner is not the user or their org (third-party,
upstream, fork of someone else's project); archived; or under a 3rdParty directory.`),
      tag('how_to_read_rules', HOW_TO_READ_RULES),
      tag('repo', repo),
    ].join('\n\n'), { label: `scan:${short(repo)}`, phase: 'Scan', schema: SCAN_SCHEMA, effort: 'low' }),
    (scan, repo) => {
      if (!scan) return { repo, error: 'scan agent returned no result' }
      if (scan.skip_reason) return { repo, scan, cmp: null }
      return agent([
        tag('instructions', `Compare the repository's git rules (<repo_scan>) with the canonical ruleset (<canon_rules>).
For every canon rule: matches / missing / conflict (repo says something incompatible) / drifted_copy (same intent,
different wording or detail that could diverge) / stale_block (the managed block exists but differs from canon).
For every repo rule with no canon counterpart: repo_only. needs_decision=true only for conflict and repo_only.
proposed_action: the default plan is ONE managed block (${BLOCK_BEGIN} ... ${BLOCK_END}) in the canonical file,
plus removing or rewording duplicated/conflicting git statements elsewhere in that repo so no second copy can drift.
File/line references are at scanned_commit.
route: read THIS repo's own rules (at scanned_commit) and the canon to decide how an instruction-file-only change
lands here — "direct-main" only if those rules allow non-functional commits to main AND has_pre_commit_gate is
true AND local_hooks_path does not shadow it; "pr" otherwise; "blocked" if the repo cannot be changed safely.`),
        tag('repo_scan', scan),
        tag('canon_rules', canon.rules),
      ].join('\n\n'), { label: `compare:${short(repo)}`, phase: 'Compare', schema: COMPARE_SCHEMA })
        .then(cmp => cmp ? { repo, scan, cmp } : { repo, scan, error: 'compare agent returned no result' })
    },
  )

  // Every repo ends up in exactly one bucket: active, skipped, or failed. Nothing silently disappears.
  const rows = compared.map((r, i) => r || { repo: A.repos[i], error: 'pipeline dropped this repo' })
  const failed = rows.filter(r => r.error)
  const skipped = rows.filter(r => !r.error && !r.cmp)
  const active = rows.filter(r => !r.error && r.cmp)
  if (failed.length) log(`WARNING: ${failed.length} repo(s) NOT covered: ${failed.map(f => `${short(f.repo)} (${f.error})`).join(', ')}`)
  const pending = active.flatMap(r => r.cmp.items.filter(i => i.needs_decision).map(i => ({ repo: r.repo, ...i })))

  phase('Unify')
  let unify = { questions: [], auto: [], skipped: skipped.map(r => `${r.repo}: ${r.scan.skip_reason}`), summary: 'nothing to unify' }
  if (active.length || canon.internal_conflicts.length) {
    const unified = await agent([
      tag('instructions', `Merge per-repo rule differences into the FEWEST possible questions for the user.
- One question per distinct rule disagreement, NOT per repo: if 7 repos say "squash merge" and canon says "merge
  commit", that is one question listing all 7 in affects.
- Every item in <canon_internal_conflicts> becomes a question first (the source must be consistent before it is copied).
- repo_only rules with the same intent across repos collapse into one question.
- Options (2-4), first is your recommendation with " (Recommended)" appended:
  "Use canon everywhere" / "Promote repo rule to the source" (source gets edited, then every repo gets it) /
  "Keep as a per-repo exception" (kept outside the managed block under "Repo-specific git exceptions") / "Remove".
- header <= 12 chars. question must stand alone (name the rule, both texts briefly, repo count).
- If a repo's local_divergence is non-empty, mention it in that repo's auto line so the user sees it.
- Order questions by blast radius (most repos first).
auto: one line per non-decision change. skipped: one line per entry in <skipped_repos>.`),
      tag('canon_rules', canon.rules.map(r => ({ id: r.id, topic: r.topic, statement: r.statement }))),
      tag('canon_internal_conflicts', canon.internal_conflicts),
      tag('items_needing_decision', pending),
      tag('active_repos', active.map(r => ({
        repo: r.repo, route: r.cmp.route, route_reason: r.cmp.route_reason, local_divergence: r.scan.local_divergence,
        changes: r.cmp.items.filter(i => !i.needs_decision && i.kind !== 'matches').map(i => i.proposed_action),
      }))),
      tag('skipped_repos', skipped.map(r => ({ repo: r.repo, reason: r.scan.skip_reason }))),
    ].join('\n\n'), { label: 'unify', phase: 'Unify', schema: UNIFY_SCHEMA, effort: 'high' })
    if (!unified) throw new Error('unify agent returned no result; questions cannot be built, so nothing may be applied')
    // skipped comes from code, not the model, so the list is always complete.
    unify = { ...unified, skipped: skipped.map(r => `${r.repo}: ${r.scan.skip_reason}`) }
  }

  return {
    mode: 'scan', date: DATE, source: A.source, canon, unify,
    repos: rows.filter(r => !r.error),
    failed: failed.map(f => ({ repo: f.repo, error: f.error })),
    uncovered: failed.length,
  }
}

// ---------------------------------------------------------------------------
if (MODE === 'apply') {
  if (!A.canon || !Array.isArray(A.plans)) throw new Error('apply needs args.canon and args.plans')
  const ts = DATE.replace(/[^0-9]/g, '')

  phase('Apply')
  const applied = await pipeline(
    A.plans,
    plan => {
      const block = plan.block || A.canon.block_markdown
      return agent([
        tag('instructions', `Apply the approved unified git rules (<plan>, <managed_block>) to the repository in <plan>.repo.
The plan is already approved by the user: do exactly this, nothing more.
1. \`git fetch\`. If \`git rev-parse origin/<default>\` differs from plan.scanned_commit, run
   \`git diff --stat <scanned_commit> origin/<default>\`. If any instruction or rule file the plan references
   changed, change nothing and report status "stale" (the approval was for different text). Otherwise continue.
2. Work in a throwaway worktree cut from origin/<default>, so local WIP and unpushed local commits never leak:
   \`git worktree add ../.ugr-<repo-name>-${ts} origin/<default>\`. Never touch the user's working tree.
3. Before editing, back up each target file AT THAT SAME REVISION (the content you are about to change):
   \`git show origin/<default>:<file> > <repo>/.git/ugr-backups/${ts}/<file>\` (mkdir -p; inside .git, so it is
   never committed and never clutters the checkout; never overwrite an existing backup). List the paths.
4. Write/replace the block between ${BLOCK_BEGIN} and ${BLOCK_END} in plan.target_file (create the markers if
   absent, at the end of the file or replacing the existing git section). Apply plan.removals (delete/reword
   duplicate or conflicting git statements elsewhere) and put plan.exceptions under "## Repo-specific git
   exceptions" right after the block. Keep every non-git line intact. @imports stay on line 1.
5. Commit following the commit-message and attribution rules in the managed block (they are now this repo's rules).
   Route plan.route:
   - direct-main: commit in the worktree, verify \`git log origin/<default>..HEAD\` shows only your commit, push to
     <default>. Never force-push, never --admin, never bypass a failed check.
   - pr: branch docs/unify-git-rules-${DATE.slice(0, 10)}, push, open a PR (mirror the repo's PR template headings),
     follow the repo's versioning rule if it requires a bump on PRs. Merge only if the repo's rules allow
     autonomous merging and every required check is green now; if checks are pending and auto-merge is allowed,
     enable it; otherwise leave the PR open and report its URL.
   - blocked: change nothing, report why.
6. Remove the worktree. Report status, files, backups, commit sha, branch, PR URL.`),
        tag('plan', plan),
        tag('managed_block', block),
      ].join('\n\n'), { label: `apply:${short(plan.repo)}`, phase: 'Apply', schema: APPLY_SCHEMA })
        .then(res => res ? { ...res, repo: plan.repo } : { repo: plan.repo, status: 'failed', files_changed: [], backups: [], commit: '', branch: '', pr_url: '', notes: 'apply agent returned no result' })
    },
    (res, plan) => {
      if (['blocked', 'failed', 'no-change', 'stale'].includes(res.status)) return res
      return agent([
        tag('instructions', `Independently verify the git-rules sync for the repository in <plan>.repo. Try to find a problem;
default matches=false if unsure. Read the repo AS PUSHED (origin/<default> after git fetch, or the PR branch in
<apply_result>.branch), not the local working tree.
Check:
- exactly one managed block (${BLOCK_BEGIN} ... ${BLOCK_END}), and its body equals <approved_block>;
- no git statement elsewhere in the repo contradicts or duplicates a rule in <canon_rules>, unless it is listed
  in <plan>.exceptions;
- non-git content was not lost (compare with the backups listed in <apply_result>.backups);
- @imports are still on line 1;
- the commit message follows the commit rules in <approved_block>.`),
        tag('how_to_read_rules', HOW_TO_READ_RULES),
        tag('plan', { repo: plan.repo, target_file: plan.target_file, exceptions: plan.exceptions || [], removals: plan.removals || [] }),
        tag('apply_result', res),
        tag('approved_block', plan.block || A.canon.block_markdown),
        tag('canon_rules', A.canon.rules),
      ].join('\n\n'), { label: `verify:${short(plan.repo)}`, phase: 'Verify', schema: VERIFY_SCHEMA, effort: 'high' })
        .then(v => ({ ...res, verify: v ? { ...v, repo: plan.repo } : { repo: plan.repo, matches: false, problems: ['verifier returned no result: NOT verified'] } }))
    },
  )

  const out = applied.map((r, i) => r || { repo: A.plans[i].repo, status: 'failed', notes: 'pipeline dropped this repo' })
  const unverified = out.filter(r => r.verify && !r.verify.matches)
  const failedApply = out.filter(r => r.status === 'failed' || r.status === 'stale')
  if (failedApply.length) log(`WARNING: ${failedApply.length} repo(s) failed or stale: ${failedApply.map(r => short(r.repo)).join(', ')}`)
  if (unverified.length) log(`WARNING: ${unverified.length} repo(s) did not verify: ${unverified.map(r => short(r.repo)).join(', ')}`)
  return { mode: 'apply', date: DATE, results: out, failed: failedApply.length, unverified: unverified.length }
}

throw new Error(`unknown mode: ${MODE}`)

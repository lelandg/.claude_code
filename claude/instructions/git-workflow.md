# Git workflow: direct-to-main rule and new repositories

Moved from `~/.config/agents/AGENTS.md` on 2026-11-24 so that file stays under agy's rule-file cut (22,035 bytes, measured 2026-11-25). AGENTS.md keeps the rule in brief and points here; this text is the full version and is equally binding.

## Rule 4 — code through a PR; non-functional changes straight to `main`

4. **Code reaches `main` through a PR; non-functional changes may be committed
   straight to `main`.**

   "Non-functional" means **every** path in the commit is one no build step
   consumes: Markdown, text, and images under `Docs/`, `Plans/`, `Notes/`,
   `Discord/`, plus `README*`, `CHANGELOG*`, `LICENSE*`, comment- or
   docstring-only edits inside source files, **and the agent-instruction files** — `AGENTS.md`,
   `CLAUDE.md`, `GEMINI.md`, `~/.claude/instructions/**`, and skill bodies. A
   mixed commit is a PR, and so is anything a machine executes, schedules, or
   serves even when it reads like prose: `.github/**`, any reviewer or CI
   config, `.snyk`, `dependabot.yml`, any config or `.sql` file, agent *code*,
   and anything the build copies, serves, or RAG-indexes. When unsure, PR.

   **The allowance for the agent-instruction files carries an obligation**,
   because a contradiction *between* two rule files is the one defect class
   diff-scoped reviewers cannot see: when you change a rule on `main` that
   another file repeats — a project `AGENTS.md`, a `CLAUDE.md`, a skill body,
   a runbook — update every copy in the **same commit**. If you cannot, or you
   are unsure where the rule is echoed, it is a PR. Grep before you commit;
   the reviewers will not do it for you.

   A direct commit still runs your pre-commit hook, still carries attribution,
   and needs no version bump. Never force-push `main`, never `--admin`, and
   never use a bypass to land something that **failed** a check — the allowance
   skips the PR, not the obligation to be clean. (It cannot also mean "never
   bypass a status check": the direct push this rule authorizes necessarily
   skips those checks *as gates*, for the reason the next paragraph gives.)

   **If you have no pre-commit hook, this allowance is not for you.** It is
   safe only because something preventive still runs on a direct commit. A
   bypassed branch with no local gate has nothing checking it at all, and the
   server-side scans then report the secret after it is already in history.
   Install one first (`tools/githooks/install.sh` in the config repo ships the
   hook this rule assumes), or keep using PRs.

   **Then check it actually runs in *this* repo.** A repo-local
   `core.hooksPath` — Husky, lefthook, the `pre-commit` framework — takes
   precedence over the global one, so git never starts the global hook and the
   gate is silently absent exactly where you assumed it was present.
   Check the effective value, not one scope: a worktree-level setting
   (`config.worktree`) overrides them all, and `--local` alone does not show
   it. `git config --show-origin --get core.hooksPath`, run in this checkout,
   must name your global hooks directory, or the hook it names must invoke
   the global `pre-commit` (the secret scan) itself. Until one of those is true, this
   repo is a PR-only repo whatever the paths say.

   For the same reason, a commit
   that used the hook's degraded-scan override has never been scanned: run
   `gitleaks` over it yourself before pushing, because nothing downstream will
   stop it and rule 2 (in `~/.config/agents/AGENTS.md`, like rules 1 to 3)
   says local `main` may hold things on purpose.

   **A direct push publishes everything `main` is holding, not just your
   commit.** Rule 2 exists because local `main` accumulates commits kept back
   deliberately, and `git push` takes them all. So start from the remote head
   (`git fetch && git status` clean against `origin/main`, or commit in a
   throwaway worktree cut from `origin/main`) and check
   `git log --oneline origin/main..HEAD` before pushing — the same check rule 3
   asks for, which until now applied only to branches.

   **Know what your branch protection actually allows before relying on this.**
   Protect a `main` that deploys to production with a ruleset requiring a pull
   request and your security checks green (e.g. `gitleaks`,
   `npm audit signatures`). A direct push then needs a bypass actor on that
   ruleset — and a bypass is granted to a *role*, which GitHub cannot scope by
   path, so the same grant also skips those checks as gates on any push by
   that role. They still run and fail visibly afterwards, which is detection,
   not prevention. So this rule, not the platform, is what keeps code off that
   path: run `gh api repos/<owner>/<repo>/rulesets` before assuming a direct
   push lands, and keep a code hotfix a PR with green checks.

## Rules 5 and 6 — new repositories

5. **Every new repository starts from a secure template.** Create it from
   your template repository
   (`gh repo create <owner>/<name> --private --template <template-owner>/<template> ...`;
   `Chameleon-Labs-LLC/secure-repo-template` is a public one built for this),
   then follow that template's `docs/agent-guide.md`: README quick start,
   the repository settings in section 7 (Dependabot alerts and security
   updates, private vulnerability reporting, CODEOWNERS, ruleset), and the
   project section of `AGENTS.md`. The project's code then arrives **through
   a PR**, never in the creating push, so the review council and the repo's
   automated reviewers see it. An existing repo that lacks the setup adopts
   it with section 4 of the same guide, as its own PR. (Origin: a repo
   created with all its code in one direct push, so no reviewer ever saw
   it.)
6. **Every repository is on GitHub, and private unless the user says
   otherwise.** Local scheduled backups are not a substitute. A repo with no
   remote is a defect: when you find one, run `gitleaks git` over its whole
   history, create the GitHub repo with `--private`, push, and say so. Make a
   repo public only when the user asks for that repo by name. (Origin: a week
   of working state held in a local-only repo.)

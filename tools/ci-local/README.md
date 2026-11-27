# ci-local

Run a repository's own GitHub Actions workflow files on your machine before you
push, the way CI would run them. It uses [act](https://github.com/nektos/act)
and Docker, costs no Actions minutes, and tells you job by job what GitHub is
going to say.

```bash
ci-local.sh /path/to/repo                       # every pull_request job, HEAD merged into the default branch
ci-local.sh /path/to/repo -j db                 # one job (its id in the workflow)
ci-local.sh /path/to/repo --ref my-branch --pr 42
ci-local.sh /path/to/repo --event push          # what a push to the branch runs
ci-local.sh /path/to/repo -- --list             # anything after -- goes to act; --list/--graph/--dryrun print act's output
```

Each run prints one line per job act planned for the event (`act --list`):
`succeeded`, `failed`, `skipped` (act exited 0 without running it, which is how
act treats a job whose `if:` is false) or `not run` (act failed before reaching
it, say in a `needs:` chain). It prints the full log's path under
`~/ci-local/logs/` and exits with act's code, with one exception: act exits 1
when removing a finished container times out on a busy Docker, even after
every job passed. ci-local removes the run's containers itself, so it reports
that run as a pass, but only when every planned job is confirmed to have
succeeded. With a skip, a matrix job (the plan shows one row however many
instances run) or a reusable workflow (its jobs report under their own ids),
act's exit code stands ([`ci_summary.py`](ci_summary.py)).

## How close is it to GitHub?

Close enough that a green local run predicts a green CI run. Each difference
between act and a GitHub-hosted runner that could change a result is handled:

| GitHub does | ci-local does |
|---|---|
| Checks out the pushed commit, as `owner/repo` | Fetches that **commit** into a clean clone under `~/ci-local/<repo>-<hash>`. Uncommitted edits are never tested (it warns when you have some), and nothing crosses a slow Windows mount. The clone keeps your repository's GitHub remote, so `github.repository` is right. One ci-local run at a time on the machine; a second is refused |
| A `pull_request` run tests `refs/pull/N/merge` | Merges the commit into the base branch your clone knows (`origin/<default>`) and tests the merge, without your signing key or hooks. A conflict fails the run, as it would on GitHub |
| 2 vCPU / 7 GB per job | Each job container, including one a job declares with `container:`, gets a 2-CPU quota and 7 GB, and **sees** 2 CPUs: `/proc/cpuinfo` and `/proc/stat` are masked, as lxcfs does. Without that, a tool that sizes itself from the CPU count (Playwright's workers, test runners) starts one worker per host core inside a 2-CPU quota, and its tests time out. Timing flakes (a cold compile beating a 5-second wait) show up here too |
| `ubuntu-latest` = Ubuntu 24.04 | `catthehacker/ubuntu:act-24.04` |
| Every job and matrix instance on its own empty VM, so `ports: 5432:5432` always binds | act runs them all on one host ([`act_compat.py`](act_compat.py)). A host port in use on your machine, or by another job of the same run, moves to a free one, together with that job's `localhost:<port>` uses and any it inherits from the workflow-level `env:` (copied into the job). A service's own health check is left alone, since it runs inside the service. A matrix job that publishes fixed ports runs one instance at a time. A free port is left alone |
| Each job fetches its own copy of its actions | act's new action cache (`--use-new-action-cache`) gives each job its own copy. The classic cache checks every action out into one shared folder, and jobs that start together delete each other's files (`remove .../.gitignore: no such file`, `archive/tar: write too long`). Once cached, actions are not re-fetched when every one is pinned to a commit SHA; a tag or branch pin is fetched fresh each run |
| Every job has its own disk | Here jobs share one disk, so at most 2 jobs run at once (`CI_LOCAL_JOBS`), and each matrix at most 2 instances at once. With eight jobs at once, and still with four, `npm ci`s starved a Postgres service past its health check, which never happens on GitHub. Two at a time kept every job within its checks and was also the fastest (below). act applies the job limit per job and the matrix limit per matrix, so a run with several matrices can exceed 2 containers |
| A finished job's VM is gone | The run's own containers and networks are removed afterwards, even when act's `--rm` times out on a busy Docker (`context deadline exceeded`). Ownership is proven, not guessed: while a job runs, ci-local records the IDs of its container (found by this run's private `/proc` mount), of its service network (named after the job container) and of the containers on that network, and deletes only those IDs. Nothing another act run created is touched, even if it reuses the same names |

What it does not do: post a check to the pull request, provide your repository
secrets (jobs that need them fail or skip, as they would on a fork), or run
`macos-*` / `windows-*` jobs. `nproc` inside a job still reports the host's
cores (it reads the CPU affinity, not `/proc`); Node's `os.cpus()` and
`os.availableParallelism()` report 2. The edits for ports happen only in the
throwaway clone; your workflow files are never changed.

Overrides: `CI_LOCAL_JOBS` (jobs at once, default 2; raise it on a fast disk)
and `CI_LOCAL_IMAGE` (runner image).

## Speed

One real repository, eight jobs (typecheck/lint/unit, Postgres tests with
migrations, `next build`, Playwright + axe, four security scans), the same
commit:

| Where | Wall clock |
|---|---|
| GitHub (every job on its own runner) | 9.9 min |
| ci-local, 4 jobs at a time | 10.5-12.5 min, and the Postgres service sometimes missed its health check |
| ci-local, 2 jobs at a time (default) | 8.8 min |

Fewer jobs at once means less disk contention, so each job runs faster, which
more than makes up for running fewer of them.

## Requirements

- Docker Engine, running (`docker info` works without sudo).
- act, pinned. The tested version is v0.2.98:

  ```bash
  d=$(mktemp -d) && cd "$d"
  base=https://github.com/nektos/act/releases/download/v0.2.98
  curl -fsSLO "$base/act_Linux_x86_64.tar.gz" && curl -fsSLO "$base/checksums.txt"
  grep ' act_Linux_x86_64.tar.gz$' checksums.txt | sha256sum -c -
  tar -xzf act_Linux_x86_64.tar.gz act && install -m 0755 act ~/.local/bin/act
  cd - && rm -rf "$d"
  ```

- The runner image, once: `docker pull catthehacker/ubuntu:act-24.04` (about
  2.3 GB). Runs use `--pull=false`, so they never download it mid-run.
- `git`, `bash`, `flock` (util-linux) and Python 3.12 or later (standard
  library only).

## WSL notes

- Run it from WSL. Pass the repository as `/mnt/<drive>/...`; a worktree that
  Windows git created works too (its `gitdir: D:/...` pointer is translated,
  and the branch comes from that worktree's `HEAD`).
- With `networkingMode=mirrored` in `.wslconfig`, WSL shares ports with
  Windows. A Windows database on 5432 is exactly the case `act_compat.py`
  handles.
- With systemd enabled, `sudo systemctl enable --now docker.socket docker.service`
  starts Docker now and at every boot. If that command seems to hang right
  after WSL starts, check `systemctl list-jobs`: it waits for the boot to
  finish (a long `systemd-tmpfiles-setup` clearing a big `/tmp` is a known
  cause), not for Docker.

## Tests

```bash
cd tools/ci-local && python -m pytest -q
```

`test_ci_local.py` runs the script against real git repos with stub `act` and
`docker` commands, so it needs Linux bash and `flock`; it skips on Windows.

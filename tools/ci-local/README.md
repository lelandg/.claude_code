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

Each run prints one line per planned job (`succeeded`, `failed` or `not run`)
and the full log's path under `~/ci-local/logs/`. It exits 0 only when every
job act planned for the event (`act --list`) succeeded; otherwise it exits with
act's code. A job a `needs:` chain never reached counts as not run, not as a
pass. The one act error it overrules is a timeout removing a finished container
after every planned job passed, since ci-local removes the run's containers
itself ([`ci_summary.py`](ci_summary.py)).

## How close is it to GitHub?

Close enough that a green local run predicts a green CI run. Each difference
between act and a GitHub-hosted runner that could change a result is handled:

| GitHub does | ci-local does |
|---|---|
| Checks out the pushed commit, as `owner/repo` | Fetches that **commit** into a clean clone under `~/ci-local/<repo>-<hash>`. Uncommitted edits are never tested (it warns when you have some), and nothing crosses a slow Windows mount. The clone keeps your repository's GitHub remote, so `github.repository` is right. One ci-local run at a time on the machine; a second is refused |
| A `pull_request` run tests `refs/pull/N/merge` | Merges the commit into the base branch your clone knows (`origin/<default>`) and tests the merge, without your signing key or hooks. A conflict fails the run, as it would on GitHub |
| 2 vCPU / 7 GB per job | Each job container gets a 2-CPU quota and 7 GB, and **sees** 2 CPUs: `/proc/cpuinfo` and `/proc/stat` are masked, as lxcfs does. Without that, a tool that sizes itself from the CPU count (Playwright's workers, test runners) starts one worker per host core inside a 2-CPU quota, and its tests time out. Timing flakes (a cold compile beating a 5-second wait) show up here too |
| `ubuntu-latest` = Ubuntu 24.04 | `catthehacker/ubuntu:act-24.04` |
| Every job and matrix instance on its own empty VM, so `ports: 5432:5432` always binds | act runs them all on one host ([`act_compat.py`](act_compat.py)). A host port in use on your machine, or by another job of the same run, moves to a free one, together with that job's `localhost:<port>` uses and any it inherits from the workflow-level `env:` (copied into the job). A service's own health check is left alone, since it runs inside the service. A matrix job that publishes fixed ports runs one instance at a time. A free port is left alone |
| Each job fetches its own copy of its actions | act's new action cache (`--use-new-action-cache`) gives each job its own copy. The classic cache checks every action out into one shared folder, and jobs that start together delete each other's files (`remove .../.gitignore: no such file`, `archive/tar: write too long`). Once cached, actions are not re-fetched when every one is pinned to a commit SHA; a tag or branch pin is fetched fresh each run |
| Every job has its own disk | Here jobs share one disk, so at most 4 jobs run at once (`CI_LOCAL_JOBS`), and each matrix at most 4 instances at once. With all eight jobs of a real repository at once, seven `npm ci`s starved a Postgres service past its health check, which never happens on GitHub. act applies the job limit per job and the matrix limit per matrix, so a run with several matrices can still exceed 4 containers |
| A finished job's VM is gone | The run's own containers and networks are removed afterwards, even when act's `--rm` times out on a busy Docker (`context deadline exceeded`). Ownership is proven, not guessed: job containers carry this run's private `/proc` mount, and each service network is named after its job container. Nothing another act run created is touched |

What it does not do: post a check to the pull request, provide your repository
secrets (jobs that need them fail or skip, as they would on a fork), or run
`macos-*` / `windows-*` jobs. `nproc` inside a job still reports the host's
cores (it reads the CPU affinity, not `/proc`); Node's `os.cpus()` and
`os.availableParallelism()` report 2. The edits for ports happen only in the
throwaway clone; your workflow files are never changed.

Overrides: `CI_LOCAL_JOBS` (jobs at once, default 4; raise it on a fast disk)
and `CI_LOCAL_IMAGE` (runner image).

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

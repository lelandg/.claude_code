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
ci-local.sh /path/to/repo -- --list             # anything after -- goes to act
```

Each run prints one line per job (`succeeded` / `failed`), the full log's path
under `~/ci-local/logs/`, and exits with act's code: 0 means every selected job
succeeded.

## How close is it to GitHub?

Close enough that a green local run predicts a green CI run. Each difference
between act and a GitHub-hosted runner that could change a result is handled:

| GitHub does | ci-local does |
|---|---|
| Checks out the pushed commit | Fetches that **commit** into a clean clone under `~/ci-local/<repo>`. Uncommitted edits are never tested (it warns when you have some), and nothing crosses a slow Windows mount |
| A `pull_request` run tests `refs/pull/N/merge` | Merges the commit into the base branch your clone knows (`origin/<default>`) and tests the merge. A conflict fails the run, as it would on GitHub |
| 2 vCPU / 7 GB per job | Each job container is capped at `--cpus 2 --memory 7g`, so timing flakes (a cold compile beating a 5-second wait) show up here too |
| `ubuntu-latest` = Ubuntu 24.04 | `catthehacker/ubuntu:act-24.04` |
| An empty VM, so `ports: 5432:5432` always binds | A host port already in use here moves to a free one, with the job's `localhost:<port>` uses ([`act_compat.py`](act_compat.py)); a free port is left alone |
| Each job fetches its actions | Every SHA-pinned action is fetched once, up front, then act runs offline. Parallel jobs otherwise race on act's shared cache (`archive/tar: write too long`) |

What it does not do: post a check to the pull request, provide your repository
secrets (jobs that need them fail or skip, as they would on a fork), or run
`macos-*` / `windows-*` jobs. The edits for ports happen only in the
throwaway clone; your workflow files are never changed.

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
- `git`, `bash` and Python 3.9 or later (standard library only).

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

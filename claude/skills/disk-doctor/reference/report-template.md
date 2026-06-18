# disk-doctor report — {{date}} ({{os}})

**Total reclaimable: {{total_human}}**

## Cleanup candidates (by reclaimable size)

| Category | Size | What it is (plain English) | Path(s) |
|---|---|---|---|
| {{category}} | {{size}} | {{reason}} | {{paths}} |

## Install-hygiene findings (report-only — nothing was changed)

| Issue | Where | Why it matters | Suggested fix (run yourself) |
|---|---|---|---|
| {{issue}} | {{location}} | {{impact}} | `{{fix_command}}` |

## Commands (runbook mode only)

Each cleanup category above maps to a command you can run yourself:

```bash
# {{category}} ({{size}})
safe-trash --allow {{allowed_root}} --commit {{paths}}
```

To undo the most recent cleanup at any time:

```bash
disk-doctor-undo
```

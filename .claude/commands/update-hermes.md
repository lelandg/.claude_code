---
description: Safely update the Hermes Agent on this machine — manual source patch/tarball backup, hermes update --backup, verify, restore customizations if lost
---

Invoke the Skill tool with `skill: "update-hermes"` and pass the arguments through: `$ARGUMENTS`

Never run a bare `hermes update` — the skill's backup-first workflow is mandatory.

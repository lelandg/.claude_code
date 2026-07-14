/**
 * config-secrets-guard — Pi port of ~/.claude/tools/config-secrets-guard.py
 *
 * Blocks tool calls that would print a secret-bearing config file
 * (config*.yaml except config.example.yaml, .env* except .env.example)
 * into the conversation transcript:
 *   - bash commands combining a content-printing tool (cat/sed/head/...)
 *     with a secret-bearing filename (incl. ssh-quoted commands, pipelines)
 *   - read calls on those files
 *
 * Escape hatch: append `# config-ok` to a bash command for a human-approved
 * exception. Safe alternative for inspecting config structure:
 *   python3 ~/.claude/tools/safe-config-reader.py <file>
 *
 * Keep the regexes in sync with the Python original (used by Claude Code,
 * Codex, and Antigravity hooks).
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const PRINT_TOOLS =
  /\b(?:cat|sed|awk|head|tail|less|more|diff|sdiff|comm|grep|egrep|fgrep|rg|bat|strings|nl|od|xxd|hexdump|paste|column|sort|uniq|tac|cut|tee)\b/;
const SECRET_FILE =
  "(?:config(?!\\.example)[\\w.-]*\\.ya?ml|\\.env(?!\\.example|ironment)(?:\\.(?!example)[\\w.-]+)?)";
const SECRET_FILE_RE = new RegExp(SECRET_FILE + "\\b");
const SECRET_FILE_FULL = new RegExp("^" + SECRET_FILE + "$");
const OVERRIDE = "# config-ok";

const DENY_REASON =
  "Blocked: this would print contents of a secret-bearing config file " +
  "(config*.yaml / .env*) into the transcript — API keys and passwords " +
  "leaked exactly this way on 2026-07-13. Use " +
  "`python3 ~/.claude/tools/safe-config-reader.py <file>` for structure " +
  "with values masked, or `--key a.b.c` for one setting. For a write-only " +
  "command that must touch the file (e.g. `sed -i`), have the human approve " +
  "appending `# config-ok` to the command.";

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event) => {
    const input = (event.input ?? {}) as Record<string, unknown>;

    if (event.toolName === "bash") {
      const command = typeof input.command === "string" ? input.command : "";
      if (command.includes(OVERRIDE)) return;
      if (SECRET_FILE_RE.test(command) && PRINT_TOOLS.test(command)) {
        return { block: true, reason: DENY_REASON };
      }
    } else if (event.toolName === "read") {
      const path = typeof input.path === "string" ? input.path : "";
      const basename = path.split(/[\\/]/).pop() ?? "";
      if (SECRET_FILE_FULL.test(basename)) {
        return { block: true, reason: DENY_REASON };
      }
    }
  });
}

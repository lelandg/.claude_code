## USAGE:
1. Copy the agent `.md` files to `~/.claude/agents/`.
2. Edit your `~/.claude/CLAUDE.md` to reference the agents.
3. Restart all Claude instances.

## Work Procedures
- When I ask you to update the code map (or CodeMap), check the last date it was modified, then use git history to look for changes and update appropriate sections.
- When I ask you to review any code, always use the code reviewer agent.
- When I ask to update the code map, use the code map agent.
- Use agent when one is available for a task.

### Code Review Agent Guidelines
**IMPORTANT**: When using the code-reviewer agent:
1. **Verify assumptions with actual code**: Don't assume issues exist - check the actual implementation
2. **Read files before claiming problems**: Always inspect the actual code rather than guessing based on patterns
3. **Check for existing implementations**: Many "potential" issues may already be properly handled
4. **Distinguish actual vs potential issues**: Focus on real problems, not theoretical ones
5. **Consider modern best practices**: Modern codebases often already implement proper patterns (IDisposable, async/await, etc.)

## Startup Procedures
- At startup, if ./CLAUDE.md exists and there is not a project-level `Docs/CodeMap.md`, offer to create it.

## Plan File Management

**CRITICAL**: Plan files in `Plans/` or `Notes/` directories must be kept current at all times to ensure continuity across sessions.

### When to Update Plan Files

Update the corresponding plan file **immediately** after:
1. **Completing any task or phase** - Mark with status "COMPLETED"
2. **Starting a new task** - Mark with status "IN PROGRESS"
3. **Creating new files** - Document file paths and line counts
4. **Modifying existing files** - Note what was changed
5. **Discovering blockers** - Document issues and workarounds
6. **Changing approach** - Update strategy sections

### Required Updates

When updating plan files, you MUST:
1. **Mark task completion status**: Use check marks (complete), clock (in progress), X (blocked), pause (paused)
2. **Add timestamps**: Update "Last Updated" at top of file or section
3. **Document deliverables**: List all files created/modified with line counts
4. **Update progress percentages**: Calculate phase completion (e.g., "Phase 2: 95% Complete")
5. **Add implementation notes**: Document deviations from plan, lessons learned
6. **Update "Status" sections**: Keep current status at top of each phase
7. **Cross-reference files**: Link to actual code files (e.g., `src/module.py`)

### Auto-Update Triggers

Automatically update the plan file when:
- Completing a TodoWrite task that's part of a plan
- Creating new files mentioned in the plan
- Finishing a phase or major milestone
- Encountering errors that affect the plan
- User asks to continue a plan (before starting work)

### Recovery After Interruption

When resuming after session interruption:
1. **Read the plan file first** - Check "Last Updated" and current status
2. **Review "Status" sections** - Understand what was in progress
3. **Check deliverables** - Verify which files were created
4. **Resume from last checkpoint** - Continue from last completed task
5. **Update plan immediately** - Mark current task as "IN PROGRESS"

## Important Agent Usage Notes

**Agent File Creation**: When agents (documentation-specialist, code-reviewer, etc.) report creating files, always verify the file exists afterward. If it doesn't exist, create it directly using the Write tool with the agent's output. Agents sometimes indicate file creation in their summaries without the actual file being written due to their sandboxed execution environment.

### Code Navigation

#### Code Map Reference
**IMPORTANT**: Always use the comprehensive code map located at the project level `Docs/CodeMap.md` for:
- **Finding classes and methods**: Detailed inventory with line numbers for quick navigation
- **Understanding file organization**: Complete project structure with cross-references
- **Locating shared variables**: Cross-file state management and variable usage
- **Navigating the codebase**: Organized by functional domains and architectural layers

**Code Map Currency Check**:
- **ALWAYS** check the last updated timestamp at the top of CodeMap.md before using it
- If the code map is older than 7 days, prompt: "The CodeMap.md was last updated on [YYYY-MM-DD HH:MM:SS]. Would you like me to update it first to ensure accuracy?"

Use `file_path:line_number` references from the code map to quickly locate specific implementations.

## File Navigation Best Practices

### Working with Files Across Directories

#### Core Principles:
- **Never use `cd` commands**: Stay in the current working directory and use absolute paths
- **Always use full paths**: Specify complete paths for all file operations
- **Batch operations**: Call multiple tools in parallel when searching

## Documentation Procedures
- Any time you write to a CodeMap.md file, see ~/.claude/CLAUDE_CodeMap.md for specs.
- Any time I ask for documentation, use the documentation specialist agent.
- **Documentation Structure**:
  - Developer and user documentation goes in project-level `Docs/` directory
  - Future plans, ideas, and brainstorming go in project-level `Notes/` directory
  - Use markdown format (.md) as standard for all documentation

## Credentials and Secrets Management

**CRITICAL**: Never store API keys, passwords, or credentials in project directories.

### Standard Pattern

Store credentials in platform-specific user config directories **outside the project**:

- **Windows**: `%APPDATA%\Roaming\{AppName}\config.json`
- **macOS**: `~/Library/Application Support/{AppName}/config.json`
- **Linux**: `~/.config/{AppName}/config.json`

### Security Notes
- Project `.env` files can contain non-secret defaults, but **never** API keys
- User config directory is outside git - must be backed up separately
- Always use absolute paths (`Path.home()`) to locate config
- Create config directory with `mkdir(parents=True, exist_ok=True)`

## Node.js Version Management
- **Update Node.js to latest LTS**:
  - `nvm install --lts --reinstall-packages-from=default`
  - `nvm alias default lts/* && nvm use default`
- **Per-project version pinning**:
  - Create a `.nvmrc` in each repo (e.g., `lts/*` or `20`), then run `nvm use` in that directory

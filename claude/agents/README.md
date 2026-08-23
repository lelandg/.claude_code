# Claude Code Agents

This directory contains specialized agent configurations for Claude Code that extend its capabilities with focused expertise in specific domains. Once installed, these agents can be invoked using the Task tool.

## Installation

These are custom agents for Claude Code. To use them, you need to install them in your Claude Code agents directory.

### Installation Steps

1. **Clone or download this repository**:
   ```bash
   git clone https://github.com/lelandg/ClaudeAgents.git
   ```

2. **Copy agent files to your Claude Code agents directory**:
   ```bash
   cp *.md ~/.claude/agents/
   ```

   Or if you cloned the entire repository:
   ```bash
   cp <repository-path>/*.md ~/.claude/agents/
   ```

3. **Verify installation**:
   - The agents should now be available in Claude Code
   - Claude Code will automatically detect any `.md` files with proper frontmatter in `~/.claude/agents/`

### Requirements

- Claude Code must be installed and configured
- The `~/.claude/agents/` directory should exist (created automatically by Claude Code)

### Quick Start

To use an agent, simply ask Claude Code to perform a task that matches the agent's purpose:

```
# Code review
"Can you review this authentication code?"
```

Claude Code will automatically select and invoke the appropriate agent based on your request. You can also manually request specific agents using the Task tool.

## Available Agents

This directory ships one agent. Earlier revisions carried a larger roster
(documentation-specialist, research-assistant, software-engineer,
test-generator, performance-optimizer); those retired in August 2026 —
built-in Claude Code capabilities and the skills in `claude/skills/` cover
their jobs now. Their definitions remain available in git history.

### Code Reviewer (`code-reviewer.md`)
**Model:** Opus  
**Color:** Green  
**Purpose:** Reviews code for quality, bugs, performance issues, and best practices

**Key Capabilities:**
- Bug detection (logic errors, edge cases, resource leaks, security issues)
- Code quality analysis (SOLID principles, design patterns, maintainability)
- Performance review (algorithm efficiency, bottlenecks, memory usage)
- Best practices compliance (language idioms, project standards)
- Provides specific, actionable improvement suggestions

**Review Structure:**
1. Summary overview
2. Critical issues (must fix)
3. Important suggestions (quality/performance)
4. Minor suggestions (style/optimization)
5. Positive observations

**When to Use:**
- After implementing new features or functions
- Following code refactoring
- When explicitly requested for code review
- Automatically after writing significant code blocks

**Example Usage:**
```
User: "I've refactored the mesh generation pipeline. Can you check if it looks good?"
Assistant: "I'll use the code-reviewer agent to thoroughly review your refactored mesh generation pipeline."
```

## Agent Configuration Format

Each agent file follows a YAML frontmatter format:

```yaml
---
name: agent-name
description: Detailed description with examples
tools: List of available tools (optional)
model: claude model to use (opus/sonnet)
color: UI color for the agent
---

[Agent prompt and instructions]
```

## How Agents Work

1. **Invocation**: Agents are invoked through Claude Code's Task tool
2. **Stateless Execution**: Each agent invocation is independent
3. **Specialized Expertise**: Agents have focused prompts for specific domains
4. **Tool Access**: Agents can use various tools (Read, Write, Edit, Bash, etc.)
5. **Automatic Selection**: Claude Code selects appropriate agents based on task context

## Best Practices

1. **Let Claude Code choose**: Claude Code will automatically select the appropriate agent based on your request
2. **Be specific**: Provide clear context about what you need
3. **Review outputs**: Agent suggestions should be reviewed before implementation
4. **Chain agents**: Multiple agents can be used sequentially for complex tasks
5. **Provide context**: Include relevant project information for better results

## Creating Custom Agents

To create a new agent:

1. Create a new `.md` file in this directory
2. Add YAML frontmatter with required fields
3. Write the agent's prompt and instructions
4. The agent will be automatically available in Claude Code

## Notes

- Agents are designed to be proactive when appropriate
- Some agents (like code-reviewer) may be invoked automatically after certain actions
- Agents follow project-specific standards from CLAUDE.md files when available
- Each agent has access to specific tools optimized for their purpose
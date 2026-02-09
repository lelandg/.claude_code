# Claude Code Agents

This directory contains specialized agent configurations for Claude Code that extend its capabilities with focused expertise in specific domains. Once installed, these agents can be invoked using the Task tool.

## Installation

These are custom agents for Claude Code. To use them, you need to install them in your Claude Code agents directory.

### Installation Steps

1. **Clone or download this repository**:
   ```bash
   git clone <repository-url>
   ```

2. **Copy agent files to your Claude Code agents directory**:
   ```bash
   cp agents/*.md ~/.claude/agents/
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

# Documentation
"Please document the new API endpoints"

# Performance optimization
"My application is slow, help me optimize it"

# Testing
"Write tests for the UserService class"
```

Claude Code will automatically select and invoke the appropriate agent based on your request. You can also manually request specific agents using the Task tool.

## Available Agents

### 1. Code Reviewer (`code-reviewer.md`)
**Model:** Opus | **Color:** Green
Reviews code for quality, bugs, performance issues, and best practices. Provides structured reviews with critical issues, suggestions, and positive observations.

### 2. Documentation Specialist (`documentation-specialist.md`)
**Model:** Sonnet | **Color:** Blue
Creates and maintains comprehensive technical documentation including user guides, API docs, architecture documents, and README files.

### 3. Research Assistant (`research-assistant.md`)
**Model:** Sonnet | **Color:** Yellow
Researches technologies, best practices, and implementation approaches. Provides comparative analysis and actionable recommendations.

### 4. Performance Optimizer (`performance-optimizer.md`)
**Model:** Opus | **Color:** Yellow
Analyzes code performance, identifies bottlenecks, and suggests optimizations for algorithms, databases, frontend, and backend.

### 5. Test Generator (`test-generator.md`)
**Model:** Sonnet | **Color:** Purple
Creates comprehensive test suites with edge cases, mocks, and fixtures. Supports Jest, pytest, JUnit, xUnit, and more.

### 6. Software Engineer (`software-engineer.md`)
**Model:** Opus | **Color:** Purple
Writes new code, fixes bugs, implements features, and refactors existing code with production-quality standards.

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

1. Create a new `.md` file in `~/.claude/agents/`
2. Add YAML frontmatter with required fields (`name`, `description`, `model`, `color`)
3. Optionally specify `tools` the agent can use
4. Write the agent's prompt and instructions
5. The agent will be automatically available in Claude Code

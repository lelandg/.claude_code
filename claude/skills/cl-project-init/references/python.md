# Python Project Reference

## Directory Structure

```
project-name/
├── src/
│   └── project_name/        # Main package (snake_case)
│       ├── __init__.py
│       └── main.py
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── scripts/                 # One-off utility scripts
├── Docs/                    # Documentation
├── Notes/                   # Plans, ideas
├── .env.example
├── .gitignore
├── CLAUDE.md
├── pyproject.toml           # Preferred for modern Python
├── requirements.txt         # Or use this for simpler projects
└── README.md
```

## pyproject.toml (modern Python)

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "project-name"
version = "0.1.0"
description = "A company Python tool"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = ["pytest", "black", "ruff", "mypy"]

[tool.black]
line-length = 88

[tool.ruff]
select = ["E", "F", "W"]
ignore = []

[tool.mypy]
python_version = "3.12"
strict = true
```

## requirements.txt (simpler projects)

```
# Core
# Add dependencies as needed

# Dev
pytest>=7
black>=23
ruff>=0.1
```

## Virtual Environment Setup

```bash
# Create venv (use venv_linux for WSL)
python3 -m venv .venv_linux

# Activate
source .venv_linux/bin/activate

# Install deps
pip install -r requirements.txt
# or: pip install -e ".[dev]"
```

## .env.example for Python

```env
# Add environment-specific variables
# Example:
# DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
# API_KEY=your-api-key
```

## CLAUDE.md Template for Python

```markdown
# [Project Name] — CLAUDE.md

## Tech Stack
- Python 3.12
- [List key libraries]

## Development
- Activate venv: `source .venv_linux/bin/activate`
- Run: `python3 src/project_name/main.py`
- Tests: `pytest tests/`
- Lint: `ruff check .`
- Format: `black .`

## Key Conventions
- Use python3 in WSL
- .venv_linux for Linux/WSL virtual environment
- All errors must be logged

## Debugging / Production
[Add deployment notes]
```

## Common Patterns

### Logging setup
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

### Config from environment
```python
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable required")
```

### CLI with argparse
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description='Project description')
    parser.add_argument('--input', required=True, help='Input file path')
    parser.add_argument('--output', default='output.txt', help='Output file path')
    args = parser.parse_args()
    # ... logic

if __name__ == '__main__':
    main()
```

## .gitignore additions for Python

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
.venv_linux/
venv/
env/
ENV/
dist/
*.egg-info/
.eggs/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
```

#!/usr/bin/env python3
"""
YourCompany Project Initializer Script

Creates a new project directory with standard CL structure.

Usage:
    python3 create_project.py --name "MyProject" --type nextjs-saas --description "A new app"
    python3 create_project.py --name "MyTool" --type python --path /path/to/your/projects/
"""

import argparse
import sys
from pathlib import Path


def to_kebab(name: str) -> str:
    return name.replace(' ', '-').replace('_', '-')


def to_snake(name: str) -> str:
    return name.replace(' ', '_').replace('-', '_').lower()


GITIGNORE_COMMON = """# Git worktrees
.worktrees/

# Dependencies
node_modules/

# Environment Variables & Secrets — CRITICAL: Never commit credentials
.env
.env.local
.env*.local
!.env.example

# Deployment docs with real credentials
DEPLOYMENT_READY.md

# Claude Code settings
.claude/settings.local.json

# Secret files
*_SECRET.txt
*.secret
*.key
*.pem
secrets.json

# AWS credentials
.aws/

# WebStorm / JetBrains IDEs
.idea/
*.iml
*.iws
*.ipr

# macOS
.DS_Store
._*

# Windows
Thumbs.db
Desktop.ini
$RECYCLE.BIN/

# Linux
*~

# Logs
logs/
*.log
npm-debug.log*

# Temporary
*.tmp
*.temp
.cache/
"""

GITIGNORE_NEXTJS = GITIGNORE_COMMON + """
# Next.js
.next/
out/
build/
dist/
!infra/lambda/*/dist/
/build

# Testing
coverage/
.nyc_output
.jest-cache/

# TypeScript
tsconfig.tsbuildinfo
next-env.d.ts

# Database
*.sqlite
*.db

# Prisma generated
/lib/generated/prisma

# Serverless
.serverless/
.webpack/
lambda-function.zip
"""

GITIGNORE_PYTHON = GITIGNORE_COMMON + """
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
build/
*.egg-info/
.eggs/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
"""


def create_nextjs_project(root: Path, name: str, description: str) -> list[str]:
    """Create Next.js SaaS project structure. Returns list of created paths."""
    created = []

    dirs = [
        'app/(site)',
        'app/api/auth',
        'app/dashboard',
        'components/ui',
        'components/layout',
        'lib/db',
        'hooks',
        'types',
        'prisma/migrations',
        'public',
        'Docs',
        'Notes',
        'Scripts',
        'infra/lambda',
    ]

    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)
        created.append(str(root / d))

    # .gitignore
    (root / '.gitignore').write_text(GITIGNORE_NEXTJS.strip() + '\n')
    created.append('.gitignore')

    # .env.example
    env_example = f"""# {name} Environment Variables

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/{to_snake(name)}

# Auth (NextAuth v5)
AUTH_SECRET=generate-with-openssl-rand-base64-32
AUTH_URL=http://localhost:3000
AUTH_GOOGLE_ID=
AUTH_GOOGLE_SECRET=
AUTH_GITHUB_ID=
AUTH_GITHUB_SECRET=

# Stripe (LIVE keys in production — NEVER commit real keys)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
"""
    (root / '.env.example').write_text(env_example)
    created.append('.env.example')

    # CLAUDE.md
    claude_md = f"""# {name} — CLAUDE.md

## Project Overview
{description}

## Tech Stack
- Next.js 14 App Router, TypeScript, Tailwind CSS
- NextAuth v5 (Google, GitHub OAuth)
- Prisma + PostgreSQL (AWS RDS)
- Stripe (LIVE mode — never use test keys)
- AWS Amplify deployment

## Development
- TypeScript check: `npx tsc --noEmit`
- Build: `npm run build`
- Dev server: `npm run dev`

## Key Conventions
- Admin auth: `const session = await auth(); if (!isAdminEmail(session?.user?.email)) return 401`
- DB helpers: `lib/db/[feature].ts` — try/catch, return null on failure
- Prisma models: CUIDs, `@@map` snake_case tables, `@updatedAt`
- Migrations: create SQL manually (no DATABASE_URL in WSL dev)
- CRITICAL Migration SQL: DB uses camelCase columns, NOT snake_case

## Debugging / Production
- Target deployed Amplify environment for production issues
- Amplify env vars must be echoed into `.env.production` in amplify.yml preBuild
- `aws amplify update-app --environment-variables` REPLACES ALL vars — read existing first
"""
    (root / 'CLAUDE.md').write_text(claude_md)
    created.append('CLAUDE.md')

    # package.json
    pkg_name = to_kebab(name).lower()
    package_json = f"""{{\
  "name": "{pkg_name}",
  "version": "0.1.0",
  "private": true,
  "scripts": {{
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  }},
  "dependencies": {{
    "next": "^14",
    "react": "^18",
    "react-dom": "^18",
    "next-auth": "^5.0.0-beta.25",
    "@prisma/client": "^5",
    "@tailwindcss/typography": "^0.5",
    "tailwindcss": "^3"
  }},
  "devDependencies": {{
    "typescript": "^5",
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "prisma": "^5",
    "postcss": "^8",
    "autoprefixer": "^10",
    "eslint": "^8",
    "eslint-config-next": "^14"
  }}
}}
"""
    (root / 'package.json').write_text(package_json)
    created.append('package.json')

    # tsconfig.json
    tsconfig = """{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
"""
    (root / 'tsconfig.json').write_text(tsconfig)
    created.append('tsconfig.json')

    # next.config.js
    (root / 'next.config.js').write_text(
        "/** @type {import('next').NextConfig} */\nconst nextConfig = {};\nmodule.exports = nextConfig;\n"
    )
    created.append('next.config.js')

    # postcss.config.mjs
    (root / 'postcss.config.mjs').write_text(
        "const config = { plugins: { tailwindcss: {}, autoprefixer: {} } };\nexport default config;\n"
    )
    created.append('postcss.config.mjs')

    # tailwind.config.ts (with CL brand colors)
    (root / 'tailwind.config.ts').write_text(
        """import type { Config } from 'tailwindcss';
import typography from '@tailwindcss/typography';

const config: Config = {
  darkMode: 'class',
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'brand-cyan': { DEFAULT: '#00D4FF', light: '#00BCD4', dark: '#0099CC' },
        'brand-navy': { DEFAULT: '#0A0E27', light: '#1a1e3f', dark: '#050711' },
        'chameleon': {
          magenta: '#FF1493', pink: '#E91E63', purple: '#9C27B0',
          violet: '#673AB7', blue: '#2196F3', 'blue-light': '#03A9F4',
          cyan: '#00BCD4', green: '#4CAF50', 'green-light': '#8BC34A',
          lime: '#CDDC39', yellow: '#FFEB3B', amber: '#FFC107',
          orange: '#FF9800', 'orange-deep': '#FF5722', red: '#F44336',
        },
        background: 'var(--background)',
        foreground: 'var(--foreground)',
      },
      fontFamily: {
        sans: ['var(--font-roboto)', 'Roboto', 'sans-serif'],
        heading: ['var(--font-limelight)', 'Limelight', 'sans-serif'],
      },
    },
  },
  plugins: [typography],
};

export default config;
"""
    )
    created.append('tailwind.config.ts')

    # amplify.yml
    (root / 'amplify.yml').write_text(
        """version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm ci
        - echo "AUTH_SECRET=$AUTH_SECRET" >> .env.production
        - echo "DATABASE_URL=$DATABASE_URL" >> .env.production
        - echo "NODE_ENV=production" >> .env.production
        - npx prisma migrate deploy
        - npx prisma generate
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: .next
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
      - .next/cache/**/*
"""
    )
    created.append('amplify.yml')

    # Prisma schema
    (root / 'prisma' / 'schema.prisma').write_text(
        f"""// {name} — Prisma Schema
// PostgreSQL database

generator client {{
  provider = "prisma-client-js"
  output   = "../lib/generated/prisma"
}}

datasource db {{
  provider = "postgresql"
  url      = env("DATABASE_URL")
}}

model User {{
  id            String    @id @default(cuid())
  email         String    @unique
  name          String?
  passwordHash  String?
  emailVerified DateTime?
  oauthProvider String?
  oauthId       String?
  stripeCustomerId String? @unique
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt

  @@map("users")
}}
"""
    )
    created.append('prisma/schema.prisma')

    # app/layout.tsx
    (root / 'app' / 'layout.tsx').write_text(
        f"""import type {{ Metadata }} from 'next';
import './globals.css';

export const metadata: Metadata = {{
  title: '{name}',
  description: '{description}',
}};

export default function RootLayout({{
  children,
}}: {{
  children: React.ReactNode;
}}) {{
  return (
    <html lang="en" className="dark">
      <body>{{children}}</body>
    </html>
  );
}}
"""
    )
    created.append('app/layout.tsx')

    # app/globals.css
    (root / 'app' / 'globals.css').write_text(
        """@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: #0A0E27;
  --foreground: #ffffff;
}

body {
  background: var(--background);
  color: var(--foreground);
}
"""
    )
    created.append('app/globals.css')

    # app/(site)/page.tsx
    (root / 'app' / '(site)' / 'page.tsx').write_text(
        f"""export default function HomePage() {{
  return (
    <main className="min-h-screen bg-brand-navy text-white">
      <h1 className="font-heading text-4xl text-brand-cyan">{name}</h1>
      <p>{description}</p>
    </main>
  );
}}
"""
    )
    created.append('app/(site)/page.tsx')

    # lib/prisma.ts
    (root / 'lib' / 'prisma.ts').write_text(
        """import { PrismaClient } from './generated/prisma';

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

export const prisma =
  globalForPrisma.prisma || new PrismaClient({ log: ['error'] });

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
"""
    )
    created.append('lib/prisma.ts')

    # lib/auth.ts
    (root / 'lib' / 'auth.ts').write_text(
        """import NextAuth from 'next-auth';
import Google from 'next-auth/providers/google';
import GitHub from 'next-auth/providers/github';

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google, GitHub],
  callbacks: {
    session: ({ session, token }) => ({
      ...session,
      user: { ...session.user, id: token.sub },
    }),
  },
});
"""
    )
    created.append('lib/auth.ts')

    # README.md
    (root / 'README.md').write_text(
        f"""# {name}

{description}

## Setup

```bash
npm install
cp .env.example .env.local
# Fill in .env.local with real values
npm run dev
```

## Tech Stack
- Next.js 14, TypeScript, Tailwind CSS
- NextAuth v5
- Prisma + PostgreSQL
- AWS Amplify
"""
    )
    created.append('README.md')

    return created


def create_python_project(root: Path, name: str, description: str) -> list[str]:
    """Create Python project structure. Returns list of created paths."""
    created = []
    pkg_name = to_snake(name)

    dirs = [
        f'src/{pkg_name}',
        'tests',
        'scripts',
        'Docs',
        'Notes',
    ]

    for d in dirs:
        (root / d).mkdir(parents=True, exist_ok=True)
        created.append(str(root / d))

    # Package init
    (root / 'src' / pkg_name / '__init__.py').write_text(
        f'"""{ name } — {description}"""\n'
    )
    created.append(f'src/{pkg_name}/__init__.py')

    (root / 'src' / pkg_name / 'main.py').write_text(
        f"""#!/usr/bin/env python3
\"\"\"{ name } — {description}\"\"\"

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting {name}")
    # TODO: Add your logic here


if __name__ == '__main__':
    main()
"""
    )
    created.append(f'src/{pkg_name}/main.py')

    # Tests
    (root / 'tests' / '__init__.py').touch()
    (root / 'tests' / 'test_main.py').write_text(
        f"""\"\"\"Tests for {name}\"\"\"
import pytest


def test_placeholder():
    assert True, "Replace with real tests"
"""
    )
    created.append('tests/test_main.py')

    # .gitignore
    (root / '.gitignore').write_text(GITIGNORE_PYTHON.strip() + '\n')
    created.append('.gitignore')

    # .env.example
    (root / '.env.example').write_text(
        f"""# {name} Environment Variables
# Copy to .env and fill in real values

# Add your variables here
# API_KEY=your-api-key
"""
    )
    created.append('.env.example')

    # requirements.txt
    (root / 'requirements.txt').write_text(
        """# Core dependencies
# Add as needed

# Dev dependencies
pytest>=7
black>=23
ruff>=0.1
"""
    )
    created.append('requirements.txt')

    # pyproject.toml
    pkg_kebab = to_kebab(name).lower()
    (root / 'pyproject.toml').write_text(
        f"""[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "{pkg_kebab}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = ["pytest", "black", "ruff"]

[tool.black]
line-length = 88

[tool.ruff]
select = ["E", "F", "W"]

[tool.pytest.ini_options]
testpaths = ["tests"]
"""
    )
    created.append('pyproject.toml')

    # CLAUDE.md
    (root / 'CLAUDE.md').write_text(
        f"""# {name} — CLAUDE.md

## Project Overview
{description}

## Tech Stack
- Python 3.12
- [List key libraries]

## Development
- Activate venv: `source .venv_linux/bin/activate`
- Run: `python3 src/{pkg_name}/main.py`
- Tests: `pytest tests/`
- Lint: `ruff check .`
- Format: `black .`

## Key Conventions
- Use python3 in WSL
- .venv_linux for Linux/WSL virtual environment
- All errors must be logged

## Debugging / Production
[Add deployment notes here]
"""
    )
    created.append('CLAUDE.md')

    # README.md
    (root / 'README.md').write_text(
        f"""# {name}

{description}

## Setup

```bash
python3 -m venv .venv_linux
source .venv_linux/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with real values
python3 src/{pkg_name}/main.py
```
"""
    )
    created.append('README.md')

    return created


def main():
    parser = argparse.ArgumentParser(
        description='Initialize a new company project'
    )
    parser.add_argument('--name', required=True, help='Project name (e.g., "QuickSort")')
    parser.add_argument(
        '--type',
        required=True,
        choices=['nextjs-saas', 'python', 'library'],
        help='Project type',
    )
    parser.add_argument('--description', default='', help='Short project description')
    parser.add_argument(
        '--path',
        default='.',
        help='Parent directory (default: current directory)',
    )
    args = parser.parse_args()

    description = args.description or f'A company {args.type} project'
    project_dir_name = to_kebab(args.name)
    root = Path(args.path) / project_dir_name

    if root.exists():
        print(f"Error: {root} already exists", file=sys.stderr)
        sys.exit(1)

    root.mkdir(parents=True)
    print(f"Creating {args.type} project: {args.name}")
    print(f"Location: {root.resolve()}")
    print()

    if args.type == 'nextjs-saas':
        created = create_nextjs_project(root, args.name, description)
    elif args.type == 'python':
        created = create_python_project(root, args.name, description)
    else:
        # library — basic structure
        created = create_python_project(root, args.name, description)

    print("Created:")
    for item in created:
        print(f"  {item}")

    print()
    print("Next steps:")
    if args.type == 'nextjs-saas':
        print(f"  1. cd {project_dir_name}")
        print("  2. npm install")
        print("  3. cp .env.example .env.local && fill in values")
        print("  4. npx prisma generate")
        print("  5. npm run dev")
        print("  6. Create GitHub repo and push")
        print("  7. Create Amplify app (aws amplify create-app)")
    else:
        print(f"  1. cd {project_dir_name}")
        print("  2. python3 -m venv .venv_linux && source .venv_linux/bin/activate")
        print("  3. pip install -r requirements.txt")
        print("  4. cp .env.example .env && fill in values")
        print("  5. Create GitHub repo and push")


if __name__ == '__main__':
    main()

# Next.js SaaS Project Reference

## Directory Structure

```
project-name/
├── app/
│   ├── (site)/              # Public marketing pages (route group)
│   │   ├── page.tsx         # Home page
│   │   ├── pricing/
│   │   └── about/
│   ├── api/                 # API routes
│   │   ├── auth/
│   │   └── webhooks/
│   ├── dashboard/           # Protected app pages
│   ├── globals.css
│   ├── layout.tsx           # Root layout with fonts
│   └── not-found.tsx
├── components/
│   ├── ui/                  # Reusable UI primitives
│   ├── layout/              # Header, footer, nav
│   └── [feature]/           # Feature-specific components
├── lib/
│   ├── auth.ts              # NextAuth config
│   ├── db/                  # DB helpers (one file per feature)
│   ├── generated/prisma/    # Prisma generated client (gitignored)
│   └── utils.ts
├── hooks/                   # Custom React hooks
├── types/                   # TypeScript type definitions
├── prisma/
│   ├── schema.prisma
│   └── migrations/
├── public/                  # Static assets
├── Docs/                    # Developer documentation
├── Notes/                   # Plans, brainstorming
├── Scripts/                 # Utility scripts
├── .env.example
├── .gitignore
├── amplify.yml
├── CLAUDE.md
├── next.config.js
├── package.json
├── postcss.config.mjs
├── tailwind.config.ts
└── tsconfig.json
```

## package.json — Core Dependencies

```json
{
  "dependencies": {
    "next": "^14",
    "react": "^18",
    "react-dom": "^18",
    "next-auth": "^5",
    "@prisma/client": "^5",
    "@tailwindcss/typography": "^0.5",
    "tailwindcss": "^3"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/node": "^20",
    "@types/react": "^18",
    "prisma": "^5",
    "postcss": "^8",
    "autoprefixer": "^10"
  }
}
```

Add as needed:
- `stripe` — for payments
- `@aws-sdk/client-ses` — for email via SES
- `@aws-sdk/client-s3` — for file uploads
- `bcryptjs` + `@types/bcryptjs` — for password hashing

## next.config.js

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ['lh3.googleusercontent.com'], // Google OAuth avatars
  },
};

module.exports = nextConfig;
```

## tsconfig.json

```json
{
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
```

## prisma/schema.prisma starter

```prisma
generator client {
  provider = "prisma-client-js"
  output   = "../lib/generated/prisma"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
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
}
```

## lib/auth.ts (NextAuth v5 pattern)

```ts
import NextAuth from 'next-auth';
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
```

## amplify.yml starter

```yaml
version: 1
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
```

## Admin Auth Pattern

```ts
// Standard admin check in API routes
import { auth } from '@/lib/auth';
import { isAdminEmail } from '@/lib/utils';

export async function GET() {
  const session = await auth();
  if (!session?.user?.email || !isAdminEmail(session.user.email)) {
    return new Response('Unauthorized', { status: 401 });
  }
  // ...
}
```

## DB Helper Pattern

```ts
// lib/db/[feature].ts
import { prisma } from '@/lib/prisma';

export async function getFeatureById(id: string) {
  try {
    return await prisma.feature.findUnique({ where: { id } });
  } catch (error) {
    console.error('getFeatureById error:', error);
    return null;
  }
}
```

## .env.example for SaaS

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Auth (NextAuth v5)
AUTH_SECRET=your-auth-secret
AUTH_URL=http://localhost:3000
AUTH_GOOGLE_ID=
AUTH_GOOGLE_SECRET=
AUTH_GITHUB_ID=
AUTH_GITHUB_SECRET=

# Stripe (use LIVE keys in production)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# AWS SES (email)
SES_REGION=us-east-1
SES_ACCESS_KEY_ID=
SES_SECRET_ACCESS_KEY=
CONTACT_FROM_EMAIL=noreply@yourdomain.com
```

## CLAUDE.md Template for Next.js SaaS

```markdown
# [Project Name] — CLAUDE.md

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

## Debugging / Production
- Target deployed Amplify environment for production issues
- Amplify env vars must be echoed into `.env.production` in amplify.yml preBuild
- `aws amplify update-app --environment-variables` REPLACES ALL vars — read existing first
```

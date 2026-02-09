# Sanitization Rules

Rules for stripping private information when syncing config files to the public repo.

## How Rules Work

Each rule has:
- **Pattern**: Regex or literal string to find
- **Replacement**: What to substitute
- **Scope**: Which files this rule applies to (`*` = all)

Apply rules in order. Earlier rules take priority.

## Rule Definitions

Rules are organized by severity. **Always apply all Critical and High rules.** Medium rules are context-dependent.

### Critical: Credentials and Secrets

| Pattern | Replacement | Scope |
|---------|-------------|-------|
| API keys (any `sk-...`, `pk-...`, `AKIA...`) | `<YOUR_API_KEY>` | * |
| Passwords in connection strings | `<YOUR_PASSWORD>` | * |
| Hardcoded tokens (not `${VAR}` references) | `<YOUR_TOKEN>` | * |
| `.pgpass` file contents | Redact password field | instructions/* |
| Private key file paths (`*.pem`, `*.key`) | `<PATH_TO_KEY>` | * |

### High: Personal Identifiers

| Pattern | Replacement | Scope |
|---------|-------------|-------|
| Your full name | `Your Name` | * |
| Your GitHub username | `your-github-username` | CLAUDE.md |
| Your Discord handle | `your-discord-username` | CLAUDE.md |
| Your email addresses | `you@example.com` | * |
| Teammate real names | `Teammate Name` | * |
| Teammate GitHub/Discord handles | `teammate-github` / `teammate-discord` | CLAUDE.md |

### High: Infrastructure Details

| Pattern | Replacement | Scope |
|---------|-------------|-------|
| AWS Account IDs (`\d{12}`) | `123456789012` | instructions/* |
| RDS/database hostnames | `your-db-host.region.rds.amazonaws.com` | instructions/* |
| EC2/server IP addresses | `<YOUR_SERVER_IP>` | instructions/* |
| S3 bucket names | `your-bucket-name` | instructions/* |
| Lambda function names | `YourFunctionName` | instructions/* |
| Amplify App IDs | `<YOUR_APP_ID>` | instructions/* |
| Domain names (company) | `yourdomain.com` | instructions/* |
| Route53 hosted zones | `<YOUR_HOSTED_ZONE>` | instructions/* |

### Medium: Local Environment

| Pattern | Replacement | Scope |
|---------|-------------|-------|
| Home directory (`/home/<user>`, `/Users/<user>`) | `~` or `/home/<YOUR_USER>` | * |
| Project-specific absolute paths | `/path/to/project` | * |
| Specific product/app names | `YourApp` or remove section | CLAUDE.md |
| Company name | `YourCompany` | * |
| Screenshot storage paths | `_screenshots` (keep symlink name, remove target) | CLAUDE.md |
| Dropbox/cloud storage paths | `<YOUR_SECURE_STORAGE>` | instructions/* |

### Medium: settings.json Specific

| Pattern | Replacement | Scope |
|---------|-------------|-------|
| Project-specific `Bash(git -C /specific/path ...)` entries | Remove entirely | settings.json |
| Project-specific `Bash(then tail ... /specific/path)` entries | Remove entirely | settings.json |
| `Bash(if [ -f /specific/path ...])` entries | Remove entirely | settings.json |
| `Read(//home/<user>/...)` | `Read(//home/<YOUR_USER>/...)` | settings.json |
| `trustedWorkspaces` array entries | Remove or empty array | settings.json |
| `feedbackSurveyState` | Remove entirely | settings.json |

## Verification Patterns

After sanitization, grep for these patterns to catch leaks. **None should match:**

```
# Personal info (customize these for each user)
your-actual-name
your-actual-email@
your-github-handle

# Infrastructure
\d{12}                    # AWS account IDs (12-digit numbers)
\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}  # IP addresses
\.rds\.amazonaws\.com     # RDS endpoints
s3://                     # S3 bucket references
/home/<your-actual-user>  # Home directory

# Secrets
sk-[a-zA-Z0-9]{20,}      # OpenAI-style keys
AKIA[A-Z0-9]{16}          # AWS access keys
ghp_[a-zA-Z0-9]{36}       # GitHub PATs
```

## How to Add User-Specific Rules

Before first sync, the user should customize this file by adding their personal patterns:

```markdown
### User-Specific Rules

| Pattern | Replacement | Scope |
|---------|-------------|-------|
| `John Smith` | `Your Name` | * |
| `johnsmith` | `your-github-username` | CLAUDE.md |
| `john@company.com` | `you@example.com` | * |
| `/home/john` | `/home/<YOUR_USER>` | * |
| `MyCompany Inc` | `YourCompany` | * |
| `mycompany.com` | `yourdomain.com` | instructions/* |
```

Fill in your actual values on the left side. The sync skill uses these to find and replace.

## Files That Should Not Be Synced

Some files contain too much private information to sanitize effectively:

- **AWS infrastructure docs** (`instructions/aws-*.md`) - Account IDs, endpoints, email forwarding maps, Lambda code
- **Deployment scripts** - Server IPs, SSH keys, deploy paths
- **Database schema docs** - Table structures may reveal business logic
- **Session/history files** - Conversation logs

For these, either exclude entirely or create a heavily redacted version manually.

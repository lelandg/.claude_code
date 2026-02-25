# Credentials and Secrets Management

Reference for managing API keys, passwords, and secrets securely.

**CRITICAL**: Never store API keys, passwords, or credentials in project directories.

## Standard Pattern

Store credentials in platform-specific user config directories **outside the project**:

- **Windows**: `%APPDATA%\Roaming\{AppName}\config.json`
- **macOS**: `~/Library/Application Support/{AppName}/config.json`
- **Linux**: `~/.config/{AppName}/config.json`

## Implementation Template

When creating configuration management for a new project:

1. **Create `config/user_config.py`** with `UserConfigManager` class:
   - `_get_config_dir()` - Returns platform-specific path
   - `load_config()` - Loads from user directory
   - `save_config()` - Saves to user directory
   - Include template generation function

2. **Update settings/config loading** to check user config as fallback:
   - Try environment variables first
   - Try project `.env` second (for non-secrets)
   - Fall back to user config directory for secrets

3. **Update `.gitignore`** to block common secret patterns:
   ```
   .env*
   !.env.example
   config.json
   secrets.json
   *.key
   *.pem
   *_credentials.json
   *_api_key.txt
   ```

4. **Create `config/README.md`** explaining:
   - Where config is stored
   - How to set it up
   - Configuration loading priority
   - Security notes

5. **Document in project CLAUDE.md** with:
   - User config location paths
   - Setup command (e.g., `python -m config.user_config`)
   - Configuration loading order

## Security Notes
- Project `.env` files can contain non-secret defaults, but **never** API keys or secrets
- Include encryption details only when explicitly requested
- Always use absolute paths (`Path.home()`) to locate config
- User config directory is outside git - must be backed up separately
- Create config directory with `mkdir(parents=True, exist_ok=True)`

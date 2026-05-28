# Development

This project uses [uv](https://docs.astral.sh/uv/) for package management and
[pre-commit](https://pre-commit.com/) for code quality checks.

## Setup

```zsh
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repo and install all dev dependencies
uv sync --group dev

# Install pre-commit hooks
uv run pre-commit install
```

## Common Commands

```zsh
# Run tests
uv run pytest

# Run linter
uv run ruff check .

# Run formatter
uv run ruff format .

# Run all pre-commit hooks manually
uv run pre-commit run --all-files

# Add a dev dependency
uv add --dev <package>
```

## Pre-commit Hooks

The following hooks run automatically on every commit:

| Hook | Purpose |
|---|---|
| `trailing-whitespace` | Remove trailing whitespace |
| `end-of-file-fixer` | Ensure files end with a newline |
| `check-yaml` | Validate YAML syntax (`services.yaml`, etc.) |
| `check-json` | Validate JSON syntax (`manifest.json`, `hacs.json`, etc.) |
| `check-added-large-files` | Prevent committing large files |
| `check-merge-conflict` | Catch merge conflict markers |
| `debug-statements` | Flag leftover `breakpoint()` / `pdb` calls |
| `ruff` | Lint Python code (with auto-fix) |
| `ruff-format` | Format Python code |

Tests (`pytest`) run automatically on `git push` (pre-push stage).

## CI

GitHub Actions runs on every push/PR to `main`:
- **HACS** — validates HACS compatibility
- **Hassfest** — validates `manifest.json` and integration structure
- **Ruff** — linting and format checks
- **Tests** — runs `pytest`

## Creating a Release

Releases are created by pushing a Git tag. The tag name drives everything —
HACS uses it as the version users see and install.

**Steps:**

1. Bump `version` in `custom_components/warema_ewfs/manifest.json` to the new version (e.g. `0.2.0`).
2. Commit the change:
   ```zsh
   git add custom_components/warema_ewfs/manifest.json
   git commit -m "chore: bump version to 0.2.0"
   git push
   ```
3. Create and push a matching tag:
   ```zsh
   git tag v0.2.0
   git push origin v0.2.0
   ```
4. The `release.yml` workflow runs automatically, verifies the tag matches
   `manifest.json`, and creates a GitHub Release with auto-generated release notes.

> The tag **must** match `manifest.json` exactly (tag `v0.2.0` → version `0.2.0`).
> The workflow will fail with an error if they differ.

HACS picks up the new release within minutes and makes it available for users to install or update.

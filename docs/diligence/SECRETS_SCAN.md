# Secret Scanning and Leak Response Policy

This document outlines the policy, tools, and processes for detecting, preventing, and remediating committed secrets in the Consultaion codebase.

## Automated Prevention (CI Gate)

We use `gitleaks` in our GitHub Actions CI pipeline to scan every pull request.
- The scan is **blocking** (configured with `continue-on-error: false`).
- If any secret signature or credential pattern is detected, the PR build fails and cannot be merged until resolved.

## Local Secret Detection

Developers are encouraged to scan their changes locally before pushing.

### Full-History Scan Command

To scan the entire git history of the repository locally, run:
```bash
gitleaks detect --source . --log-opts="--all" --redact
```

This checks all commits, branches, and merges for credential signatures.

## Incident Response & Remediating Leaks

If a secret is inadvertently committed to the repository (either on a branch or to `main`), the following response protocol must be followed immediately:

### 1. Key Revocation and Rotation (Critical)
**Committed credentials must be treated as immediately compromised.**
- Do not merely delete the credential from the code in a new commit.
- Immediately revoke/deactivate the key or secret at the provider level.
- Provision a new credential and update necessary deployment environments (Vercel, Render, local `.env`).

### 2. Rewriting Git History (Sanitization)
Once the key is rotated, the historical commit containing the plaintext secret must be purged from the repository's git history to prevent attackers from mining old commits.
- **Preferred Tool**: Use `git-filter-repo` (do not use legacy tools like BFG Repo-Cleaner or `git filter-branch`, which are deprecated and error-prone).
- Command to purge a file or specific pattern:
  ```bash
  # Install git-filter-repo (e.g. via pip or brew)
  pip install git-filter-repo

  # Purge a specific file containing secrets from all history
  git filter-repo --path path/to/compromised_file.txt --invert-paths
  ```
- After rewriting history, coordinate with the team to force-push the sanitized branch, ensuring everyone re-clones or resets their local checkouts to the rewritten upstream commits.

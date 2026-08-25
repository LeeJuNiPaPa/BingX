# CHANGELOG & README Sync Rule

Whenever new features, bug fixes, or updates are implemented in this repository:

1. **Update `CHANGELOG.md`**:
   - Document new versions and changes under clear version headings (`## [vX.Y.Z] - YYYY-MM-DD`).
2. **Sync into `README.md`**:
   - Run `python scripts/sync_changelog.py` to automatically embed the updated `CHANGELOG.md` content into `README.md`.
3. **Commit & Push**:
   - Commit all updated code files along with `CHANGELOG.md` and `README.md` and push to GitHub so the GitHub repository main page is always up to date.

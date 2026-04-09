<!-- SPDX-License-Identifier: Attribution-NonCommercial-ShareAlike (CC BY-NC-SA) -->

# Contributing

This document covers the process for contributing to ERM.

---

## Before You Start

- Read the [license](../LICENSE). All contributions must be compatible  
  with the Attribution-NonCommercial-ShareAlike (CC BY-NC-SA) license.  
- If you are using an AI coding assistant, read  
  [coding-assistants.md](coding-assistants.md) before submitting.  
- Set up your local environment using [setup.md](setup.md).  

---

## Workflow

1. Fork the repository and create a branch from `main`.  
2. Make your changes.  
3. Run the test suite locally with `pytest` before pushing.  
4. Open a pull request against `main` with a clear description of  
   what changed and why.  

---

## Branch Naming

Use a short, descriptive name prefixed with the type of change:

- `fix/` — Bug fixes  
- `feat/` — New features  
- `refactor/` — Code restructuring without behavior changes  
- `docs/` — Documentation changes only  
- `chore/` — Dependency updates, CI changes, and similar maintenance  

Example: `fix/shift-end-break-overlap`

---

## Commit Messages

Write commits in the imperative mood and keep the subject line  
under 72 characters.

```
Add quota enforcement to shift types
Fix break duration calculation on overnight shifts
Remove unused LOA reminder fallback
```

Do not use `Signed-off-by` tags unless you are a human contributor  
certifying the Developer Certificate of Origin (DCO). See  
[coding-assistants.md](coding-assistants.md) for details on AI attribution.

---

## Code Style

- Python 3.12. Match the style of the surrounding code.  
- All database calls must be `async`. Use `await` throughout — do not  
  use blocking pymongo calls.  
- Use `discord.ext.tasks.loop` for new background tasks. Register  
  them in `utils/task_loader.py`.  
- New interactive Discord flows belong in `menus.py`. Check there  
  before creating a new file for a View or Modal.  
- Use `utils/constants.py` for shared colour values (`BLANK_COLOR`,  
  `GREEN_COLOR`, `RED_COLOR`) rather than hardcoding hex values.  
- Use `decouple.config()` for all environment variable access.  

---

## Tests

The test suite lives in `test_erm.py`. `helpers.py` provides mock  
infrastructure for the `Bot` class and Discord objects.

Run all tests:

```bash
pytest
```

CI runs `pytest` and `flake8` (with `--exit-zero`) on every push  
via the GitHub Actions workflow in `.github/workflows/app.yaml`.

---

## Pull Request Checklist

- [ ] `pytest` passes locally  
- [ ] No new blocking `flake8` errors introduced  
- [ ] New environment variables added to `.env.template` with a comment  
- [ ] New background tasks registered in `utils/task_loader.py`  
- [ ] DCO certified with a `Signed-off-by` tag (human contributors only)  

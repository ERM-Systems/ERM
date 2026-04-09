<!-- SPDX-License-Identifier: Attribution-NonCommercial-ShareAlike (CC BY-NC-SA) -->

# Testing

This document covers how to run ERM's test suite and how the  
test infrastructure is structured.

---

## Running Tests

```bash
pytest
```

A minimal set of environment variables is required:

```
ENVIRONMENT=PRODUCTION
PRODUCTION_BOT_TOKEN=anystring
MONGO_URL=mongodb://localhost:27017/test
```

These can be set in a `.env` file or exported directly in the shell.  
The `MONGO_URL` can point to a local MongoDB instance or any test  
database — the test suite does not require a live Discord connection.

---

## CI

Tests run automatically on every push via the GitHub Actions workflow  
in `.github/workflows/app.yaml`. The workflow uses Python 3.12,  
installs dependencies from `requirements.txt`, and runs `pytest`.

`flake8` also runs with `--exit-zero`, meaning linting issues are  
reported in CI output but do not fail the build.

---

## Test Infrastructure

`helpers.py` provides mock infrastructure for writing tests against  
bot internals without a live Discord connection.

### `HashableMixin`

Provides `__hash__` and equality for mock Discord objects. Used as  
a base for mocked guilds, members, channels, and similar objects  
that discord.py expects to be hashable.

### `ColourMixin`

Aliases `.color` to `.colour` on mock objects, matching discord.py's  
aliasing behavior.

### Bot mocking

To test cog logic or event handlers, construct a mock `Bot` instance  
using the helpers in `helpers.py` rather than spinning up a real  
Discord connection. All loggers are set to `CRITICAL` level by default  
in the test environment to keep output clean.

---

## Notes

- The test suite is minimal. When adding new features, add  
  corresponding tests in `test_erm.py`.  
- Avoid tests that require live network access to Discord, Roblox,  
  or MongoDB Atlas. Use mocks or a local MongoDB instance.  

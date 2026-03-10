# ADR 001: Playwright E2E Testing Against Docker Compose

## Status

Accepted

## Context

The reference template needs end-to-end tests to validate that the full stack
works together. This serves two purposes: catching integration issues, and
providing a pattern that template users can build on.

Key constraints:
- Tests must run the same way locally and in CI (GitHub Actions)
- The Docker Compose stack is already the standard development environment
- Setup should be minimal — this is a template, not a testing framework

## Decision

Use Playwright running in a Docker container against the Docker Compose stack.

- **Playwright in a container**, using the official
  `mcr.microsoft.com/playwright` image. Eliminates host-OS dependencies
  (NixOS missing libraries, macOS quirks). Same image works locally and in CI.
- **Docker Compose `test` profile.** The Playwright container only starts on
  demand (`docker compose --profile test run --rm playwright`), not during
  normal `docker compose up`.
- **Docker Compose networking.** Playwright connects to Caddy at
  `http://caddy:3000` via the internal network — no exposed ports needed.
- **Docker Compose stack with healthchecks.** All three services (api, ui,
  caddy) declare healthchecks so `docker compose up --wait` blocks until the
  stack is ready. The Playwright service depends on Caddy being healthy.
- **Single browser (Chromium).** Sufficient for a reference template. Template
  users can add Firefox/WebKit later.
- **Minimal test suite.** One happy-path test demonstrates the pattern. The
  wiring (config, healthchecks, CI steps) is the real value.

## Consequences

- Docker Compose services must maintain healthcheck endpoints. The API uses a
  TCP socket check; the UI and Caddy use HTTP checks.
- `docker compose up --wait` requires `--wait-timeout 120` in CI because the
  first run installs dependencies inside containers (up to 90 seconds).
- The Playwright container installs npm dependencies on each run (cached by a
  named volume). First run is slower; subsequent runs reuse the volume.
- The Playwright image version must match the `@playwright/test` version in
  `package.json`. Mismatched versions will fail to locate browser executables.

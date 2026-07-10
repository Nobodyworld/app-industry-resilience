# Security Policy

## Supported Versions

The U.S. Industry Cost Structure & Resilience Dashboard is developed and released from the `main` branch. Security updates are applied to the current `main` branch and the most recent release only. Older tags are not maintained.

## Reporting a Vulnerability

Please report suspected security vulnerabilities privately so they can be investigated without exposing users or maintainers to unnecessary risk.

1. Open the repository **Security** tab and use **Report a vulnerability** when private vulnerability reporting is available.
2. If that option is unavailable, contact the repository owner through a private contact method published on the [Nobodyworld GitHub profile](https://github.com/Nobodyworld).
3. Include affected versions or commit SHAs, reproduction steps, impact, relevant logs, and any suggested mitigation.

Do not open a public issue, discussion, or pull request containing vulnerability details.

Reports are handled on a best-effort basis. The maintainer aims to acknowledge a complete report within five business days, but this open-source project does not provide a response-time SLA.

## Coordinated Disclosure

Please allow a reasonable remediation period before publishing vulnerability details. After a fix is available, the project may:

1. Communicate remediation steps directly to the reporter.
2. Publish a GitHub Security Advisory or changelog entry describing the impact and resolution.
3. Credit the reporter when requested.

## Dependency Monitoring

- Run `make security` (`pip-audit` plus `detect-secrets`) when dependencies change and during release validation.
- Track runtime and development dependencies in [DEPENDENCIES.md](../DEPENDENCIES.md).
- Document mitigations and remediation timelines for high or critical vulnerabilities in `docs/execplans/` and reference completed remediation in `CHANGELOG.md`.

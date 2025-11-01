# Security Policy

## Supported Versions

The Idiot Index application is developed and released from the `main` branch. Security updates are applied to the most recent release and the current `main` branch only. Older tags are not maintained.

## Reporting a Vulnerability

Please report suspected security vulnerabilities privately so we can triage and respond without exposing users to unnecessary risk.

- Email: [security@idiot-index.app](mailto:security@idiot-index.app)
- Subject: `SECURITY: <short summary>`
- Include: affected versions (if known), reproduction steps, impact assessment, and any suggested mitigations.

We acknowledge reports within **2 business days** and aim to provide an initial assessment or mitigation plan within **7 business days**. If you do not receive a timely response, please follow up using the same email thread.

## Coordinated Disclosure

We prefer coordinated disclosure. After a fix is available, we will:

1. Communicate remediation steps directly with the reporter.
2. Publish an advisory (GitHub Security Advisory or CHANGELOG entry) summarizing the impact and resolution.
3. Credit the reporter if they wish to be acknowledged.

Please do not create public GitHub issues for vulnerabilities. For questions about this policy, contact the maintainers via [maintainers@idiot-index.app](mailto:maintainers@idiot-index.app).

## Dependency monitoring

- Run `make security` (pip-audit + detect-secrets) monthly or when upgrading dependencies.
- Track runtime and development dependencies in [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md). The register records license information, review cadence, and data-source obligations.
- Document mitigations and remediation timelines for any high or critical CVEs in `REPORTS/` and reference them in `CHANGELOG.md` once resolved.

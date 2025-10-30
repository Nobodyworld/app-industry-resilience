# Stage 5 – Dependency Alignment Audit

## Inputs
- `MASTER-VERSIONS.json`
- `requirements.txt`
- `requirements-dev.txt`

## Summary
All monitored Python runtime and development dependencies match the organization master versions. No upgrades or pin adjustments
are required for Phase 1 defaults.

## Runtime Dependencies
| Package | Target Version | Repository Specifier | Status |
| --- | --- | --- | --- |
| streamlit | 1.39.0 | >=1.39.0,<2 | ✅ Aligned |
| pandas | 2.2.2 | >=2.2.2,<3 | ✅ Aligned |
| python-dotenv | 1.0.1 | >=1.0.1,<2 | ✅ Aligned |
| requests | 2.32.3 | >=2.32.3,<3 | ✅ Aligned |
| plotly | 6.3.1 | >=6.3.1,<7 | ✅ Aligned |
| pytest | 8.4.2 | >=8.4.2,<9 | ✅ Aligned |
| redis | 5.0.1 | >=5.0.1,<8 | ✅ Aligned |
| botocore | 1.34.69 | >=1.34.69,<2 | ✅ Aligned |

## Development Dependencies
| Package | Target Version | Repository Specifier | Status |
| --- | --- | --- | --- |
| black | 24.8.0 | >=24.8.0,<26 | ✅ Aligned |
| ruff | 0.6.9 | >=0.6.9,<1 | ✅ Aligned |
| mypy | 1.11.2 | >=1.11.2,<2 | ✅ Aligned |
| pytest-cov | 5.0.0 | >=5.0.0,<8 | ✅ Aligned |
| pre-commit | 3.7.0 | >=3.7.0,<5 | ✅ Aligned |
| codespell | 2.3.0 | >=2.3.0,<3 | ✅ Aligned |
| commitizen | 3.27.0 | >=3.27.0,<5 | ✅ Aligned |
| detect-secrets | 1.5.0 | >=1.5.0,<2 | ✅ Aligned |
| pip-audit | 2.7.3 | >=2.7.3,<3 | ✅ Aligned |
| types-requests | 2.32.0 | >=2.32.0,<3 | ✅ Aligned |
| fakeredis | 2.23.2 | >=2.23.2,<3 | ✅ Aligned |

## Notes
- Compatible specifiers remain preferred for this repository; pinning will be re-evaluated after modernization milestones if
  reproducibility requirements change.
- Future dependency additions must update `MASTER-VERSIONS.json` alongside the requirements files.

# Streamlit Community Cloud deployment

This runbook defines the first public hosted deployment for the U.S. Industry Cost Structure & Resilience Dashboard. It covers only the Streamlit UI. Public hosting of the headless API is a separate future decision.

## Deployment contract

Use these coordinates for the public app:

- Repository: `Nobodyworld/app-industry-resilience`
- Branch: `main`
- Entrypoint: `app.py`
- Python: `3.13`
- Dependency file: root `requirements.txt`
- Streamlit configuration: root `.streamlit/config.toml`
- Required secrets for the default public experience: **none**

The default public experience must remain usable with the bundled `Sample (offline)` dataset and committed contextual snapshots. Do not add BEA or Census credentials merely to make the public deployment work.

Streamlit Community Cloud runs the app from the repository root, which matches the repository's tested path assumptions. The deployment must explicitly select Python 3.13 because Community Cloud's default Python version may differ from the repository requirement.

Official references:

- <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy>
- <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization>
- <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies>

## Repository readiness

Before external deployment, require all of the following on the exact candidate `main` commit:

1. CI / Quality Gate passes under Python 3.13.
2. Docker Deployment Smoke passes.
3. Redis Compatibility passes when applicable to the candidate.
4. The non-Docker CI startup smoke starts `streamlit run app.py` from the repository root and reaches `/_stcore/health` without credentials.
5. Streamlit AppTest coverage remains green so the script itself is executed hermetically, not merely the web server process.
6. No secret or private configuration is committed.

The startup smoke complements, rather than replaces, AppTest and Docker coverage. A healthy Streamlit server alone does not prove every interactive path works.

## Create the Community Cloud app

This step requires the owner's Streamlit account linked to GitHub.

1. Open Streamlit Community Cloud and choose **Create app**.
2. Select or enter `Nobodyworld/app-industry-resilience`.
3. Select branch `main`.
4. Select entrypoint `app.py`.
5. Choose an available `*.streamlit.app` subdomain. Do not document a guessed URL.
6. Open **Advanced settings** and select Python `3.13`.
7. Leave the secrets field empty for the initial public deployment.
8. Record the exact `main` commit SHA being deployed.
9. Deploy.

Do not change repository dependency floors, disable TLS/security checks, or add provider credentials in response to a deployment failure. Capture the deployment/build log and fix the actual incompatibility through a reviewed repository change.

## Hosted acceptance

After the app reports ready, verify the public URL in a fresh browser session.

Required checks:

- initial page loads without authentication or provider credentials;
- `Sample (offline)` is available and the first-run experience renders without an exception;
- Overview, Explore, Compare, Scenario Lab, and Industry Momentum are reachable;
- Scenario Lab accepts a non-zero adjustment, produces a result, and resets;
- Data provenance opens and contains no secret values, local paths, uploaded filenames, or unexpected private metadata;
- Industry Momentum renders its committed contextual data and clearly preserves partial/unmapped states;
- CSV/JSON/XLSX download controls used by the public walkthrough still produce valid files where the browser permits them;
- browser refresh/reload restores a usable application state;
- a narrow mobile-width view remains usable without blocking navigation;
- no BEA/Census credential is required for the default demo;
- no application error, secret, traceback, or private filesystem path appears in the UI.

Record the deployed commit SHA, public URL, browser/version, viewport(s), checks performed, limitations, and any Streamlit platform warnings in issue #139.

## Publish the URL

Only after hosted acceptance passes:

1. Add the verified `https://<subdomain>.streamlit.app/` URL to the repository README.
2. Set the GitHub repository homepage to the same verified URL.
3. Update issue #139 with the deployed SHA and acceptance evidence.

Do not move or republish the v0.4.0 tag/release merely because `main` now has a hosted demo.

## Updating the app

Community Cloud tracks the configured GitHub branch and redeploys application changes from that branch. `main` remains the deployment source; do not create a separate long-lived deployment branch.

Dependency-file changes can trigger a full environment rebuild. Treat deployment failures after a dependency change as a release/readiness regression and restore a green `main` through a normal reviewed fix rather than editing the hosted environment manually.

## Python upgrades

Python is selected during Community Cloud deployment. Streamlit documents that changing the Python version of an existing app requires deleting and redeploying the app. Before any future Python-version change, record the current subdomain, GitHub coordinates, and secrets posture so the app can be recreated deliberately.

## Rollback and recovery

If a new `main` commit breaks the hosted app:

1. Capture the failing deployed SHA and Community Cloud logs.
2. Determine whether the failure is repository code/dependency behavior or a platform incident.
3. Fix forward through a reviewed PR when practical.
4. If an urgent rollback is required, use the repository's normal owner-approved Git history/revert process; do not rewrite `main` or move published release tags.
5. Re-verify the hosted URL after Community Cloud observes the corrected `main`.

The public demo is a convenience surface for the current application, not a new release identity or a source of truth separate from GitHub `main`.

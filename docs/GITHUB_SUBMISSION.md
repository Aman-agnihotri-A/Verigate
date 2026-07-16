# GitHub and Submission Steps

## 1. Perform a local secret check

Before committing, confirm that `.env` is not tracked and that only `.env.example` is included:

```powershell
git status
git ls-files .env
```

The second command should print nothing. Never commit real MongoDB credentials, admin keys, or Flask secrets.

## 2. Run the final checks

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q
```

Expected result:

```text
187 passed
```

With MongoDB running locally, also verify:

```powershell
copy .env.example .env
python scripts/seed.py
python run.py
```

In another terminal, run:

```powershell
python scripts/load_test.py
```

Then call the MIS endpoints from `docs/curl_examples.md` and confirm Alpha Bank has rate-limited hits and Nova HR has blocked-IP hits.

## 3. Create the private GitHub repository

1. Sign in to GitHub.
2. Select **New repository**.
3. Name it `verigate-assignment`.
4. Set visibility to **Private**.
5. Do not initialize it with a README, license, or `.gitignore`, because those files already exist locally.
6. Create the repository.

## 4. Connect and push the local project

Open PowerShell in the project folder:

```powershell
git init
git branch -M main
git add .
git status
git commit -m "feat: complete VeriGate verification gateway"
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/verigate-assignment.git
git push -u origin main
```

Replace `<YOUR_GITHUB_USERNAME>` with your GitHub username.

## 5. Preserve meaningful commit history

The assignment requests at least ten meaningful commits. If your working repository already has those commits, push that repository rather than creating a single new history from this ZIP.

Do not fabricate dates or misleading work. If this clean package is being added to the existing project repository, commit the final changes separately, for example:

```powershell
git add app/vendors app/verification.py app/models/api_log.py app/audit/repository.py tests
git commit -m "feat: audit primary and fallback vendor attempts"

git add scripts/load_test.py scripts/seed.py
git commit -m "test: make TPS load demonstration reproducible"

git add README.md docs
git commit -m "docs: finalize assessment and submission guidance"

git push
```

## 6. Invite the reviewer

In the private repository:

1. Open **Settings**.
2. Open **Collaborators** or **Collaborators and teams**.
3. Select **Add people**.
4. Enter the GitHub handle supplied in the assessment/submission form.
5. Send the invitation.

## 7. Final repository check

Confirm the GitHub repository contains:

- `app/`
- `scripts/seed.py`
- `scripts/load_test.py`
- `tests/`
- `README.md`
- `CLAUDE.md`
- `docs/AI_WORKFLOW.md`
- `docs/ASSUMPTIONS.md`
- `docs/DEPLOYMENT.md`
- `docs/curl_examples.md`
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`

Confirm it does **not** contain:

- `.env`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- emergency `.jsonl` logs
- real credentials or personal identity data

## 8. Submit

Use the submission link you received. Provide the private GitHub repository URL and any requested details. Keep the repository private, but ensure the reviewer invitation has been accepted or remains pending for the correct account.

A suitable repository description is:

> Flask and MongoDB verification API gateway with API-key authentication, IP whitelisting, TPS limiting, simulated vendor failover, PII-safe auditing, and MIS analytics.

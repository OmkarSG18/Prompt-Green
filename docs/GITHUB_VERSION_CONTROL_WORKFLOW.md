# PromptGreen Version 2 — Continuous GitHub Version Control Workflow Policy

**Active Repository:** `https://github.com/OmkarSG18/Prompt-Green`  
**Remote Name:** `origin` (`https://github.com/OmkarSG18/Prompt-Green.git`)  
**Version 1 Baseline Branch:** `main` (Immutable production baseline)  
**Version 2 Development Branch:** `version-2` (Active feature branch tracking `origin/version-2`)  
**Physical Backup:** `D:\EDU\DSU\Major project\PromptGreen.zip` (Immutable, untouched)  

---

## 1. Core Principles & Safety Rules

1. **Version 1 Immutability:** Never overwrite, rewrite, or commit Version 2 code to `main`. The `main` branch preserves the baseline Version 1 capstone submission.
2. **Dedicated Version 2 Branch:** All Version 2 development, testing, and continuous synchronization occurs exclusively on `version-2`.
3. **No Destructive Git Commands:**
   - Never use `git reset --hard`.
   - Never use `git clean -fd`.
   - Never use `git push --force` or `git push --force-with-lease`.
   - Never rewrite Git history or rebase published commits.
4. **No Premature or Unreviewed Commits:** Never automatically stage or push unreviewed changes. Group logically related, tested changes into structured semantic commits.
5. **No Secret or Artifact Leakage:** Never commit `.env` files, API keys, credentials, local SQLite databases (`*.db`), virtual environments, or downloaded neural model weights.
6. **Physical Backup Preservation:** `PromptGreen.zip` must never be modified, extracted over the repository, regenerated, or deleted.

---

## 2. Continuous Synchronization Lifecycle

During the entire 4-day development lifecycle, every completed and verified milestone must follow this structured synchronization pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                 Antigravity Implementation                  │
│   (Write clean code conforming to Thesis & Roadmap)         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Git Modification Check                    │
│   (Inspect `git status`, verify zero unintended edits)       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                Full Regression Verification                 │
│   (Run `pytest -p no:langsmith -v` & `verify_engine.py`)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Git Diff Inspection                     │
│   (Audit staged changes with `git diff --cached --stat`)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      Approved Commit                        │
│   (Create semantic commit e.g. `feat(v2): ...`)             │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  Push to origin/version-2                   │
│   (Fast-forward push: `git push origin version-2`)          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  Remote Branch Verification                 │
│   (Verify GitHub commit hash & tree integrity)              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Four-Day Development Milestone Roadmap & Commit Schema

### Day 1: 4-Stage Optimization Pipeline (`promptgreen/optimizer/`)
- `feat(v2): implement structural prompt pruning` (Stage 1 & 1.1)
- `feat(v2): integrate extractive token compression` (Stage 2)
- `feat(v2): add local SLM output directive shaper` (Stage 3)
- `feat(v2): implement semantic fidelity cosine guardrail` (Stage 4)
- `feat(v2): orchestrate 4-stage optimization pipeline` (Pipeline integration)
- `test(v2): add 4-stage optimizer regression test suite`

### Day 2: Thermodynamic Carbon Engine & Model Routing (`promptgreen/engine/`, `predictor/`)
- `feat(v2): model prefill vs decode thermodynamic energy`
- `feat(v2): implement net carbon abatement and cooling water footprint`
- `feat(v2): build green model tier down-router`
- `test(v2): verify physical energy benchmarks and routing logic`

### Day 3: Asynchronous Backend & Telemetry Ledger (`promptgreen/api/`, `ledger/`)
- `feat(v2): upgrade FastAPI server to async REST endpoints`
- `feat(v2): abstract LedgerRepository with SQLite WAL support`
- `feat(v2): upgrade CLI with green prompt optimizer command`
- `feat(v2): create 240-prompt benchmark evaluation suite`
- `test(v2): add async API and benchmark verification tests`

### Day 4: Green Prompt Studio & Final Verification (`frontend/`, `docs/`)
- `feat(v2): scaffold Next.js 15 Green Prompt Studio UI`
- `feat(v2): implement real-time Monaco diff editor and token telemetry`
- `test(v2): end-to-end integration verification`
- `docs(v2): finalize v2 capstone thesis demonstration guide`

---

## 4. Emergency & Failure Procedures

- **Push Rejection (Non-Fast-Forward):** If `git push origin version-2` fails, stop immediately. Do not force push. Inspect `git fetch origin version-2` and compare commit histories.
- **Test Failure:** If any unit or regression test fails, do not commit. Diagnose and resolve the defect before staging.
- **Accidental Switch to Main:** If active branch is `main`, do not make edits or commits. Run `git checkout version-2`.

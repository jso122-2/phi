# environment

#code #hub

Mamba Python 3.11 environment — the substrate everything else runs in.

---

## Connections

→ [[CODE]] ← code hub  
→ [[HOME]] ← grand central  
→ [[mcp-server]] — server runs inside this environment  

---

## Setup

```bash
mamba env create -f environment.yml
mamba activate spotify-rip
```

---

## `environment.yml`

```yaml
name: spotify-rip
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - pip
  - numpy>=1.26
  - scipy>=1.12
  - matplotlib>=3.8
  - pip:
      - pytest>=8.0
      - pytest-cov>=5.0
      - mcp>=1.0
      - -e .
```

---

## Package hierarchy

| Layer | Packages | Install via |
|---|---|---|
| Scientific | numpy, scipy, matplotlib | conda-forge |
| MCP protocol | mcp>=1.0 | pip |
| Testing | pytest, pytest-cov | pip |
| This project | -e . (editable) | pip |
| **Forbidden** | torch, torchvision, torchaudio | — never add |

---

## `pyproject.toml` — key sections

```toml
[project.scripts]
spotify-rip-mcp = "mcp_server.server:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"

[tool.setuptools.packages.find]
include = ["sims*", "workers*", "mcp_server*"]
```

---

## Rules for agents

1. Never add `torch`, `torchvision`, `torchaudio` to `environment.yml` or `pyproject.toml`.
2. Prefer `numpy` for numerical work.
3. New conda packages: `mamba install -c conda-forge <pkg>`.
4. `environment.yml` is the single source of truth — always update it when adding packages.

---

## Auto-linked

→ [[2025-05-11-042356-conda-commands]]
→ [[COMMANDS]]
→ [[2025-02-13-044420-conda-churn-final-env-packages]]
→ [[workers]]
→ [[agent-context]]
→ [[2025-09-24-132835-2025-09-24t23-28-36-054-10-00]]

→ [[index]]
→ [[2025-05-28-154122-dawn-test-1]]
→ [[2025-05-15-081254-2025-05-15t18-22-57-859-10-00]]
→ [[2025-09-09-072136-2025-09-09t17-21-36-865-10-00]]

→ [[2025-05-28-224414-2025-05-29t08-44-14-473-10-00]]
→ [[2025-05-19-163744-server-scribble]]
→ [[2025-10-06-150602-2025-10-07t02-07-04-211-11-00]]
→ [[2025-05-27-104057-visual-suite]]
→ [[2025-08-09-044150-soot-ash-residue-dynamics-in-dawn]]
→ [[2025-05-15-113345-pretty-code]]

→ [[keep]]
→ [[2025-02-20-075321-docker-and-celery-commands]]
→ [[2025-03-03-074553-gti-commands]]
→ [[2025-08-18-101454-security]]
→ [[2025-06-08-062357-fresh-termial-instate-gpt]]
→ [[2025-05-20-091739-linkedin-draft-20-5-25]]

→ [[2025-09-19-041208-neofetch]]
→ [[2025-08-12-011708-a-disiplined-rebillion]]
→ [[2025-12-13-062815-miler-coat-of-arms]]
→ [[2025-12-12-032609-formulas-1212-25]]
→ [[2025-12-13-051108-formulas-13-12-25]]
→ [[2025-06-08-063438-linux-first-checklist-8-6-25]]

→ [[2025-12-10-120936-2025-12-10t23-39-19-648-11-00]]
→ [[2025-08-12-045215-notes-for-thinkerbell-preso]]
→ [[2025-04-10-125121-tanatlus-prompt]]
→ [[2025-05-28-145651-2025-05-29t00-56-55-879-10-00]]
→ [[2025-05-20-052550-operator-scraping-prompts]]
→ [[2025-05-26-141917-dawn-tests]]

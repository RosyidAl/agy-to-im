# AGENTS.md — Development Guidelines & Pocock Engineering Skills

This repository follows the **Matt Pocock Engineering Discipline** and integrates portable Agent Skills (including Matt Pocock's skills and Perplexity AI skills).

Every AI agent working on this repository MUST adhere to these rules when developing, modifying, or debugging code.

---

## 1. Core Engineering Discipline (Matt Pocock Skills)

Whenever developing features or fixing bugs in this project, execute the appropriate workflow:

### A. Test-Driven Development (`.agents/skills/tdd/SKILL.md`)
- **Red**: Write a minimal failing test reproducing the bug or asserting the desired new feature behavior first.
- **Green**: Write the minimal production code needed to make the test pass.
- **Refactor**: Clean up the code while keeping tests green.
- **Verification**: Always execute the test suite (`pytest tests/`) and ensure 0 failures before declaring work done.

### B. Bug Diagnosis (`.agents/skills/diagnosing-bugs/SKILL.md`)
- Never guess or apply speculative patches.
- Formulate a clear hypothesis regarding the root cause.
- Trace the issue back to its source in the state, network, or event loop.
- Confirm the fix by re-running targeted unit tests.

### C. Architecture & Interface Design (`.agents/skills/codebase-design/SKILL.md`, `.agents/skills/to-spec/SKILL.md`)
- Design deep, clean interfaces: simple interface on the surface, robust implementation underneath.
- Keep module boundaries clean:
  - `src/state.py`: Atomic state persistence and serialization.
  - `src/commands.py`: Command routing, inline keyboards, user UI formatting.
  - `src/daemon.py`: Polling, lifecycle, queue, rate limiting, and execution dispatch.
  - `src/telegram.py`: Pure Telegram API client and HTML message formatting.
  - `src/turn.py` & `src/agy_runner.py`: Subprocess execution and streaming communication with the `agy` CLI.

### D. Code Review & Regression Prevention (`.agents/skills/code-review/SKILL.md`)
- Every change must maintain backward compatibility with existing `state.json` and `config.json` files.
- Preserved comments and docstrings must remain intact.
- Verify full test suite passes without regressions.

---

## 2. Research & Perplexity Integration (`.agents/skills/pplx-cli/SKILL.md`, `.agents/skills/research/SKILL.md`)

- When encountering unfamiliar APIs (e.g. Telegram Bot API updates, systemd user service behaviors, asyncio loop nuances):
  - Consult primary sources and official documentation.
  - Use Perplexity CLI / search tools (`.agents/skills/pplx-cli/SKILL.md`) to verify facts against live documentation.

---

## 3. Skill Catalog in this Project

Available local skills located in `.agents/skills/`:
- `tdd`: Test-driven development loop
- `diagnosing-bugs`: Root cause analysis and bug diagnosis
- `code-review`: Structured code quality and regression checks
- `codebase-design`: Architecture, interface design, and clean boundaries
- `grill-me` & `grill-with-docs`: Interactive alignment and plan stress-testing
- `to-spec` & `to-tickets`: Breaking down complex features into actionable specifications
- `pplx-cli` & `pplx-search-sdk`: Perplexity live search and facts retrieval
- `research`: In-depth investigation against primary documentation sources

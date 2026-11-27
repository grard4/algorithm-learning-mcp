# Algorithm Learning MCP

[简体中文（默认）](README.md) | English

> **Noncommercial source-available:** Noncommercial learning, research, modification, and sharing are permitted. Unauthorized commercial exploitation and unlawful resale are prohibited. The project uses [PolyForm Noncommercial License 1.0.0](LICENSE), with attribution to `grard4`. The license controls, including its express organizational-use provisions; this summary does not add a learning-only restriction or limit statutory rights. This is not an OSI open-source license.

A model-independent MCP server for algorithm and programming-contest learning. One server process can be connected by MCP-compatible clients; SQLite stores topic trees, learning progress, source-linked knowledge, tasks, change history, backups, and concept-link audit events.

> **Compatibility status:** Codex is the only installed client in the current test environment. Other clients are candidates until their own installation and tool calls are tested. See [the compatibility report](docs/AGENT_COMPATIBILITY.md).

## Features

- Independent topics under a shared logical root, with conversation mappings and cross-topic knowledge search.
- Layered context reads (manifest, current topic, relevant search, targeted history) and versioned deltas.
- Evidence-backed, idempotent learning updates with optimistic version checks and audit history.
- Incremental import of Codex rollout files as an optional Codex-specific adapter; it is disabled unless explicitly invoked. Other agents use the standard registration and update tools. See [sync and discovery limits](docs/SYNC_AND_DISCOVERY.md).
- User-editable natural-language learning preferences, read on demand.
- SQLite backup/restore/verification commands.
- Standard MCP tools over stdio and Streamable HTTP; no model provider is required by the server.

## Requirements

- Python 3.11 or newer (tested locally with Python 3.14.7).
- SQLite with JSON1 and FTS5 (the Python Windows build used here includes both).
- Any MCP client that supports the selected transport and tool schemas. Client support is not implied by protocol capability.

## Install on Windows

```powershell
git clone https://github.com/grard4/algorithm-learning-mcp.git
cd algorithm-learning-mcp
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item config\learning_preferences.example.md config\learning_preferences.md
python server.py
```

The first start creates a new empty database at `data/learning.sqlite3` (override with `ALGORITHM_KB`). No sample learner data is preloaded. For a reproducible isolated smoke check, see `tests/` and `docs/TEST_REPORT.md`.

## Configure an MCP client

Every installation should use its own `ALGORITHM_KB` and preferences path. Multiple client processes can share one local SQLite file when they belong to the same learner and host; SQLite serializes writes. For unrelated users, configure separate database files. Do not put a shared SQLite database on a network share.

Example Codex `config.toml` entry (replace the absolute paths with your own):

```toml
[mcp_servers.algorithm_learning]
command = "C:\\path\\to\\algorithm-learning-mcp\\.venv\\Scripts\\python.exe"
args = ["C:\\path\\to\\algorithm-learning-mcp\\server.py"]
cwd = "C:\\path\\to\\algorithm-learning-mcp"
[mcp_servers.algorithm_learning.env]
ALGORITHM_KB = "C:\\Users\\you\\AppData\\Local\\algorithm-learning\\learning.sqlite3"
ALGORITHM_PREFERENCES = "C:\\Users\\you\\AppData\\Local\\algorithm-learning\\learning_preferences.md"
```

Codex configuration is in the user's `config.toml` or project `.codex/config.toml`; see [Codex setup](docs/clients/codex.md). Other examples are indexed in [docs/clients](docs/clients/README.md). They are reference configurations only unless the compatibility report says otherwise.

For Streamable HTTP, set `ALGORITHM_MCP_TRANSPORT=streamable-http`; the default is `127.0.0.1:8000/mcp`. Non-loopback bindings now fail with UNSAFE_HTTP_BIND. Local HTTP remains supported, without built-in authentication or tenant isolation. Remote single-owner access requires an independently authenticated SSH tunnel; that deployment is not tested here. Never expose an unauthenticated forwarder. See [security notes](docs/SECURITY.md); stdio remains recommended locally.

## Learning preferences

Copy `config/learning_preferences.example.md` to `config/learning_preferences.md` and write natural-language teaching preferences. The server reads it through `get_learning_preferences` when requested and reloads changed files. Missing or empty files use a generic default. Keep your private file out of source control; `.gitignore` excludes it.

Fixed writing and course-formatting rules live in `course_rules.py`, are included directly in MCP initialization instructions, and can also be read through `get_course_rules`. Deleting or editing preferences cannot change these rules. Their task scopes and explicit exceptions remain applicable. See [built-in course rules](docs/COURSE_RULES.md) for migration and enforcement boundaries: delivery of instructions is not a guarantee that an external client or model follows them.

The server does not dictate a model. **Recommended teaching model:** GPT-6-Astra, Medium or High reasoning. Algorithm teaching involves building complete knowledge structures, rigorous mathematical derivations, algorithm correctness and complexity proofs, and reliable code. Users may choose another model; reasoning, knowledge accuracy, context handling, and teaching quality can differ. Other models may provide shallower explanations, less rigorous derivations, or incorrect code; users are responsible for checking those outputs. This recommendation is not a server requirement.

## Main tools

| Tool | Use |
|---|---|
| `register_conversation` | Associate a real conversation ID with an existing or new topic. |
| `get_context_manifest` | Read the lightweight global index or a single conversation mapping. |
| `get_topic_context`, `get_context_delta`, `get_topic_version` | Read current topic summary/version and incremental updates. |
| `search_knowledge`, `read_knowledge` | Search cross-topic knowledge, then fetch targeted details. |
| `update_learning` | Atomically record evidence-backed progress, knowledge, tasks, and relations. |
| `get_global_overview` | Read a compact or explicitly requested full overview. |
| `get_learning_preferences` | Read user preferences without requiring a particular model. |
| `get_course_rules` | Read versioned built-in course rules; no mutation endpoint exists. |
| `search_concept_knowledge`, `read_concept_link`, `get_concept_changes` | Read approved concept links and their source invalidations; link does not imply mastery. |
| `get_conversation_history` | Read targeted original messages in pages. |
| `rollback_update`, `get_update_history`, `detect_knowledge_conflicts` | Audit and manage prior updates. |

Full schemas and examples are discoverable through MCP `tools/list`; the server intentionally keeps default descriptions short. Legacy management tools remain callable through the local CLI or can be exposed by setting `ALGORITHM_LEGACY_TOOLS=1`.

## Client compatibility and privacy

| Agent | Compatibility status | Real client test |
|---|---|---|
| OpenAI Codex | Partially verified | CLI approval/cancellation and knowledge read/write tested; other capabilities remain partial |
| Claude Desktop | Theoretically compatible; unverified | Not run |
| Claude Code | Theoretically compatible; unverified | Not run |
| Cursor | Theoretically compatible; unverified | Not run |
| VS Code + GitHub Copilot | Protocol/config adapted; client unverified | Not run |
| Cline | Theoretically compatible; unverified | Not run |
| Roo Code | Protocol/config adapted; client unverified | Not run |
| DeepSeek Harness | Theoretically compatible; unverified | Not run |
| Tencent WorkBuddy | Theoretically compatible; unverified | Not run |
| Windsurf | Theoretically compatible; unverified | Not run |
| Gemini CLI | Protocol/config adapted; client unverified | Not run |
| Continue | Protocol/config adapted; client unverified | Not run |
| Goose | Theoretically compatible; unverified | Not run |
| OpenCode | Protocol/config adapted; client unverified | Not run |
| Google Antigravity | Theoretically compatible; unverified | Not run |
| Qwen Code | Theoretically compatible; unverified | Not run |
| JetBrains AI Assistant | Theoretically compatible; unverified | Not run |
| Kiro | Protocol/config adapted; client unverified | Not run |
| LM Studio | Theoretically compatible; unverified | Not run |
| LibreChat | Theoretically compatible; unverified | Not run |
| Cherry Studio | Theoretically compatible; unverified | Not run |
| OpenHands | Theoretically compatible; unverified | Not run |
| Zed | Theoretically compatible; unverified | Not run |
| Gemini Code Assist | Theoretically compatible; unverified | Not run |
| AnythingLLM | Theoretically compatible; unverified | Not run |

Configuration samples are references, not guarantees. Where current official config details could not be confirmed, no fields or paths are guessed. **Connection or tool discovery alone does not mean full compatibility.** See [the evidence report](docs/AGENT_COMPATIBILITY.md) and [client references](docs/clients/README.md).

The server protocol implementation is shared; there is no per-agent server fork. New conversation detection and transcript ingestion remain client-specific; the server does not listen to every Agent chat in real time. The advanced C2.3 concept API is read-only; this derivative does not yet ship the reviewed concept-link import/admin workflow, so a blank database reports `not_indexed` until links are imported through a separately reviewed path.

This repository starts with an empty database. Local database, archives, backups, preferences, runtime configuration, and logs are ignored by Git. Never commit a populated database or private preference file.

## Backup and restore

```powershell
python cli.py backup backups\backup-2026-01-01.sqlite3
python cli.py verify
python cli.py restore backups\backup-2026-01-01.sqlite3 data\restored.sqlite3
```

Restore writes a new destination and refuses overwrite. Stop the service before switching `ALGORITHM_KB` to a verified restored database.

## Tests and support

Run `python -m pytest`. The test report records protocol-level results separately from client tests. To report a client test, submit client name/version, OS, transport, configuration with secrets redacted, `tools/list` output, representative read/write tool results, and logs. Compatibility statuses are updated only when evidence can be reproduced.

See [CHANGELOG.md](CHANGELOG.md). The selected license is PolyForm Noncommercial 1.0.0. The repository is public. Published versions and release notes are available on [GitHub Releases](https://github.com/grard4/algorithm-learning-mcp/releases).

## Copyright and contributions

This project uses [PolyForm Noncommercial License 1.0.0](LICENSE). Attribution: `grard4`. When distributing copies, pass along the license text or its URL and the Required Notice supplied in [COPYRIGHT](COPYRIGHT). The license permits covered modifications and redistribution, but does not grant licensees a right to sublicense or transfer their licenses.

All noncommercial purposes are permitted. The license also expressly permits use by the listed charitable, educational, public research, and other institutions regardless of their funding source. It is not strong copyleft and does not require every modification to be published. Compliant noncommercial sharing is not unlawful resale.

Third-party components retain their respective copyrights and licenses. Contributors retain copyright in their contributions; no transfer to the maintainer is implied. Project names, logos, and trademarks are not automatically licensed by publishing the code. See [contribution rules](CONTRIBUTING.md), [copyright audit](docs/COPYRIGHT_AUDIT.md), and [licensing decision](docs/LICENSING_DECISION.md).

LICENSE contains the unchanged official English terms. Explanatory summaries do not amend them. The repository has been published. Verified capabilities and remaining limitations are documented below.

## Release acceptance and additional documentation

The independent audit fixes dated 2026-11-27 are unreleased. See [fix report](FIX_REPORT.md), [test matrix](TEST_MATRIX.md), and [release readiness](RELEASE_READINESS.md) for current evidence and compatibility changes. Earlier client and test results below retain their historical scope and are not automatically counted as validation of this branch.

On 2026-11-27, 16 isolated tests passed. Real Codex CLI approval, cancellation, creation, reads, update and audit were tested with synthetic data. Preference-tool execution, full Desktop coverage and OS isolation remain unverified. The Windows sandbox runtime issue is a disclosed limitation, not a successful isolation test. Third-party dependencies are installed separately, not bundled. See docs/CODEX_INTEGRATION_TEST.md.

See [installation](docs/INSTALLATION.md), [configuration](docs/CONFIGURATION.md), [usage](docs/USER_GUIDE.md), [security](docs/SECURITY.md), [third-party dependencies](docs/THIRD_PARTY.md), and [release acceptance](docs/FINAL_RELEASE_ACCEPTANCE.md). These reports are maintained in Simplified Chinese.

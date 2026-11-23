# Pathfinder Context Organizer

A local CLI for reviewing context from one explicitly selected Claude Code JSONL file and exporting selected context as UTF-8 Markdown.

## Claude Code plugin

Install the plugin from this repository using Claude Code:

```text
/plugin marketplace add TaylanPekbilek/Pathfinder-Context-Organizer
/plugin install pathfinder-context-organizer@pathfinder-context-organizer-marketplace
```

In a new session, run `/pathfinder-context-organizer:handoff` for interactive CLI guidance, or give the command a single approved Markdown handoff path to use it as session context. The skill runs on request. It does not install software, launch background commands, or discover session files. Reading a handoff into Claude Code adds that approved Markdown to the active session context.

The separate Python CLI performs the import, review, and export. Install it manually as described below. The optional provider workflow is a CLI feature and is not invoked by the plugin.

## Install and verify

Requires Python 3.13 or newer and uv. In PowerShell, from this folder:

```powershell
uv sync
uv run pathfinder-context --help
uv run pytest
uv run mypy
uv run ruff check src tests
uv run python examples/demo.py
```

The demo uses a disposable database and the synthetic session in `examples/session.jsonl`. It checks that the source file's SHA-256 remains unchanged after import, review, handoff, and deletion.

## Use

```powershell
$session = (Resolve-Path examples/session.jsonl).Path
uv run pathfinder-context import Demo $session
uv run pathfinder-context list Demo
uv run pathfinder-context review Demo ITEM_ID confirm
uv run pathfinder-context handoff Demo --select ITEM_ID:essential --purpose "Continue the work"
uv run pathfinder-context delete Demo --with-handoffs
```

Type `yes` at each confirmation prompt. Replace `ITEM_ID` with the ID printed by `list`. Use `review … edit --text "…"` to edit a proposal or `review … reject` to reject it. Repeat `--select` for each item to include. A package ID printed by `handoff` can be used with `render PACKAGE_ID --profile detailed`.

The deterministic extractor recognizes line labels such as `Status:`, `Decision:`, `Todo:`, `File:`, `Assumption:`, and `Risk:`, with Turkish equivalents. Unlabelled source text stays out of deterministic proposals. Inspect proposals before confirming them. Secret-marked items are blocked from transfer. Token estimates use the byte length of the entire rendered document as a conservative budget.

The CLI stores derived records in `pathfinder.sqlite3` and tracked Markdown in its sibling `pathfinder-handoffs` directory. Use `--db FILE` before the command to select a separate database. Give each database its own directory to keep outputs easy to identify. Comprehensive project deletion shows the affected records and tracked files before confirmation. External copies remain under your control.

## Optional model extraction

Add `--model MODEL_NAME` to an import to preview and separately approve an Anthropic-compatible request. The key is read from `ANTHROPIC_API_KEY` or the environment variable named by `--key-env`. Use `--endpoint https://HOST/v1/messages` for a compatible gateway. The prompt shows the endpoint and the exact redacted scope. Segments marked private or secret are omitted. If consent is declined, the request times out, or output fails validation, the deterministic proposals remain available. Model proposals require the same user review as deterministic proposals.

To propose a correction to confirmed content, run `review … edit --text "…"` and then confirm the replacement ID. Use `review … edit --topic "Title"` to attach a topic and `list PROJECT --topics` to list topic IDs.


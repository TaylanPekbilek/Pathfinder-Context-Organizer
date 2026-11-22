# Pathfinder - Context Organizer

**Carry the decisions, open tasks, and references you choose into your next Claude Code session.**

Pathfinder Context Organizer is a local CLI that reads one Claude Code JSONL file you select and proposes context for a Markdown handoff. Review and edit those proposals, then choose which approved items to export.

[English](#quick-start) | [Türkçe](#türkçe)

## Why

When a long coding session ends, the next session often needs just a few things: what changed, why a decision was made, and what still needs doing. Context Organizer lets you review those details before carrying them forward.

## Quick start

This page introduces the release candidate. The commands below require a local copy of the project source.

Requires Python 3.13 or newer and uv. From a checkout containing the project source, run the synthetic demo in PowerShell:

```powershell
uv sync
uv run python examples/demo.py
```

The demo imports a synthetic session, approves one item, writes a Markdown handoff, and deletes its disposable project data and tracked output. It checks that the source file's SHA-256 stays the same.

## The 30-second example

```powershell
$session = (Resolve-Path examples/session.jsonl).Path
uv run pathfinder-context import Demo $session
uv run pathfinder-context list Demo
uv run pathfinder-context review Demo ITEM_ID confirm
uv run pathfinder-context handoff Demo --select ITEM_ID:essential --purpose "Continue the documentation work"
```

Replace `ITEM_ID` with an ID from `list`. Type `yes` at each approval prompt. Repeat `--select` to include multiple approved items.

The deterministic extractor recognizes explicit labels such as `Status:`, `Decision:`, `Todo:`, `File:`, `Assumption:`, and `Risk:`, including Turkish equivalents.

## What the release candidate does

| Step | Behavior |
| --- | --- |
| Import | Reads one selected absolute JSONL path after approval, checks for changes, and skips duplicate imports |
| Review | Lets you edit, confirm, or reject proposals |
| Handoff | Previews the selection and writes UTF-8 Markdown after approval. Supports short, standard, and detailed profiles |
| Delete | Previews the affected project data, approved packages, and tracked Markdown files. Copies elsewhere are managed separately |

## Privacy and scope

The deterministic workflow runs locally and needs no API key. The source file is read-only, and the local SQLite database stores derived records and operational metadata. Redaction happens before extraction. Inspect the preview before sharing any handoff.

Optional Anthropic-compatible extraction with `--model` shows the endpoint and redacted scope and requires separate approval. Private and secret segments stay out of that request. If you decline or the provider fails, deterministic proposals remain available.

**0.1.0rc1** passed 102 tests on Python 3.13.11, including the deterministic end-to-end demo. The optional model workflow was verified with a fake provider and HTTP mock.

## Türkçe

Tek bir Claude Code oturum dosyası seçip içe aktar. Oluşan durum, karar, açık iş ve referans önerilerini incele. Onayladığın ve seçtiğin öğeleri yeni oturum için Markdown devir paketine dönüştür.

Kaynak kodun bulunduğu klasörde `uv sync` ve ardından `uv run python examples/demo.py` komutlarını çalıştırarak sentetik demoyu deneyebilirsin. Deterministik akış yerelde çalışır ve API anahtarı gerektirmez.

## Pathfinder tools

- [Pathfinder FileGuard](https://github.com/TaylanPekbilek/Pathfinder-FileGuard) blocks verified duplicate file reads within a Claude Code context.
- [Pathfinder MCPGuard](https://github.com/TaylanPekbilek/Pathfinder-MCPGuard) protects the context window from oversized MCP results.

## License

[MIT](LICENSE)

"""Command-line entry point for the local workspace."""

import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from pathfinder_context_organizer.adapters.claude_code.errors import SessionSourceError
from pathfinder_context_organizer.adapters.claude_code.session_source import ClaudeCodeSessionSource
from pathfinder_context_organizer.adapters.markdown_output import MarkdownHandoffOutput
from pathfinder_context_organizer.application.handoff import (
    BuildHandoffWorkflow,
    DeleteLocalDataWorkflow,
    HandoffWriteError,
    project_key,
)
from pathfinder_context_organizer.application.import_session import ImportSessionWorkflow
from pathfinder_context_organizer.application.review import ReviewExtractionWorkflow
from pathfinder_context_organizer.domain.value_objects import (
    ContextItemType,
    RenderProfile,
    RenderTier,
    Sensitivity,
)
from pathfinder_context_organizer.infrastructure.sqlite.repo import SqliteContextRepository
from pathfinder_context_organizer.infrastructure.sqlite.schema import apply_migrations


def confirm(preview: str) -> bool:
    print(preview)
    try:
        return input("Type yes to approve: ").strip() == "yes"
    except EOFError:
        return False


def selected_item(value: str) -> tuple[str, RenderTier]:
    item_id, separator, tier = value.partition(":")
    try:
        return item_id, RenderTier(tier if separator else "essential")
    except ValueError:
        raise argparse.ArgumentTypeError("use ITEM_ID:essential, :standard, or :detail") from None


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Review one Claude Code session and prepare a local handoff."
    )
    root.add_argument(
        "--db", type=Path, default=Path("pathfinder.sqlite3"), help="SQLite database file"
    )
    commands = root.add_subparsers(dest="command", required=True)
    load = commands.add_parser("import", help="preview and import one explicit JSONL file")
    load.add_argument("project")
    load.add_argument("source", help="absolute path to one Claude Code JSONL file")
    load.add_argument("--model", help="opt in to a second consent prompt for model extraction")
    load.add_argument("--endpoint", default="https://api.anthropic.com/v1/messages")
    load.add_argument("--key-env", default="ANTHROPIC_API_KEY")
    listing = commands.add_parser("list", help="list items in a project")
    listing.add_argument("project")
    listing.add_argument("--topics", action="store_true")
    review = commands.add_parser("review", help="edit, confirm, or reject a proposal")
    review.add_argument("project")
    review.add_argument("item")
    review.add_argument("action", choices=("edit", "confirm", "reject"))
    review.add_argument("--text")
    review.add_argument("--topic", help="add to a topic by title")
    review.add_argument("--sensitivity", choices=[level.value for level in Sensitivity])
    review.add_argument("--type", choices=[kind.value for kind in ContextItemType])
    handoff = commands.add_parser("handoff", help="preview and create a Markdown handoff")
    handoff.add_argument("project")
    handoff.add_argument("--select", type=selected_item, action="append", required=True)
    handoff.add_argument("--purpose", required=True)
    handoff.add_argument("--topic", help="scope to one topic ID")
    render = commands.add_parser(
        "render", help="render an existing package with a different profile"
    )
    render.add_argument("package")
    for command in (handoff, render):
        command.add_argument(
            "--profile", choices=[p.value for p in RenderProfile], default="standard"
        )
        command.add_argument("--budget", type=int, default=8000)
    delete = commands.add_parser("delete", help="preview permanent project data deletion")
    delete.add_argument("project")
    delete.add_argument(
        "--with-handoffs", action="store_true", help="include linked packages and tracked Markdown"
    )
    return root


def run(
    args: argparse.Namespace, repo: SqliteContextRepository, output: MarkdownHandoffOutput
) -> str:
    cmd = args.command
    if cmd == "import":
        model = None
        if args.model:
            from pathfinder_context_organizer.adapters.anthropic_provider import model_request

            model = model_request(args.endpoint, args.model, args.key_env)
        return ImportSessionWorkflow(repo, ClaudeCodeSessionSource()).run(
            args.project, args.source, confirm, model
        )
    if cmd == "render":
        return BuildHandoffWorkflow(repo, output, lambda rid: str(output.path_for(rid))).export(
            args.package, RenderProfile(args.profile), args.budget, confirm
        )
    project = project_key(args.project)
    review = ReviewExtractionWorkflow(repo)
    if cmd == "list":
        if args.topics:
            return (
                "\n".join(
                    f"{topic.id}\t{topic.title}" for topic in repo.list_topics_by_project(project)
                )
                or "No topics."
            )
        return (
            "\n".join(
                f"{item.id}\t{item.review_status.value}\t{item.type.value}\t{item.content_summary}"
                for item in review.list_items(project)
            )
            or "No items."
        )
    if cmd == "review":
        return review.review(
            project,
            args.item,
            args.action,
            confirm,
            args.text,
            ContextItemType(args.type) if args.type else None,
            topic_title=args.topic,
            sensitivity=Sensitivity(args.sensitivity) if args.sensitivity else None,
        )
    if cmd == "handoff":
        return BuildHandoffWorkflow(repo, output, lambda rid: str(output.path_for(rid))).build(
            project,
            tuple(args.select),
            args.purpose,
            RenderProfile(args.profile),
            args.budget,
            confirm,
            args.topic,
        )
    return DeleteLocalDataWorkflow(repo, output.remove).run(
        project, confirm, with_handoffs=args.with_handoffs
    )


def main() -> int:
    args = parser().parse_args()
    try:
        db = args.db.absolute()
        if db.suffix.lower() == ".jsonl" or db.is_symlink() or db.is_junction():
            raise ValueError("database must be a separate regular SQLite file")
        with closing(sqlite3.connect(db, timeout=1.0)) as connection:
            apply_migrations(connection)
            output = MarkdownHandoffOutput(db.parent / "pathfinder-handoffs")
            result = run(args, SqliteContextRepository(connection), output)
        print(result)
        return 0
    except (ValueError, SessionSourceError, HandoffWriteError) as error:
        print(str(error), file=sys.stderr)
    except (OSError, sqlite3.Error, RuntimeError):
        print(
            "Local operation failed. Check the selected file, database, and output access.",
            file=sys.stderr,
        )
    except KeyboardInterrupt:
        print("Operation interrupted.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

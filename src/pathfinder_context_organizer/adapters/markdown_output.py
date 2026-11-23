"""Atomic Markdown publication and managed output cleanup."""

import os
import re
import tempfile
from pathlib import Path

from pathfinder_context_organizer.ports.handoff_output import HandoffOutput


class MarkdownHandoffOutput(HandoffOutput):
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, render_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", render_id):
            raise ValueError("invalid output reference")
        if self.directory.is_symlink() or self.directory.is_junction():
            raise ValueError("managed output directory cannot be a link")
        return self.directory / f"{render_id}.md"

    def write_markdown(self, path: str, content: str) -> None:
        target = Path(path)
        if target != self.path_for(target.stem):
            raise ValueError("invalid managed output destination")
        target.parent.mkdir(exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=target.parent, prefix=f".{target.stem}.", delete=False
            ) as file:
                temporary = Path(file.name)
                file.write(content.encode("utf-8"))
                file.flush()
                os.fsync(file.fileno())
            if os.name == "nt":
                temporary.rename(target)
            else:
                os.link(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def remove(self, render_id: str) -> None:
        target = self.path_for(render_id)
        target.unlink(missing_ok=True)
        for temporary in target.parent.glob(f".{render_id}.*"):
            temporary.unlink(missing_ok=True)


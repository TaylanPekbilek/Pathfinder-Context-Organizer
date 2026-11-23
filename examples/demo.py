"""Repeatable end-to-end run against a synthetic source and disposable database."""

import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    source = Path(__file__).with_name("session.jsonl").resolve()
    before = sha256(source.read_bytes()).digest()
    with TemporaryDirectory(prefix="pathfinder-demo-") as workdir:
        db = Path(workdir) / "demo.sqlite3"

        def cli(*args: str, consent: str = "") -> str:
            result = subprocess.run(
                [sys.executable, "-m", "pathfinder_context_organizer.cli", "--db", str(db), *args],
                check=True,
                capture_output=True,
                text=True,
                input=consent,
                encoding="utf-8",
                env=os.environ | {"PYTHONUTF8": "1"},
            )
            print(result.stdout.rstrip())
            return result.stdout

        cli("import", "Demo", str(source), consent="yes\n")
        listing = cli("list", "Demo")
        item_id = listing.splitlines()[0].split("\t")[0]
        cli("review", "Demo", item_id, "confirm", consent="yes\n")
        cli(
            "handoff",
            "Demo",
            "--select",
            f"{item_id}:essential",
            "--purpose",
            "Continue the documentation work",
            consent="yes\n",
        )
        output = db.parent / "pathfinder-handoffs"
        assert len(list(output.glob("*.md"))) == 1
        cli("delete", "Demo", "--with-handoffs", consent="yes\n")
        assert cli("list", "Demo").strip() == "No items."
        assert not list(output.glob("*.md"))
        assert sha256(source.read_bytes()).digest() == before
        print("Demo complete. Source SHA-256 unchanged.")


if __name__ == "__main__":
    main()


"""Build Linux-compatible Lambda dependencies without Docker or AWS credentials."""

import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
target = root / "build" / "lambda"
shutil.rmtree(target, ignore_errors=True)
target.mkdir(parents=True)
subprocess.run(
    [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--platform",
        "manylinux2014_x86_64",
        "--implementation",
        "cp",
        "--python-version",
        "3.11",
        "--only-binary=:all:",
        "--target",
        str(target),
        "-r",
        str(root / "requirements-lambda.txt"),
    ],
    check=True,
)
shutil.copytree(root / "app", target / "app", ignore=shutil.ignore_patterns("__pycache__"))
print(f"Lambda package ready: {target}")

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable

from rich.console import Console

from distro_builder.util.logging import get_logger

_console = Console(stderr=True)


def stream_subprocess(
    cmd: Iterable[str],
    description: str = "running",
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> int:
    logger = get_logger("progress")
    argv = list(cmd)
    if not argv:
        raise ValueError("cmd must be non-empty")
    if not shutil.which(argv[0]):
        logger.debug("binary %r not on PATH, attempting direct exec anyway", argv[0])
    logger.info("%s: %s", description, " ".join(argv))
    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=env,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        logger.error("binary not found: %s", argv[0])
        return 127
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            _console.print(line.rstrip(), highlight=False)
    finally:
        returncode = proc.wait()
    logger.info("%s: exit=%d", description, returncode)
    return returncode

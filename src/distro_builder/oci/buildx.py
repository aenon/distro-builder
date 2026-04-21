from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class BuildxError(Exception):
    def __init__(self, message: str, *, argv: list[str] | None = None, stderr: str | None = None):
        super().__init__(message)
        self.argv = argv or []
        self.stderr = stderr or ""


class BuildxBuilder:
    def __init__(self, docker_binary: str | Path = "docker") -> None:
        self.docker_binary = str(docker_binary)

    def _run(
        self,
        args: list[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        argv = [self.docker_binary, *args]
        try:
            proc = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise BuildxError(f"docker binary not found: {self.docker_binary}", argv=argv) from exc
        if check and proc.returncode != 0:
            raise BuildxError(
                f"docker {args[0] if args else ''} failed (exit {proc.returncode}): "
                f"{proc.stderr.strip()}",
                argv=argv,
                stderr=proc.stderr,
            )
        return proc

    def available(self) -> bool:
        if not shutil.which(self.docker_binary):
            return False
        try:
            self._run(["buildx", "version"])
            return True
        except BuildxError:
            return False

    def builder_exists(self, name: str) -> bool:
        proc = self._run(["buildx", "ls"], check=False)
        if proc.returncode != 0:
            return False
        return any(line.split()[0:1] == [name] for line in proc.stdout.splitlines() if line.strip())

    def ensure_builder(self, name: str, driver: str = "docker-container") -> None:
        if self.builder_exists(name):
            self._run(["buildx", "use", name])
            return
        self._run(["buildx", "create", "--name", name, "--driver", driver, "--use"])

    def build_command(
        self,
        dockerfile: Path,
        context: Path,
        tag: str,
        platforms: list[str],
        *,
        output: dict[str, str] | None = None,
        builder: str | None = None,
        push: bool = False,
        load: bool = False,
        build_args: dict[str, str] | None = None,
    ) -> list[str]:
        if not platforms:
            raise BuildxError("at least one platform must be specified")
        argv: list[str] = [self.docker_binary, "buildx", "build"]
        if builder:
            argv.extend(["--builder", builder])
        argv.extend(["--platform", ",".join(platforms)])
        argv.extend(["--file", str(dockerfile)])
        argv.extend(["--tag", tag])
        if build_args:
            for k, v in build_args.items():
                argv.extend(["--build-arg", f"{k}={v}"])
        if output:
            argv.extend(["--output", ",".join(f"{k}={v}" for k, v in output.items())])
        if push:
            argv.append("--push")
        if load:
            argv.append("--load")
        argv.append(str(context))
        return argv

    def build(
        self,
        dockerfile: Path,
        context: Path,
        tag: str,
        platforms: list[str],
        *,
        output: dict[str, str] | None = None,
        builder: str | None = None,
        push: bool = False,
        load: bool = False,
        build_args: dict[str, str] | None = None,
    ) -> None:
        argv = self.build_command(
            dockerfile=dockerfile,
            context=context,
            tag=tag,
            platforms=platforms,
            output=output,
            builder=builder,
            push=push,
            load=load,
            build_args=build_args,
        )
        self._run(argv[1:])

    def inspect(self, builder: str | None = None) -> dict:
        args = ["buildx", "inspect"]
        if builder:
            args.append(builder)
        args.append("--format=json")
        proc = self._run(args)
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"raw": proc.stdout}

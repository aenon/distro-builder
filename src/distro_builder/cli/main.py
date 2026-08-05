from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from distro_builder import __version__
from distro_builder.iso.pipeline import PipelineError, build_iso
from distro_builder.manifest import Distribution, Manifest, ManifestLoadError, load_manifest
from distro_builder.oci.buildx import BuildxError
from distro_builder.oci.pipeline import OciPipelineError, build_oci
from distro_builder.qemu.pipeline import QemuPipelineError, build_qemu_image
from distro_builder.qemu.qemu_img import QemuImgError
from distro_builder.util.logging import set_level

_EXIT_USAGE = 1
_EXIT_VALIDATION = 1

_err_console = Console(stderr=True)
_out_console = Console()


def _load_or_fail(manifest_path: Path) -> Manifest:
    try:
        return load_manifest(manifest_path)
    except FileNotFoundError as exc:
        _err_console.print(f"[red]error:[/red] {exc}")
        sys.exit(_EXIT_USAGE)
    except ManifestLoadError as exc:
        _err_console.print(f"[red]error:[/red] {exc}")
        sys.exit(_EXIT_VALIDATION)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="distro-builder")
@click.option("--verbose", "-v", is_flag=True, help="Enable DEBUG logging.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress INFO logging (errors only).")
def cli(verbose: bool, quiet: bool) -> None:
    if quiet:
        set_level("ERROR")
    elif verbose:
        set_level("DEBUG")
    else:
        set_level("INFO")


@cli.command()
@click.argument("manifest", type=click.Path(dir_okay=False, path_type=Path))
def validate(manifest: Path) -> None:
    m = _load_or_fail(manifest)
    count = len(m.distributions)
    plural = "s" if count != 1 else ""
    _out_console.print(f"OK: {count} distribution{plural}")


@cli.command(name="list")
@click.argument("manifest", type=click.Path(dir_okay=False, path_type=Path))
def list_cmd(manifest: Path) -> None:
    m = _load_or_fail(manifest)
    table = Table(title=f"distro-builder manifest (version {m.version})")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Family")
    table.add_column("Format")
    table.add_column("Base image")
    table.add_column("Targets")
    table.add_column("Stages", justify="right")
    for d in m.distributions:
        targets = ", ".join(t.platform for t in d.targets)
        table.add_row(d.name, d.family, d.format, d.base_image, targets, str(len(d.stages)))
    _out_console.print(table)


def _filter_distributions(m: Manifest, distribution: str | None) -> list[Distribution]:
    if distribution is None:
        return list(m.distributions)
    matches = [d for d in m.distributions if d.name == distribution]
    if not matches:
        available = ", ".join(d.name for d in m.distributions) or "<none>"
        _err_console.print(
            f"[red]error:[/red] distribution {distribution!r} not found; available: {available}"
        )
        sys.exit(_EXIT_USAGE)
    return matches


@cli.command()
@click.argument("manifest", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--distribution", "-d", default=None, help="Build only the named distribution.")
@click.option(
    "--target",
    "-t",
    "target_platform",
    default=None,
    help="Build only the named target platform (x86_64, arm64, riscv64).",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("./outputs"),
    show_default=True,
    help="Directory where build artifacts will be written.",
)
@click.option("--dry-run", is_flag=True, help="Print planned actions without executing them.")
def build(
    manifest: Path,
    distribution: str | None,
    target_platform: str | None,
    output_dir: Path,
    dry_run: bool,
) -> None:
    m = _load_or_fail(manifest)
    distributions = _filter_distributions(m, distribution)
    plan: list[tuple[str, str, str]] = []
    for d in distributions:
        for tgt in d.targets:
            if target_platform is not None and tgt.platform != target_platform:
                continue
            plan.append((d.name, tgt.platform, tgt.output_name))
    if not plan:
        _err_console.print("[red]error:[/red] no distribution/target combinations selected")
        sys.exit(_EXIT_USAGE)
    prefix = "Would build" if dry_run else None
    for name, platform, out in plan:
        if dry_run:
            _out_console.print(f"{prefix}: {name} \\[{platform}] -> {output_dir / out}")
            continue
        dist = next(d for d in distributions if d.name == name)
        target_obj = next(t for t in dist.targets if t.platform == platform)
        try:
            if dist.format == "iso":
                path = build_iso(dist, target_obj, output_dir)
                _out_console.print(f"built: {name} \\[{platform}] -> {path}")
            elif dist.format in ("qcow2", "raw"):
                path = build_qemu_image(dist, target_obj, output_dir)
                _out_console.print(f"built: {name} \\[{platform}] -> {path}")
            elif dist.format == "oci":
                oci_plan = build_oci(dist, target_obj, output_dir, dry_run=dry_run)
                if dry_run:
                    _out_console.print(
                        f"prepared OCI build for {name} \\[{platform}]; "
                        f"Dockerfile: {oci_plan.dockerfile_path}"
                    )
                    _out_console.print(
                        "run: " + " ".join(oci_plan.buildx_command),
                        highlight=False,
                    )
                else:
                    _out_console.print(f"built: {name} \\[{platform}] -> {oci_plan.output_path}")
            else:
                _out_console.print(
                    f"Planned build (format {dist.format!r} not yet implemented): "
                    f"{name} \\[{platform}] -> {output_dir / out}"
                )
        except (
            PipelineError,
            QemuPipelineError,
            QemuImgError,
            OciPipelineError,
            BuildxError,
        ) as exc:
            _err_console.print(f"[red]error:[/red] {exc}")
            sys.exit(_EXIT_VALIDATION)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()

# distro-builder Project Plan

## Current Implementation Status (as of 2025-07-15)

**All 5 phases are complete.** The repository contains:

- Full source code in `src/distro_builder/` (CLI, manifest, OCI, ISO, QEMU, utils)
- 15 test files (~170 tests, all passing)
- `pyproject.toml` with dependencies and entry point
- 3 example manifests in `templates/manifests/`
- GitHub Actions CI (`.github/workflows/ci.yml`)
- `Dockerfile` for the builder itself
- `README.md` with installation, usage, prerequisites, and known limitations

### Phase-by-Phase Completion

| Phase | Tasks | Status | Notes |
|-------|-------|--------|-------|
| 1: Foundation & CLI | 1.1–1.5 | ✅ Complete | pyproject.toml, pydantic models, manifest loader, click CLI, tests |
| 2: ISO Builder | 2.1–2.4 | ✅ Complete | pycdlib wrapper, GRUB2 config, initramfs/dracut, pipeline. GRUB boot image generation added via `grub-mkimage` (Closes #6) |
| 3: QEMU Image Builder | 3.1–3.3 | ✅ Complete | qemu-img wrapper, format adapters, pipeline. All 6 formats supported: raw, qcow2, vmdk, vdi, vhdx, qed (Closes #7) |
| 4: OCI Container Builder | 4.1–4.3 | ✅ Complete | buildx wrapper, Dockerfile renderer, pipeline. OCI builds now execute (Closes #2), copy stages produce COPY instructions (Closes #3) |
| 5: Polish | 5.1–5.5 | ✅ Complete | logging/progress, example manifests, CI, README, Dockerfile |

### Remaining Known Gaps

| Issue | Description | Priority |
|-------|-------------|----------|
| [#4](https://github.com/aenon/distro-builder/issues/4) | UEFI boot support declared but not wired up | Medium |
| [#5](https://github.com/aenon/distro-builder/issues/5) | initramfs.py dracut integration wired into pipeline (Closes #5) | Done |
| [#6](https://github.com/aenon/distro-builder/issues/6) | ISO output won't boot — no GRUB2 bootloader binary embedded (Closes #6) | Done |
| [#8](https://github.com/aenon/distro-builder/issues/8) | This plan file is outdated (Closes #8) | Done |

## Executive Summary

**Goal**: Build a containerized Linux distribution builder in Python + Shell capable of creating bootable ISOs, QEMU disk images, and OCI containers for X86 PCs, QEMU emulation (ARM64/RPi), and multi-platform OCI images. The builder itself must run from macOS or Linux host.

### Key Constraints & Tradeoffs Identified:

| Constraint | Impact on Design | Recommended Mitigation |
| macOS NDISK incompatibility with standard GRUB2/systemd-boot | Cannot create bootable x86 ISOs from macOS directly | Use Linux VM (Ubuntu 22.04) for x86 bootable ISO generation |
| Python setuptools#2520 universal2 wheel bug | Universal binaries fail on Apple Silicon | Use Docker Desktop (pre-configured QEMU/binfmt) or conda-forge for C extensions |
| QEMU emulation slowness (5-50x slower than native) | ARM64 builds take longer on Intel x86_64 | Accept 2-5h build time, consider multi-node Docker builders for scale |
| QEMU user-mode emulation cannot access hardware (GPIO, I/O) | Raspberry Pi device drivers won't work in qemu-user-static | Build kernel/drivers on native ARM64 hardware, use docker buildx with multi-node builders |

## Final Decision: Hybrid Architecture

### Why Not Other Approaches?


| Approach                                 | Pros                         | Cons                                | Decision                                 |
| ---------------------------------------- | ---------------------------- | ----------------------------------- | ---------------------------------------- |
| Standalone Python + CLI tools            | Simple, portable             | macOS x86 ISO impossible without VM | **Use Linux VM via Docker Desktop**      |
| Native UnixTools (mkinitfs, genisoimage) | Pure Python not needed       | macOS x86 NDISK incompatibility     | **Accept limitation, use VM**            |
| Buildah + podman-py                      | Low-level control            | REST API overhead, not layered      | **Use BuildKit/Buildx**                  |
| Dockerfile multi-stage + buildx          | Production-standard, caching | Requires root or Docker Desktop VM  | **BuildKit via docker-container driver** |
| BuildKit gRPC API                        | True programmatic control    | High complexity, Go-optimized       | **Use CLI wrapper - sufficient**         |


## Proposed Project Structure

**NOTE**: This is the **target layout** to be created during implementation. Currently the repository contains only `LICENSE`, `README.md`, `.git/`, and `.sisyphus/plans/distro-builder-plan.md`. All directories and files below will be scaffolded starting with Task 1.1.

```
distro-builder/
├── .sisyphus/                    # Plan documents (this plan here)
│   └── plans/                    
├── src/
│   ├── __init__.py
│   └── distro_builder/           # Core orchestration layer
│       ├── __init__.py
│       ├── engine.py             # Main build engine (manifest -> stages)
│       ├── stage_manager.py      # Stage lifecycle management
│       └── pipeline.py           # Pipeline/manifest parsing (JSON/YAML)
├── core/
│   ├── __init__.py
│   │
│   ├── iso/                      # ISO creation layer
│   │   ├── __init__.py
│   │   ├── pycdlib_wrapper.py    # Python wrapper around pycdlib
│   │   ├── grub2_builder.py       # GRUB2 bootloader integration
│   │   └── initramfs_builder.py   # Initramfs generation (dracut or custom)
│   │
│   ├── qemu/                     # QEMU disk image layer
│   │   ├── __init__.py
│   │   ├── qemudisk.py          # Python wrapper around qemu-img
│   │   ├── qemu_runner.py        # QEMU system emulation runner
│   │   └── formats/              # Format-specific adapters
│   │       ├── raw.py
│   │       └── qcow2.py
│   │
│   ├── oci/                      # OCI container layer
│   │   ├── __init__.py
│   │   ├── buildx_builder.py    # BuildKit/buildx wrapper
│   │   └── qemu_emulator.py     # QEMU user-mode emulation controller
│   │
├── commands/                     # CLI entry points
│   ├── __init__.py
│   ├── build.py                 # main --build command (CLI)
│   └── shell.py                 # Interactive build mode
├── templates/                    # Build manifests, Dockerfiles
│   ├── manifests/
│   │       └── distributions/    # YAML templates (template engine)
│   └── dockerfiles/
│       └── distributions/        # Dockerfile templates
├── util/                         # Shared utilities
│   ├── __init__.py
│   ├── logging.py               # Custom logger with build output capture
│   └── progress.py              # Progress bar, build status display
├── tests/                        # Unit & integration tests
│   ├── __init__.py
│   ├── test_iso.py              # ISO creation tests (qemu-based)
│   └── test_oci.py              # OCI container tests
├── .github/                     # GitHub Actions, CI config
│   └── workflows/
│       └── ci.yml               # Continuous integration tests
├── pyproject.toml              # Python build system (poetry/pip)
├── Dockerfile                   # Project container definition
└── README.md                    # Documentation (to be written)
```

## Manifest System Design (The "Source of Truth")

**Format**: JSON Schema-based manifest with YAML pretty-print for readability

```yaml
# distro-builder-manifest.yaml
distributions:
  - name: "alpine-minimal"
    family: "alpine" 
    description: "Minimal Alpine Linux distribution with custom packages"
    
    # Build settings
    format: "oci"  # OCI container, ISO, raw disk, qcow2 QEMU image
    base_image: "alpine"  # Base layer (e.g., alpine, debian)
    
    # Target platforms
    targets:
      - platform: "x86_64" 
        output_name: "alpine-minimal-x86_64.iso"
      - platform: "arm64" 
        output_name: "alpine-minimal-arm64.iso"
      - platform: "riscv64" 
        output_name: "alpine-minimal-riscv64.iso"
    
    # Stages (pipeline definition)
    stages: []
  - name: "debian-minimal"
    ...
```

## Stage Architecture (Composable, Immutable Pipeline)

```python
# Conceptual API
class Stage(Base):
    """Immutable stage - never modified, only created"""
    
    # Stage types
    
    class BaseLayer(Stage):
        """Unchanged base layer (e.g., Alpine, Debian)"""
    
    class RunCommand(Stage):
        """Run command in container filesystem"""
    
    class InstallPackage(Stage):
        """Install packages into image"""
    
    class BuildKernel(Stage):
        """Compile kernel (delegated to Linux VM)"""
    
    class GenerateGrub(Stage):
        """Generate GRUB2 boot configuration"""
    
    class GenerateInitramfs(Stage):
        """Create initramfs with kernel modules"""
    
    class CreateISO(Stage):
        """Assemble final ISO image"""

## Build Pipeline Workflow
## Implementation Phases (Actionable Tasks with QA)

**NOTE**: All file paths are relative to repo root `/Users/xilins/Personal/distro-builder/`. These files do NOT yet exist - they will be created during implementation.

### Phase 1: Foundation & CLI

#### Task 1.1 - Project scaffolding
- **Create**: `pyproject.toml` (Poetry config with deps: click, pydantic>=2, PyYAML, rich, pytest)
- **Create**: `src/distro_builder/__init__.py` (exports __version__)
- **Create**: `tests/__init__.py` (empty)
- **Create**: `.gitignore` (Python standard: __pycache__, *.pyc, .venv, dist/, build/, .pytest_cache)
- **Expose**: Package installable via `pip install -e .`
- **QA Scenario**:
  - Run: `pip install -e .`
  - Expected: exit code 0, `distro_builder` import works in Python REPL
  - Run: `python -c "import distro_builder; print(distro_builder.__version__)"`
  - Expected: prints version string (e.g., "0.1.0")

#### Task 1.2 - Manifest schema (pydantic models)
- **Create**: `src/distro_builder/manifest/__init__.py`
- **Create**: `src/distro_builder/manifest/models.py` with pydantic v2 models:
  - `Target` (platform: Literal["x86_64","arm64","riscv64"], output_name: str)
  - `Stage` (name: str, type: Literal["run","copy","install","kernel","initramfs","grub","iso"], params: dict)
  - `Distribution` (name: str, family: str, format: Literal["iso","qcow2","raw","oci"], base_image: str, targets: list[Target], stages: list[Stage])
  - `Manifest` (version: str, distributions: list[Distribution])
- **Expose**: All models with strict validation (no extra fields)
- **QA Scenario**:
  - Run: `pytest tests/test_manifest_models.py -v`
  - Tests cover: valid manifest parses, invalid platform raises ValidationError, missing required field raises ValidationError, extra field raises ValidationError
  - Expected: all tests pass

#### Task 1.3 - Manifest loader (YAML/JSON)
- **Create**: `src/distro_builder/manifest/loader.py` with `load_manifest(path: Path) -> Manifest`
- **Behavior**: Auto-detect YAML (.yml/.yaml) vs JSON (.json) by extension, parse, validate via pydantic
- **Create**: `tests/fixtures/valid_manifest.yaml`, `tests/fixtures/valid_manifest.json`, `tests/fixtures/invalid_manifest.yaml`
- **Expose**: `load_manifest()` function + `ManifestLoadError` exception
- **QA Scenario**:
  - Run: `pytest tests/test_manifest_loader.py -v`
  - Tests: loads YAML fixture → Manifest object, loads JSON fixture → same Manifest, invalid fixture raises ManifestLoadError, missing file raises FileNotFoundError
  - Expected: all tests pass

#### Task 1.4 - CLI skeleton (click)
- **Create**: `src/distro_builder/cli/__init__.py`
- **Create**: `src/distro_builder/cli/main.py` with click group and commands:
  - `distro-builder validate <manifest.yaml>` → loads + validates, prints "OK: N distributions" or error
  - `distro-builder list <manifest.yaml>` → prints table of distributions + targets
  - `distro-builder build <manifest.yaml> [--distribution NAME] [--target PLATFORM] [--output-dir DIR]` → placeholder that prints planned actions (no actual build yet in Phase 1)
- **Wire up**: `[project.scripts]` in pyproject.toml: `distro-builder = "distro_builder.cli.main:cli"`
- **QA Scenario**:
  - Run: `distro-builder --help` → exit 0, shows usage with 3 subcommands
  - Run: `distro-builder validate tests/fixtures/valid_manifest.yaml` → exit 0, prints "OK: 1 distributions"
  - Run: `distro-builder validate tests/fixtures/invalid_manifest.yaml` → exit 1, prints error to stderr
  - Run: `distro-builder list tests/fixtures/valid_manifest.yaml` → exit 0, prints table with rich
  - Run: `distro-builder build tests/fixtures/valid_manifest.yaml --distribution alpine-minimal` → exit 0, prints "Would build: alpine-minimal [x86_64, arm64]"

#### Task 1.5 - CLI tests
- **Create**: `tests/test_cli.py` using click.testing.CliRunner
- **Cover**: validate success, validate failure, list output contains distribution name, build dry-run prints distribution name
- **QA Scenario**:
  - Run: `pytest tests/ -v`
  - Expected: all tests pass, coverage on cli/main.py ≥ 80%

**Phase 1 Completion Criteria**:
- [ ] `pip install -e .` succeeds
- [ ] `pytest tests/ -v` all pass
- [ ] `distro-builder --help` works
- [ ] Manifest schema validates 3 fixture files as expected
- [ ] No existing files in `src/` or `tests/` - all new content

---

### Phase 2: ISO Builder

#### Task 2.1 - pycdlib wrapper
- **Create**: `src/distro_builder/iso/__init__.py`
- **Create**: `src/distro_builder/iso/pycdlib_wrapper.py` with class `IsoBuilder`:
  - `__init__(output_path: Path)`
  - `add_file(src: Path, iso_path: str)` - adds file to ISO
  - `add_directory(src: Path, iso_path: str)` - recursive add
  - `set_boot_record(boot_file: str, boot_type: Literal["el_torito_bios","el_torito_uefi","hybrid"])`
  - `write()` - finalizes and writes ISO
- **Dep**: Add `pycdlib` to pyproject.toml
- **QA Scenario**:
  - Run: `pytest tests/test_iso_builder.py -v`
  - Tests: create ISO with single file → file readable via pycdlib, add directory → all entries present, boot record set → ISO has El Torito boot catalog
  - Expected: all tests pass

#### Task 2.2 - GRUB2 config generator
- **Create**: `src/distro_builder/iso/grub2.py` with:
  - `GrubConfig` pydantic model (timeout, default, menuentries: list[MenuEntry])
  - `MenuEntry` model (title, kernel_path, initrd_path, kernel_cmdline)
  - `render_grub_cfg(config: GrubConfig) -> str` - renders grub.cfg text
  - `write_grub_cfg(config: GrubConfig, path: Path)` - writes to file
- **Expose**: Generator only - actual GRUB binary installation is out of scope (user's Docker container provides it)
- **QA Scenario**:
  - Run: `pytest tests/test_grub2.py -v`
  - Tests: render_grub_cfg produces valid GRUB syntax (contains "menuentry", "linux", "initrd"), multi-entry config renders correctly
  - Expected: all tests pass

#### Task 2.3 - Initramfs spec generator
- **Create**: `src/distro_builder/iso/initramfs.py` with:
  - `InitramfsSpec` model (kernel_version, modules: list[str], extra_files: list[Path])
  - `render_dracut_conf(spec: InitramfsSpec) -> str` - generates dracut.conf
  - `render_dracut_command(spec: InitramfsSpec, output: Path) -> list[str]` - returns CLI args
- **Note**: We generate configs + command strings. Actual dracut execution happens in user's Linux VM/container (we do NOT run dracut on macOS).
- **QA Scenario**:
  - Run: `pytest tests/test_initramfs.py -v`
  - Tests: render_dracut_conf includes modules, render_dracut_command returns proper argv list
  - Expected: all tests pass

#### Task 2.4 - ISO build pipeline integration
- **Create**: `src/distro_builder/iso/pipeline.py` with `build_iso(distribution: Distribution, target: Target, workdir: Path) -> Path`
- **Behavior**: Given a Distribution manifest entry + target, orchestrates IsoBuilder + GRUB + initramfs to produce an ISO file
- **Wire**: Update `cli/main.py` build command to call `build_iso()` when `format == "iso"`
- **QA Scenario**:
  - Run: `distro-builder build tests/fixtures/iso_manifest.yaml --output-dir /tmp/out`
  - Expected: exit 0, file `/tmp/out/<distro>-<arch>.iso` exists, `file /tmp/out/<distro>-<arch>.iso` reports "ISO 9660 CD-ROM filesystem"
  - User will do full boot test via QEMU separately (not our responsibility)

**Phase 2 Completion Criteria**:
- [ ] `pytest tests/ -v` all pass (including Phase 1 tests)
- [ ] ISO file produced is valid ISO 9660 (verifiable via `file` command)
- [ ] GRUB config renders valid syntax
- [ ] Initramfs command/config generators produce correct outputs

---

### Phase 3: QEMU Image Builder

#### Task 3.1 - qemu-img wrapper
- **Create**: `src/distro_builder/qemu/__init__.py`
- **Create**: `src/distro_builder/qemu/qemu_img.py` with class `QemuImg`:
  - `create(path: Path, format: Literal["raw","qcow2"], size: str) -> None` - shells to `qemu-img create`
  - `convert(src: Path, dst: Path, src_format: str, dst_format: str) -> None`
  - `info(path: Path) -> dict` - returns parsed `qemu-img info --output=json`
  - `snapshot_create(path: Path, name: str)`, `snapshot_list(path: Path)`, `snapshot_apply(path: Path, name: str)`
  - `resize(path: Path, new_size: str)`, `commit(path: Path)`, `rebase(path: Path, backing: Path)`
- **Implementation**: All methods use `subprocess.run` with `qemu-img` binary; check return code; raise `QemuImgError` on failure
- **QA Scenario**:
  - Run: `pytest tests/test_qemu_img.py -v` (uses mocker to stub subprocess)
  - Tests: create() calls correct qemu-img args, info() parses JSON output, snapshot_create() returns on success, error exit code raises QemuImgError
  - Expected: all tests pass
  - Additional: integration test gated on `qemu-img --version` success - create actual 10MB qcow2, verify via `file` command

#### Task 3.2 - Disk format adapters
- **Create**: `src/distro_builder/qemu/formats/__init__.py`
- **Create**: `src/distro_builder/qemu/formats/raw.py` with `RawDiskBuilder` class
- **Create**: `src/distro_builder/qemu/formats/qcow2.py` with `Qcow2Builder` class (supports backing_file, compression=zstd)
- **Expose**: Each builder has `build(output: Path, size: str, **opts) -> None`
- **QA Scenario**:
  - Run: `pytest tests/test_qemu_formats.py -v`
  - Tests: RawDiskBuilder.build creates raw file, Qcow2Builder.build passes correct -o args to qemu-img
  - Expected: all tests pass

#### Task 3.3 - QEMU pipeline integration
- **Create**: `src/distro_builder/qemu/pipeline.py` with `build_qemu_image(distribution, target, workdir) -> Path`
- **Wire**: Update CLI `build` to call this when `format in ("qcow2", "raw")`
- **QA Scenario**:
  - Run: `distro-builder build tests/fixtures/qemu_manifest.yaml --output-dir /tmp/out`
  - Expected: exit 0, file exists, `qemu-img info /tmp/out/<name>.qcow2` reports format=qcow2

**Phase 3 Completion Criteria**:
- [ ] `pytest tests/ -v` all pass
- [ ] qemu-img wrapper generates correct subprocess args for all commands
- [ ] QEMU image files verifiable via `qemu-img info`

---

### Phase 4: OCI Container Builder

#### Task 4.1 - buildx CLI wrapper
- **Create**: `src/distro_builder/oci/__init__.py`
- **Create**: `src/distro_builder/oci/buildx.py` with class `BuildxBuilder`:
  - `ensure_builder(name: str) -> None` - runs `docker buildx create --name <name>` if not exists
  - `build(dockerfile: Path, context: Path, tag: str, platforms: list[str], output: dict) -> None`
  - `inspect() -> dict` - returns parsed `docker buildx inspect` output
- **Implementation**: All via subprocess to `docker` binary; capture stdout/stderr; raise `BuildxError` on non-zero exit
- **QA Scenario**:
  - Run: `pytest tests/test_buildx.py -v` (mocker stubs subprocess)
  - Tests: build() produces correct `docker buildx build --platform linux/amd64,linux/arm64 -t tag .` args, ensure_builder checks existing builder
  - Expected: all tests pass

#### Task 4.2 - Dockerfile template engine
- **Create**: `src/distro_builder/oci/dockerfile.py` with:
  - `DockerfileSpec` model (base_image, stages: list[DockerStage])
  - `DockerStage` model (from_image: str, commands: list[str], run_mount: list[Mount] | None)
  - `render_dockerfile(spec: DockerfileSpec) -> str` - produces valid Dockerfile text
- **QA Scenario**:
  - Run: `pytest tests/test_dockerfile.py -v`
  - Tests: render includes FROM, RUN commands, multi-stage syntax correct, BuildKit mount syntax valid
  - Expected: all tests pass

#### Task 4.3 - OCI pipeline integration
- **Create**: `src/distro_builder/oci/pipeline.py` with `build_oci(distribution, target, workdir) -> Path`
- **Behavior**: Renders Dockerfile from stages, invokes BuildxBuilder, exports to OCI tarball
- **Wire**: CLI `build` handles `format == "oci"` by calling this
- **QA Scenario**:
  - Run: `distro-builder build tests/fixtures/oci_manifest.yaml --output-dir /tmp/out --dry-run`
  - Expected: exit 0, prints the Dockerfile that WOULD be built + the exact buildx command
  - User will do full buildx run via their Docker Desktop (not our responsibility)

**Phase 4 Completion Criteria**:
- [ ] `pytest tests/ -v` all pass
- [ ] Dockerfile renderer produces valid syntax
- [ ] buildx wrapper generates correct command args
- [ ] --dry-run prints the would-be build command

---

### Phase 5: Polish

#### Task 5.1 - Progress + logging
- **Create**: `src/distro_builder/util/__init__.py`
- **Create**: `src/distro_builder/util/logging.py` with:
  - `get_logger(name: str) -> logging.Logger` - returns a rich-backed logger with consistent format
  - `set_level(level: str)` - configures root level from CLI flag
- **Create**: `src/distro_builder/util/progress.py` with:
  - `stream_subprocess(cmd: list[str], description: str) -> int` - runs subprocess, streams stdout to rich.Progress, returns exit code
- **Wire**: Update `cli/main.py` to accept `--verbose/-v` and `--quiet/-q` flags that map to logging levels
- **Create**: `tests/test_util_logging.py`, `tests/test_util_progress.py`
- **QA Scenario**:
  - Run: `pytest tests/test_util_logging.py tests/test_util_progress.py -v`
  - Tests: get_logger returns Logger instance with rich handler attached, set_level changes root level correctly, stream_subprocess returns 0 on `echo hello`, returns non-zero on `false`
  - Expected: all tests pass
  - Run: `distro-builder -v validate tests/fixtures/valid_manifest.yaml`
  - Expected: exit 0, stderr contains DEBUG-level log lines (via rich formatter with colors)

#### Task 5.2 - Example manifests
- **Create**: `templates/manifests/alpine-minimal.yaml` - OCI format, alpine:3.19 base, linux/amd64 + linux/arm64 targets, 2 install stages
- **Create**: `templates/manifests/debian-minimal.yaml` - ISO format, debian:bookworm base, x86_64 target, kernel + initramfs + grub stages
- **Create**: `templates/manifests/oci-multiarch.yaml` - OCI format, ubuntu:22.04 base, 3 platforms (amd64, arm64, riscv64)
- **QA Scenario**:
  - Run: `distro-builder validate templates/manifests/alpine-minimal.yaml`
  - Expected: exit 0, stdout "OK: 1 distributions"
  - Run: `distro-builder validate templates/manifests/debian-minimal.yaml`
  - Expected: exit 0, stdout "OK: 1 distributions"
  - Run: `distro-builder validate templates/manifests/oci-multiarch.yaml`
  - Expected: exit 0, stdout "OK: 1 distributions"
  - Run: `distro-builder list templates/manifests/oci-multiarch.yaml`
  - Expected: exit 0, stdout table contains "amd64", "arm64", "riscv64" rows

#### Task 5.3 - GitHub Actions CI
- **Create**: `.github/workflows/ci.yml` with jobs:
  - `test` - matrix over python-version: [3.11, 3.12], runs `pip install -e .[dev]` then `pytest tests/ -v --cov=distro_builder --cov-fail-under=80`
  - `lint` - runs `ruff check src/ tests/` and `ruff format --check src/ tests/`
  - `validate-templates` - runs `distro-builder validate templates/manifests/*.yaml` on every example
- **Dep**: Add `ruff`, `pytest-cov` to pyproject.toml `[tool.poetry.group.dev]`
- **QA Scenario**:
  - Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
  - Expected: exit 0 (valid YAML)
  - Run: `actionlint .github/workflows/ci.yml` (if actionlint installed, else skip)
  - Expected: exit 0, no errors
  - Run: `ruff check src/ tests/`
  - Expected: exit 0, no violations
  - Run: `pytest tests/ -v --cov=distro_builder --cov-fail-under=80`
  - Expected: exit 0, coverage report shows ≥80% on `distro_builder` package
  - Full GitHub validation: push to feature branch, verify Actions tab shows green on all 3 jobs

#### Task 5.4 - README
- **Update**: `README.md` to include:
  - Installation section (`pip install -e .` + `poetry install`)
  - Usage section with `distro-builder validate/list/build` examples using `templates/manifests/`
  - Prerequisites section (Docker Desktop for OCI, qemu-img for QEMU images, Linux VM for ISO builds)
  - Known limitations section (macOS x86 ISO requires Linux VM)
  - Link to plan: `.sisyphus/plans/distro-builder-plan.md`
- **QA Scenario**:
  - Run: `grep -E "^## (Installation|Usage|Prerequisites|Known Limitations)" README.md | wc -l`
  - Expected: output `4` (all 4 required sections present)
  - Run: `grep -c "distro-builder validate" README.md`
  - Expected: output ≥ 1 (at least one usage example)
  - Run: `grep -c "templates/manifests/" README.md`
  - Expected: output ≥ 1 (references example manifests)
  - Manual check: render README on GitHub preview or `grip README.md`, verify markdown formatting correct

#### Task 5.5 - Dockerfile for distro-builder itself
- **Create**: `Dockerfile` at repo root:
  - Base: `python:3.12-slim-bookworm`
  - Install system deps: `qemu-utils`, `genisoimage`, `xorriso`, `grub-pc-bin`, `grub-efi-amd64-bin`, `dracut-core`, `curl`, `ca-certificates`
  - Install Docker CLI + buildx plugin (copy from `docker:cli` image)
  - Copy repo, run `pip install -e .`
  - Default `ENTRYPOINT ["distro-builder"]`
- **Create**: `.dockerignore` (exclude `.git`, `.venv`, `__pycache__`, `tests/`, `dist/`, `build/`)
- **QA Scenario**:
  - Run: `docker build -t distro-builder:test .` (user performs this in their Docker Desktop)
  - Expected: exit 0, image built
  - Run: `docker run --rm distro-builder:test --help`
  - Expected: exit 0, prints CLI help (matches Task 1.4 help output)
  - Run: `docker run --rm -v $(pwd)/templates:/t distro-builder:test validate /t/manifests/alpine-minimal.yaml`
  - Expected: exit 0, stdout "OK: 1 distributions"
  - Run: `docker run --rm distro-builder:test --version` (hidden flag added by click)
  - Expected: exit 0, prints version matching `distro_builder.__version__`
  - Static lint (we can run): `hadolint Dockerfile` (if hadolint installed, else skip)
  - Expected: exit 0, no errors above `warning` level

**Phase 5 Completion Criteria**:
- [ ] CI passes on GitHub (all 3 jobs green)
- [ ] README documents all CLI commands with verifiable examples
- [ ] All 3 example manifests validate via `distro-builder validate`
- [ ] Dockerfile builds (user-verified) and produces working CLI in container

## Risk Assessment & Contingency Planning

| Risk | Severity | Probability | Mitigation |
|------|----------|-------------|------------|
| macOS NDISK incompatibility prevents x86 ISO creation | HIGH | Certain (on Apple Silicon Mac) | Use Linux VM (Ubuntu 22.04 multipass or Docker Desktop VM) - documented workaround |
| QEMU emulation slow (5-50x native speed) | MEDIUM | High | Accept for initial builds, add multi-node Docker builder option in future |
| Python setuptools#2520 universal2 wheel bug breaks build | MEDIUM | High (on Apple Silicon Mac) | Use Docker Desktop (pre-configured QEMU/binfmt), or conda-forge for C extensions |
| BuildKit API changes break Python wrapper | LOW | Medium | Test against latest Docker Desktop, pin buildx version in requirements.txt |
| User wants to avoid Docker (security, rootless mode) | MEDIUM | Low | Add Podman/podman-py option as fallback, document requirements |
| ARM64 kernel/drivers initialization fails in qemu-user-emulation | HIGH | Medium (RPi specific) | Provide native ARM64 build option, or use full QEMU system emulation (slower but supports hardware) |

## Critical Questions to Resolve Before Implementation

### 1. **User Interface Choice**

| Option | Pros | Cons |
|--------|------|------|
| **click** (Python standard) | No external deps, simple, well-tested | Less powerful than clickhouse |
| **clickhouse** (more features) | Rich UI, decorators, presets | External dep, slightly more complex |
| **typer** (clickfork) | Click features in Pydantic types | External dep |
| **argparse** (built-in) | Zero deps, simple | Verbose, not as clean |

**Recommendation**: **click** - best balance of features and simplicity. Add `typer` as optional dependency.

---

### 2. **Manifest Engine**

| Option | Pros | Cons |
|--------|------|------|
| **pydantic v2** (types via PyYAML) | Strongly typed, auto-docs from schemas | External dep |
| **python-multipart** (YAML schema) | Standard library, minimal deps | Less type safety |
| **jsonschema** (JSON native) | Standard lib, pure Python | JSON only, not YAML |
| **kubernetes** (yaml + k8s types) | Rich types, validation built-in | Heavy external dep |

**Recommendation**: **pydantic v2 + PyYAML**. Type safety with validation. Add `typer` for CLI types.

---

### 3. **Package Management**

| Option | Pros | Cons |
|--------|------|------|
| **Poetry** (Python standard) | Pydantic v2, simple CLI, no root | External deps, locked dependencies |
| **setuptools** (pip) | Zero config, built-in pip | Less control over dep tree |
| **uv** (new Python tool) | Blazing fast, Rust-backed | Less mature than poetry/pip |

**Recommendation**: **Poetry**. De facto Python packaging standard. Auto-generates lock file.

---

### 4. **Log Output Handling**

| Option | Pros | Cons |
|--------|------|------|
| **rich** (colorful terminal) | Rich UI, themes, auto-wrap | External dep |
| **pydantic** (rich) | Standard library, minimal deps | Less features than rich |
| **colorama** (Windows ANSI) | Cross-platform color support | More complex code, external dep |

**Recommendation**: **rich**. Most robust terminal output with minimal config.

---

### 5. **BuildKit Driver Selection**

| Driver | Pros | Cons |
|--------|------|______|
| **docker-container** (default) | Native Docker, full Dockerfile support | Requires root or Docker Desktop VM |
| **docker** (legacy) | Simple, no extra config | Not supported in newer Docker Desktop |
| **remote** (external BuildKit) | No root needed, external server | Requires external setup |
| **kubernetes** | Distributed builds on K8s | Complex, requires K8s cluster |

**Recommendation**: **docker-container**. Industry standard, full feature set. Works via Docker Desktop VM on macOS (no root required).

---

### 6. **Linux VM Selection**

| Option | Pros | Cons |
|--------|------|______|
| **Docker Desktop VM** (default) | Pre-configured, one-click start | Slightly higher I/O overhead |
| **multipass** (Ubuntu official) | Official Ubuntu, lightweight (~10MB) | Requires VM agent, more setup |
| **Docker machine** | Full config control | Manual setup, less convenient |

**Recommendation**: **Docker Desktop VM**. Lowest friction, pre-configured QEMU/binfmt support for cross-platform builds.

---
## Summary: Final Stack Decisions

| Category | Decision | Rationale |
|----------|----------|-----------|
| **CLI** | click + typer (optional) | Best balance of features and simplicity |
| **Manifest Parsing** | pydantic v2 + PyYAML | Type safety, validation from schemas |
| **Package Manager** | Poetry | De facto Python packaging standard. Auto-generates lock file. |
| **Logging** | rich | Most robust terminal output |
| **Build System** | docker-buildx (docker-container driver) | Industry standard, Dockerfile support |
| **ISO Creation** | pycdlib (Python) + grub2-cli (subprocess) | Cross-platform, pure Python ISO builder |
| **QEMU Images** | qemu-img (subprocess wrapper) + qemudisk module | No external deps, full disk image control |
| **OCI Containers** | docker-cli (subprocess) + buildctl CLI | Direct access to BuildKit, multi-platform |
| **Platform Selection** | Docker Desktop (includes Linux VM) | Pre-configured QEMU/binfmt, no root required |

## Next Steps

1. Review plan with Momus agent for completeness and verifiability
2. Begin Phase 1 implementation: Project scaffolding + CLI skeleton
3. User will perform e2e tests with qemu/docker (we do NOT run qemu/docker)
4. Each phase must produce testable code (pytest-based unit tests)


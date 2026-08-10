# distro-builder

Containerized cross-platform Linux distribution builder. Produces bootable ISOs, QEMU disk images (`qcow2`, `raw`), and OCI container images (multi-architecture) from a single YAML/JSON manifest. Runs on macOS or Linux.

## Installation

```bash
git clone https://github.com/your-org/distro-builder.git
cd distro-builder
pip install -e .
```

Or with Poetry:

```bash
poetry install
poetry run distro-builder --help
```

## Prerequisites

Different build formats require different host tooling:

- **OCI containers**: Docker Desktop (includes `docker buildx` and QEMU/binfmt for multi-arch builds). Works on macOS + Linux.
- **QEMU disk images** (`qcow2`, `raw`): `qemu-img` binary (part of `qemu-utils` on Debian/Ubuntu, `qemu` on macOS via Homebrew).
- **Bootable x86 ISOs**: A Linux environment (native Linux host, Docker Desktop VM, or `multipass` on macOS). See [Known Limitations](#known-limitations).

Python 3.11+ is required.

## Usage

The CLI exposes three subcommands: `validate`, `list`, `build`.

### Validate a manifest

```bash
distro-builder validate templates/manifests/alpine-minimal.yaml
```

Exits 0 on success, 1 on validation error (with detailed pydantic errors on stderr).

### List distributions in a manifest

```bash
distro-builder list templates/manifests/oci-multiarch.yaml
```

Prints a rich-formatted table showing name, family, format, base image, target platforms, and stage count.

### Build distributions

```bash
distro-builder build templates/manifests/alpine-minimal.yaml --output-dir ./outputs
```

Flags:

- `--distribution NAME` / `-d NAME` - only build the named distribution
- `--target PLATFORM` / `-t PLATFORM` - only build the named platform (`x86_64`, `arm64`, `riscv64`)
- `--output-dir DIR` / `-o DIR` - where artifacts are written (default `./outputs`)
- `--dry-run` - print planned actions without executing
- `--verbose` / `-v` - DEBUG logging
- `--quiet` / `-q` - suppress all non-error output

Examples:

```bash
# Just show what would be built
distro-builder build templates/manifests/alpine-minimal.yaml --dry-run

# Build only the arm64 target of a specific distribution
distro-builder build templates/manifests/alpine-minimal.yaml \
    --distribution alpine-minimal --target arm64 -o ./outputs

# Build an ISO
distro-builder build templates/manifests/debian-minimal.yaml -o ./outputs
file ./outputs/debian-minimal-x86_64.iso
```

For OCI builds, distro-builder prepares a Dockerfile and prints the exact `docker buildx build` command it will invoke - you can pipe the output into your own CI or run it directly. When actually executed, it delegates to `docker buildx`.

## Manifest format

Manifests are YAML or JSON. Top-level schema:

```yaml
version: "1"
distributions:
  - name: alpine-minimal
    family: alpine
    description: "Minimal Alpine Linux OCI image"
    format: oci                 # oci | iso | qcow2 | raw
    base_image: "alpine:3.19"
    targets:
      - platform: x86_64        # x86_64 | arm64 | riscv64
        output_name: alpine-amd64.oci.tar
      - platform: arm64
        output_name: alpine-arm64.oci.tar
    stages:
      - name: install
        type: install           # run | copy | install | kernel | initramfs | grub | iso
        params:
          manager: apk          # apk | apt | dnf (for install stages)
          packages: [curl, ca-certificates]
      - name: hello
        type: run
        params:
          command: "echo hello-world"
```

See `templates/manifests/` for complete working examples:

- `alpine-minimal.yaml` - Minimal Alpine OCI (amd64 + arm64)
- `debian-minimal.yaml` - Debian bootable ISO (x86_64)
- `oci-multiarch.yaml` - Ubuntu multi-arch OCI (amd64, arm64, riscv64)

## Development

```bash
pip install -e .
pip install pytest pytest-cov pytest-mock ruff

pytest tests/ -v --cov=distro_builder
ruff check src/ tests/
ruff format --check src/ tests/
```

### Development Environment

**macOS** (current primary dev platform):
```bash
# Python deps (use uv or pip)
uv venv .venv && source .venv/bin/activate
uv pip install -e .

# Docker + buildx (required for OCI builds)
# Install Docker Desktop - includes buildx and QEMU/binfmt

# QEMU disk image tools (optional, for qcow2/raw)
brew install qemu

# ISO building: NOT available natively
# GRUB2 BIOS/UEFI modules and dracut are Linux-only tools.
# Use Docker Desktop VM, multipass, or remote Linux host.
```

**Linux** (required for full ISO and UEFI work):
```bash
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y qemu-utils grub-pc-bin grub-efi-amd64-bin dracut-core

# Verify GRUB2 can build both BIOS and UEFI images
grub-mkimage -O i386-pc --help
grub-mkimage -O x86_64-efi --help

# Install Python deps
pip install -e .
```

### Restarting UEFI work (Issue #4)

UEFI boot support is [parked in issue #4](https://github.com/aenon/distro-builder/issues/4). To resume:

1. Work on a **Linux machine** with `grub-efi-amd64-bin` installed.
2. BIOS boot image generation already works (`generate_grub_boot_image()` in `grub2.py`).
3. Mirror that pattern for UEFI: `generate_grub_efi_image()` with `-O x86_64-efi`.
4. Wire `boot_type` param (`bios` | `uefi` | `hybrid`) into the `grub` stage and `iso/pipeline.py`.
5. For hybrid ISOs: call `set_boot_record` twice (BIOS `boot.img` + UEFI `BOOTX64.EFI`).

See the [checklist on issue #4](https://github.com/aenon/distro-builder/issues/4) for full details.

## Known Limitations

- **Bootable x86 ISOs on macOS Apple Silicon**: Cannot be produced directly on macOS because standard Linux bootloader artifacts (GRUB2 BIOS/UEFI modules) are not distributed for macOS hosts. Use a Linux VM (Docker Desktop's built-in VM, `multipass`, or any Linux container) to run the builder.
- **ARM64 cross-compilation speed**: QEMU user-mode emulation is typically **5-50x slower than native**. Large ARM64 OCI builds on an Intel host may take hours.
- **QEMU user-mode emulation can't access hardware**: Raspberry Pi GPIO/I/O device drivers will not initialize under `qemu-user-static`. Use a native ARM64 builder for full device-tree validation.
- **Rosetta 2 is the wrong direction**: Rosetta translates x86 -> ARM, not ARM -> x86. On Apple Silicon, use `qemu-user-static` (provided by Docker Desktop) for running Linux x86 binaries.

distro-builder itself does not run `docker`, `qemu-img`, or `qemu-system-*` - it generates configuration and prints the exact commands. You (or your CI) execute them. That keeps the tool portable and testable without requiring privileged runtime access.

## Project plan

See `.sisyphus/plans/distro-builder-plan.md` for the full architecture plan, task breakdown, QA scenarios, and risk analysis.

## License

Apache-2.0 (see `LICENSE`).

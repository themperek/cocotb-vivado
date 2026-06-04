# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `cocotb_vivado.runner` — a Python runner subclass of
  `cocotb.runner.Simulator`. Reachable via
  `cocotb_vivado.runner.get_runner("vivado")` and the standard
  `runner.build()` / `runner.test()` interface. Pure XSim binary
  orchestration: only `xelab` / `xvlog` / `xvhdl` are invoked
  directly.
- Content-hash build cache at `build_dir/build_signature.json`
  (active by default; `always=True` bypasses it). The signature
  captures user HDL source content hashes, every kwarg that affects
  output (parameters, defines, build_args, includes, timescale,
  waves, wave_format, extra_global_modules, hdl_toplevel,
  hdl_library), each `VivadoSource.fingerprint()`, and
  `xelab` / `xvlog` / `xvhdl --version`. On a hit, the entire
  pipeline — including `VivadoSource.prepare()` — is skipped.
  On a miss, `prepare()` is called with `force=True` so each
  source bypasses its own mtime check (guards against
  content-change-without-mtime-change, e.g. after `git checkout`).
  Cache decisions are logged on the `cocotb_vivado.runner.cache`
  logger.
- `cocotb_vivado.vivado` — sub-package for Vivado-managed sources
  and the tool-driver helpers behind them. Architectural rule:
  anything that runs `vivado -mode batch` lives here, not in the
  runner.
- Vivado-managed source classes in `cocotb_vivado.vivado`, usable as
  entries in `runner.build(sources=[...])`:
  - `VivadoIp(*xci_paths, builder_tcl=..., part_num=...)` —
    runs `set_part; add_files -norecurse; export_ip_user_files`
    with mtime-based caching against the per-IP `xsim/README.txt`.
    Optional `builder_tcl` produces the XCIs on first run, letting
    the test fixture stay Vivado-version-agnostic instead of
    committing a version-locked XCI.
  - `VivadoBd(bd_path, builder_tcl=..., part_num=..., wrapper=True,
    top=...)` — ingests a `.bd` block design. Builds a throwaway
    project under the build dir, optionally generates the RTL wrapper
    (`make_wrapper -top -import`) that flattens interface ports
    (`create_bd_intf_port` — AXI/AXIS/BRAM) into discrete scalar ports,
    and runs `launch_simulation -scripts_only`. `bd.top` reports the
    generated `<bd>_wrapper` name and `bd.library` the `xil_defaultlib`
    target, so neither is hand-typed. `wrapper=False` elaborates a
    plain-signal BD module directly.
  - `VivadoProject(xpr_path, builder_tcl=..., part_num=...)` — runs
    `open_project; launch_simulation -scripts_only -absolute_path`
    with mtime-based caching against the resulting
    `xsim/elaborate.sh`. Optional `builder_tcl` produces the `.xpr`
    on first run; optional `part_num` retargets the project
    in-memory for simulation (never written back to the `.xpr`).
  - `VivadoExportedSim(tcl_file, result_dir, result_file=...,
    force_extract=...)` — for user-supplied TCL that drives its own
    `launch_simulation -scripts_only` extraction.
- `cocotb_vivado.vivado.read_sim_dir()` + `SimDirInfo`: canonical
  parsed view of a Vivado-emitted `xsim/` directory. Discovers
  per-language `.prj` files by content sniff and extracts the
  precompiled-library list (`-L` flags) plus `<lib>.glbl` modules
  from the sibling xelab `*.sh` script. The `.prj` files are
  self-contained (absolute paths and `--include` directives inline)
  — no separate CSV index is consulted.
- `cocotb_vivado.vivado.discover_default_part()` opt-in helper: runs
  Vivado once to query `[lindex [get_parts] 0]` and caches the
  answer at `~/.cache/cocotb-vivado/default_part`.
- `cocotb_vivado.__main__` — subprocess entry point that
  `runner.test()` spawns via `python -m cocotb_vivado`. Reads the
  snapshot name and optional WDB output path from environment.
- `cocotb_vivado.stub.manager` + `cocotb_vivado.stub.handles` — a
  value-change manager that emulates cocotb's edge / read-write /
  read-only callbacks by re-reading top-level signals after each XSI
  kernel step (XSI has no native value-change callback registration),
  so cocotb's stock `RisingEdge` / `FallingEdge` / `Edge` triggers work
  on any signal, not just Python-driven `Clock`s. Split out of the
  former `stub.mgr`.
- VHDL top-level support. `hdl_toplevel_lang="vhdl"` elaborates a VHDL
  top; the XSI value bridge encodes/decodes `std_logic` via its 9-state
  representation. Waveform dump via `$dumpfile` / `$dumpvars` is
  Verilog-only, so a VHDL top supports only `wave_format="wdb"`.
- `wdb_file` kwarg threaded through `xsi.XSI.__init__` and
  `stub.manager.Mgr.init`, so the WDB output path can be set explicitly
  by the runner instead of defaulting to `xsi.wdb` in the cwd.
- `pyproject.toml` mirroring cocotb upstream's lint and type
  configuration (ruff with the same extend-select / ignore set, mypy
  in strict mode with per-module overrides for the legacy modules,
  pytest with `--strict-markers`).
- `.pre-commit-config.yaml` with `ruff --fix`, `ruff-format`, basic
  whitespace/EOL fixers, and `validate-pyproject`.
- GitHub Actions workflow `.github/workflows/lint.yml` running ruff
  and mypy on every push/PR.
- `CONTRIBUTING.md` describing the Linux-only dev setup, the
  architectural rules (runner stays on XSim binaries; `.prj` files
  as the canonical interface for Vivado-managed sources), and the
  submission convention.
- `CHANGELOG.md` (this file) and `MIGRATION.md` (before/after
  guidance for users moving off the legacy `cocotb_vivado.run()`
  path).
- `.github/PULL_REQUEST_TEMPLATE.md` with required sections for
  behavioral summary, breaking changes, local test output, and the
  documentation-diff checklist.
- `examples/counter/`, `examples/parameters/`, and `examples/ip/`
  showing the runner-first API.
- `tests/test_params.py` + `tests/tb_params.v` — verify top-level
  Verilog parameter / VHDL generic pass-through to `xelab` via
  `-generic_top`.

### Changed

- **Edge triggers now observe same-timestep value deposits.** The
  value-change manager samples signals *after* cocotb applies its
  scheduled writes, so a signal written in the same timestep as a clock
  edge is visible to that edge — matching a real simulator (verified
  against nvc). The previous polling scheduler sampled the *stale*
  value, so a testbench that releases reset exactly on a clock edge now
  counts one cycle later. See [MIGRATION.md](MIGRATION.md).
- `tests/test_simple.py` and `tests/test_tb.py` rewritten on top of
  `cocotb_vivado.runner.get_runner()`. Their legacy
  `cocotb_vivado.run()`-based variants stay available but are
  skip-gated behind `COCOTB_VIVADO_TEST_DIRECT=1`.
- `tests/test_axil.py` migrated to the new runner (RTL only, no
  Vivado source). Skip gate removed.
- `tests/test_fw.py` migrated to the new runner via `VivadoProject(
  xpr_path="fw/fw.xpr", builder_tcl="fw.tcl")` as a source. Skip
  gate removed. `tests/fw.tcl` reduced to pure project construction
  — the trailing `export_simulation` and the `--dll` simset
  property are dropped; the runner adds `-dll` on its xelab
  invocation and the script extraction is now `VivadoProject`'s
  responsibility.
- `tests/test_xsi.py` remains skip-gated behind
  `COCOTB_VIVADO_TEST_DIRECT=1` — it is a low-level XSI ctypes
  smoke test rather than a runner-based simulation.
- `setup.py` reduced to a thin shim; project metadata moved to the
  `[project]` table in `pyproject.toml`.

### Removed

- `cocotb_vivado.clock_scheduler` and `cocotb_vivado.mock_triggers` —
  the Timer-polled `Clock` / edge-trigger stand-ins that emulated
  callbacks before the value-change manager. The manager now drives
  cocotb's native triggers directly, so the stand-ins (and the rule
  that only Python-driven `Clock`s could raise edges) are gone.

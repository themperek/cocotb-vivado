# Contributing to cocotb-vivado

## Development environment

cocotb-vivado is **Linux-only**. The package loads XSI shared libraries
(`libxv_simulator_kernel.so`, `xsimk.so`) via ctypes; the XSI interface
is Linux-specific and there are no plans to support Windows or macOS.

You need:

- Python 3.10 or newer.
- A Linux install of Xilinx Vivado. Vivado 2023.1 is the minimum tested
  version; newer ones are expected to work but verify locally.
- `vcd2fst` from gtkwave (optional, only needed if you select
  `wave_format="fst"`).

Set up:

```bash
# Source your Vivado environment so xelab/xvlog/xvhdl/vivado are on PATH.
# Note settings64.sh does NOT export LD_LIBRARY_PATH on every install --
# export it yourself so the XSI shared libraries can be dlopened:
source /path/to/Vivado/<version>/settings64.sh
export LD_LIBRARY_PATH=$XILINX_VIVADO/lib/lnx64.o

# Editable install of the project + test and dev dependencies
pip install -e ".[dev]"

# (Optional) install pre-commit hooks so the linters run on every commit
pre-commit install
```

## Running tests

```bash
cd tests
pytest -s test_simple.py        # one test
pytest -s                       # the whole suite
```

Tests spawn `python -m cocotb_vivado` as a subprocess that loads XSI in
process. The Vivado binaries must be reachable on `PATH`. For those tests
`LD_LIBRARY_PATH` need not be set in your shell -- the runner exports it
for the subprocess, synthesizing it from `XILINX_VIVADO` when absent.

`tests/test_xsi.py` is the exception: it dlopens `xsimk.so` *in the pytest
process* via ctypes, so it needs `LD_LIBRARY_PATH` exported **before**
Python starts. Setting it from inside the process does not work -- the
dynamic loader captures its search path at exec time. The test skips
itself with an explanatory message when the XSI kernel library is not
loadable, so a missing `LD_LIBRARY_PATH` is a skip, not a failure.

Every other test runs unconditionally -- there are no opt-in gates, so a
green `pytest tests/` means the whole suite really ran. Note `pytest
tests/` does not cover `examples/`; run both.

**Testing across versions.** `noxfile.py` (requires `uv` and `nox`) sweeps
cocotb, Python, and Vivado. The Vivado axis comes from `VIVADO_SETTINGS`, an
`os.pathsep`-joined list of `settings64.sh` paths; each is sourced in an
isolated shell, so combos never share a `PATH`. Launch from a shell with no
Vivado sourced:

```bash
export VIVADO_SETTINGS=/opt/Xilinx/Vivado/2023.1/settings64.sh:/opt/Xilinx/2025.1/Vivado/settings64.sh
nox                 # tests/ across every cocotb version x every Vivado
nox -s pythons      # tests/ across Python versions on the newest cocotb
nox -s examples     # examples/ smoke on the newest cocotb
```

If `VIVADO_SETTINGS` is unset, nox runs once against whatever Vivado is on
`PATH`, and fails fast if none is.

**Clearing the build cache after runner-code edits.** Tests default to
`always=False`, so the Tier 1 build cache
(`tests/sim_build/build_signature.json`) is active. The signature keys
on build *inputs* (sources, kwargs, fingerprints, tool versions) — not
on `runner.py` itself. After editing `src/cocotb_vivado/runner.py` or
any pipeline-affecting module (`vivado/sources.py`, `vivado/_tcl.py`,
…), clear `tests/sim_build/` before re-running:

```bash
rm -rf tests/sim_build && pytest tests/test_simple.py
```

Otherwise the cache hits on the stale snapshot, the modified code path
skips xvlog/xvhdl/xelab, and the test passes against pre-edit
artifacts. If you only changed tests or docs, the cache invalidates
correctly on its own.

## Linting and type checking

```bash
ruff check .
ruff format --check .
mypy src/
```

`pre-commit run --all-files` runs all of the above plus the basic
whitespace / line-ending hooks.

## Architectural rules

Two rules govern where code goes. Both are enforceable by `grep` during
review.

1. **`cocotb_vivado.vivado` is the home for anything that
   invokes the `vivado` binary** (the full tool, not the small XSim
   binaries). If you're adding a `subprocess.run([..., 'vivado', ...])`
   call, it belongs in `vivado.py`, not in `runner.py`.
2. **`cocotb_vivado.runner` invokes only the XSim binaries**
   (`xelab` / `xvlog` / `xvhdl`). When Vivado-the-tool work is required
   (TCL execution, IP regeneration, project export, part discovery),
   the runner delegates to `vivado`.

For Vivado-managed sources (`.xci`, `.bd`, `.xpr`), Vivado-emitted
`.prj` files (consumed via `xvlog -prj` / `xvhdl -prj`) plus the
sibling `*.sh` xelab script are the canonical interface between
`vivado` and `runner`. Producers live in `vivado` (each
`VivadoSource.prepare()` runs the appropriate `vivado -mode batch`
invocation that produces them); the parser and consumer live in
`vivado.sim_dir` and `runner` respectively.

## Supporting multiple cocotb versions

cocotb-vivado stands in for `cocotb.simulator`, the C extension cocotb
normally links against. That shim is expected to *adapt*: when a cocotb
release changes the GPI surface (a callback loses its user-data argument, a
loader drops a parameter), the shim absorbs the difference so one install
works across every supported cocotb version.

**The rule: the shim adapts, the tests stay precise.** Version handling
belongs inside `src/cocotb_vivado/`, invisible to the suite — a sentinel
default, an `inspect.signature` branch, a superset of names every version can
read back. A test should never need to know which cocotb it runs under.

**The red flag** is a test that itself accepts either of two behaviours —
most visibly `pytest.raises((OldError, NewError))`. That difference has
surfaced *below* the shim, in code we don't control (e.g. `cocotb_tools.
runner`), where the shim cannot paper over it. Each such leak is a divergence
the suite can now observe. These leaks are the metric, not a nuisance to
suppress: one or two are tolerable, but when they accumulate the cost of
keeping the older cocotb is no longer hidden — that is the signal to raise
the floor and drop it. Count them; don't bury them under more branching.

**Before widening the supported range:**

1. Add the version to `COCOTB_VERSIONS` in `noxfile.py`.
2. Run the matrix against every supported Vivado (see *Running tests*).
3. Update the "Tested versions" table in `README.md`.
4. Only then widen the bound in `pyproject.toml`.

The static, Vivado-free `scripts/check_cocotb_compat.py` catches GPI-surface
drift on new cocotb releases, but it runs no simulation — a green static
check is necessary, not sufficient. The nox matrix is the real gate.

## Why a separate package, not upstream cocotb

Reasonable question to ask once. The short answer:

- **Vivado XSim does not expose VPI or VHPI.** Every cocotb upstream
  simulator backend (Icarus, Verilator, Questa, GHDL, Riviera,
  Xcelium, NVC) talks to its simulator through VPI / VHPI / FLI via a
  cocotb-maintained C shim. Vivado ships only XSI — a low-level
  kernel API with no value-change callback registration. `xelab` has
  no `-loadvpi` equivalent. It's an architectural mismatch, not a
  missing-feature gap.
- **The XSI workarounds don't generalize.** The value-change
  manager's post-step signal re-reads (emulating callbacks XSI won't
  deliver), the `sys.modules["cocotb.simulator"]` patch, and the
  `python -m cocotb_vivado` subprocess pattern exist *because* XSI has
  no native value-change callback registration. They're a XSim-shaped
  crutch with no reuse in any other simulator context.
- **Vivado tool integration (TCL, IP regeneration, project export)
  is vendor-specific** and doesn't belong in cocotb core.
- **No community signal.** No issues in the cocotb/cocotb repo
  mention Vivado, XSim, or Xilinx.
- **Independent release cadence.** Vivado-specific tooling iterates
  on Xilinx releases, not cocotb releases.

The cocotb-blessed pattern for external simulator backends is exactly
what this package does: subclass `cocotb.runner.Simulator`, ship as a
third-party package, register via the project's own `get_runner()`
shim. No fork of cocotb internals; just a backend that follows the
documented integration pattern.

## Submitting changes

- Open PRs against `main`.
- Use the PR template in `.github/PULL_REQUEST_TEMPLATE.md`.
- Every PR must update `CHANGELOG.md` under the appropriate heading
  (`### Added` / `### Changed` / `### Removed` / `### Fixed`). If the
  PR introduces a breaking change, add a row to `MIGRATION.md` as well.
- New public symbols need module / class / function docstrings stating
  their contract (parameters, return value, raises, notable side
  effects). Type hints carry the rest — don't duplicate type
  information in docstring prose.
- Keep comments short and focused on intent. Don't describe history
  (no "previously this returned X" / "renamed from Y"); that belongs
  in commit messages and CHANGELOG.

## License

By contributing, you agree your contributions are licensed under the
[Apache License 2.0](LICENSE).

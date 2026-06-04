# cocotb-vivado

[![PyPI version](https://badge.fury.io/py/cocotb-vivado.svg)](https://pypi.org/project/cocotb-vivado/)
[![lint](https://github.com/themperek/cocotb-vivado/actions/workflows/lint.yml/badge.svg)](https://github.com/themperek/cocotb-vivado/actions/workflows/lint.yml)

A Python/[cocotb](https://github.com/cocotb/cocotb/) interface to the
[Xilinx Vivado Simulator](https://docs.xilinx.com/v/u/en-US/dh0010-vivado-simulation-hub).

Based on [cocotb-stub-sim](https://github.com/fvutils/cocotb-stub-sim).
The Python runner and the value-change manager are derived from
[vicoco](https://github.com/kiran-vuksanaj/vicoco) by Kiran Vuksanaj.

---

## Project status

**Active development.** The Python runner experience is being rebuilt.
See [CHANGELOG.md](CHANGELOG.md) for what's landed and
[MIGRATION.md](MIGRATION.md) for breaking changes.

Known limitations:

- Only top-level ports are accessible (XSI limitation).
- `RisingEdge` / `FallingEdge` / `Edge` only see changes after Python
  advances time (`Timer` / `cocotb.clock.Clock`). Verilog `#` delays are
  not visible to those triggers, so awaiting an edge on a DUT-driven
  clock with no concurrent Python-driven time advance will not progress.
- Waveform dump via `$dumpfile` / `$dumpvars` is Verilog-only and
  cannot hook into a VHDL top; with a VHDL top, only the Vivado WDB
  output (`wave_format="wdb"`) is available.
- Direct access to the **XSI interface** via `cocotb_vivado.xsi` is
  available for low-level tooling.

## Platform support

**Linux only.** The loader is Linux-specific — cocotb-vivado `dlopen`s
the XSim snapshot (`xsimk.so`) via `ctypes` and derives an
`LD_LIBRARY_PATH` from Vivado's `lib/lnx64.o`. XSI itself is not
Linux-specific (Vivado's XSim and the XSI C API ship on Windows too), so
a Windows port is plausible, but it is untested.

## Tested Vivado versions

- Vivado **2023.1** — minimum supported.
- Newer versions are expected to work but verify locally.

## Installation

```bash
pip install cocotb-vivado
```

## Quickstart

```python
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

from cocotb_vivado.runner import get_runner


@cocotb.test()
async def simple_test(dut):
    dut.clk.value = 0
    await Timer(10, units="ns")
    dut.clk.value = 1
    await Timer(10, units="ns")
    assert dut.out.value == 1


def test_simple():
    runner = get_runner("vivado")
    runner.build(
        sources=[Path(__file__).parent / "tb.v"],
        hdl_toplevel="tb",
        always=True,
        timescale=("1ns", "1ps"),
    )
    runner.test(
        hdl_toplevel="tb",
        test_module="test_simple",
        hdl_toplevel_lang="verilog",
        testcase="simple_test",
    )
```

See [`examples/`](examples/) for runnable projects and the `tests/`
directory for more scenarios.

Before running:

```bash
source /path/to/Vivado/<version>/settings64.sh
pytest -s tests/
```

`xelab` / `xvlog` / `xvhdl` must be on `PATH` and `LD_LIBRARY_PATH`
must be set (or `XILINX_VIVADO` set as a courtesy fallback so the
runner can synthesize one for the test subprocess).

## How the GPI shim is installed

Importing `cocotb_vivado` replaces `cocotb.simulator` in `sys.modules`
with the in-process XSI stub, and cocotb caches the simulator handle at
its own import time — so the stub has to be installed before cocotb is
imported.

**This is handled for you and imposes no rule on your testbench.**
`runner.test()` spawns `python -m cocotb_vivado`, which installs the stub
before importing cocotb; cocotb then loads your test module. Import
`cocotb` and `cocotb_vivado` in whatever order your formatter prefers:

```python
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from cocotb_vivado.runner import get_runner
```

## Waveform output

The `wave_format` kwarg on `runner.build()` / `runner.test()` selects
the dump format:

```python
runner.build(..., wave_format="vcd")      # Verilog $dumpfile/$dumpvars
runner.build(..., wave_format="fst")      # VCD post-processed by vcd2fst
runner.build(..., wave_format="wdb")      # Vivado native, viewable in xsim --gui
runner.build(...)                          # default: no waves
```

All formats land in `{build_dir}/{hdl_toplevel}.{ext}` for symmetry.

## Vivado-managed sources (IP / BD / XPR)

Vivado inputs are passed to the runner via **source objects** from
`cocotb_vivado.vivado`, alongside plain HDL paths in
`runner.build(sources=[...])`. Pick the class by input file format:

| Input | Class | Vivado mechanism |
|-------|-------|------------------|
| `.xci` | `VivadoIp` | `add_files; export_ip_user_files` |
| `.bd` | `VivadoBd` | `make_wrapper; launch_simulation -scripts_only` |
| `.xpr` | `VivadoProject` | `open_project; launch_simulation -scripts_only` |
| `.tcl` / pre-extracted | `VivadoExportedSim` | runs your TCL |

A source object sits in the same `sources=` list as plain HDL. Here a
`blk_mem_gen` IP is instantiated by a hand-written wrapper, and the wrapper
is the toplevel (`tests/test_bram.py`):

```python
from pathlib import Path

from cocotb_vivado.runner import get_runner
from cocotb_vivado.vivado import VivadoIp

here = Path(__file__).resolve().parent
runner = get_runner("vivado")
runner.build(
    sources=[
        VivadoIp(
            "ip/blk_mem_kilobyte/blk_mem_kilobyte.xci",
            builder_tcl=here / "ip" / "blk_mem_kilobyte" / "regen.tcl",
            part_num="xczu7eg-ffvc1156-2-e",
        ),
        here / "bram_wrap.sv",
    ],
    hdl_toplevel="bram_wrap",
)
```

A block design or a project defines its own toplevel instead, and reports
the names to use (`tests/test_bd_axi.py`):

```python
from cocotb_vivado.vivado import VivadoBd

bd = VivadoBd(
    "ip/bd_axi/bd_axi.bd",
    builder_tcl=here / "ip" / "bd_axi" / "regen.tcl",
    part_num="xczu7eg-ffvc1156-2-e",
)
runner.build(
    sources=[bd],
    hdl_toplevel=bd.top,        # "bd_axi_wrapper" — Vivado's wrapper name
    hdl_library=bd.library,     # "xil_defaultlib"
)
```

Note the path convention: a relative `.xci` / `.bd` path resolves **under
the build directory** — that is where `builder_tcl` deposits it — while
`builder_tcl` itself is an input you already have, so pass it absolute
(relative resolves against the current working directory).

**One design-defining source per build.** `hdl_library` is a single
setting for the whole build — every plain source is compiled into it and
the toplevel is elaborated from it — so a `VivadoBd` and your own RTL
necessarily share one library. `VivadoBd`, `VivadoProject` and
`VivadoExportedSim` each extract into `xil_defaultlib`, so combining two
of them in one build merges two independently generated structural HDL
sets and risks name collisions. Use at most one of those three, plus any
number of `VivadoIp` and plain HDL sources.

Each source self-orchestrates its Vivado batch invocation (with
mtime-based caching) and returns a parsed view of the resulting
Vivado-emitted `xsim/` directory: per-language `.prj` files (consumed
via `xvlog -prj` / `xvhdl -prj`) and a sibling `*.sh` script whose
`xelab` command line contributes the `-L` library set and any
`<lib>.glbl` modules. `VivadoBd`, `VivadoProject` and `VivadoExportedSim`
go through `launch_simulation -scripts_only -absolute_path`;
`VivadoIp` uses `export_ip_user_files`.

**Block designs and interface flattening.** XSI exposes only top-level
*scalar* ports — there is no hierarchical or interface access. A block
design whose top is built from `create_bd_intf_port` (AXI/AXIS/BRAM) is
therefore not directly drivable. `VivadoBd` defaults to `wrapper=True`,
generating Vivado's RTL wrapper (`make_wrapper -top`) that flattens each
interface bundle into discrete scalar ports — the form `cocotbext-axi`
binds to. `bd.top` reports the resulting `<bd>_wrapper` name so you need
not hardcode it. For a BD whose top is all plain signals
(`create_bd_port`), pass `wrapper=False` to elaborate the BD module
directly (`bd.top` is then the bare `<bd>`).

`part_num` is required on `VivadoIp` and `VivadoBd` (the IP/BD generator
needs a `set_part` target). `VivadoProject` reads the part from the XPR
and accepts an optional `part_num` to *retarget* in-memory for
simulation. `VivadoExportedSim`'s TCL controls its own part. It falls back
to the `COCOTB_DEFAULT_PART_NUM` environment variable, and
`cocotb_vivado.vivado.discover_default_part()` is an opt-in helper that
queries Vivado once and caches the answer. Pure-RTL builds without any
`VivadoSource` instance never touch the `vivado` binary.

The `.bd` can be committed alongside the test, or regenerated on first
build by passing `builder_tcl` (a script that constructs it and
`save_bd_design`s) — the latter keeps the fixture Vivado-version-
agnostic. To use a block design as a *sub-component* under your own
top-level RTL, list the `VivadoBd` alongside your HDL and name your
module as the top: `sources=[VivadoBd("x.bd"), "my_tb.sv"]`,
`hdl_toplevel="my_tb"`.

See `tests/test_bd_axi.py` for a `VivadoBd` example that flattens an
AXI-Lite + AXIS block design, and `tests/test_fw.py` for the equivalent
via a full `VivadoProject`.

## cocotb extensions

Extensions like [cocotbext-axi](https://github.com/alexforencich/cocotbext-axi)
work as long as the DUT is clocked by a Python-driven `Clock` (XSI
exposes no native GPI clock). AXI bus accesses are routed through
the cocotb scheduler the extension expects.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Acknowledgment

We'd like to thank our employer, [Dectris](https://dectris.com/) for
supporting this work.

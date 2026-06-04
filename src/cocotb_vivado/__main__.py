# Copyright cocotb-vivado contributors
# Copyright 2026 Kiran Vuksanaj
# Licensed under the Apache License 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Derived from vicoco's subprocess entry point
# (https://github.com/kiran-vuksanaj/vicoco).

"""Subprocess entry point invoked by :meth:`Vivado.test`.

The runner spawns ``python -m cocotb_vivado`` after build, passing the
snapshot name and (optionally) the WDB output path via environment
variables. This module patches ``cocotb.simulator`` to point at the
in-process XSI stub, initializes the simulator manager, runs the
cocotb regression, and exits with the regression's pass/fail status.
"""

from __future__ import annotations

import importlib
import os
import sys
from sys import argv

# The stub must replace cocotb.simulator BEFORE cocotb itself is imported,
# so the GPI shim is in place when cocotb wires up its callbacks.
sys.modules["cocotb.simulator"] = importlib.import_module(
    "cocotb_vivado.stub.simulator"
)

import cocotb  # noqa: E402

from .stub.manager import Mgr  # noqa: E402


def _initialize_simulator(
    argv_: list[str], xsim_design: str, wdb_file: str | None = None
) -> None:
    toplevel_lang = os.getenv("TOPLEVEL_LANG", "verilog")
    mgr = Mgr.init(  # type: ignore[no-untyped-call]
        xsim_design, wdb_file=wdb_file, toplevel_lang=toplevel_lang
    )
    cocotb._initialise_testbench([])
    mgr.run()
    mgr.close()
    if cocotb.regression_manager.failures:
        sys.exit(1)


if __name__ == "__main__":
    snapshot_name = os.getenv("VIVADO_SNAPSHOT_NAME")
    if not snapshot_name:
        raise SystemExit(
            "ERROR: VIVADO_SNAPSHOT_NAME is unset. "
            "Launch via cocotb_vivado.runner.Vivado.test(), not directly."
        )

    design_so_file = f"xsim.dir/{snapshot_name}/xsimk.so"
    wdb_file = os.getenv("VIVADO_WDB_FILE") or None

    _initialize_simulator(argv, design_so_file, wdb_file=wdb_file)

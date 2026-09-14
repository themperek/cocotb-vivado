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
import importlib.util
import os
import sys

# Replace cocotb.simulator with the in-process XSI stub. cocotb's
# ``cocotb.handle`` reads ``cocotb.simulator.*`` at import time, so the
# stub must be bound as the ``cocotb.simulator`` *attribute* before
# cocotb's ``__init__`` runs. Putting it in ``sys.modules`` alone does not
# bind the parent attribute — importlib only does that when it loads the
# submodule itself — so build the cocotb module, set the attribute, then
# execute its ``__init__``.
_stub = importlib.import_module("cocotb_vivado.stub.simulator")
sys.modules["cocotb.simulator"] = _stub

_spec = importlib.util.find_spec("cocotb")
assert _spec is not None and _spec.loader is not None
cocotb = importlib.util.module_from_spec(_spec)
cocotb.simulator = _stub  # type: ignore[attr-defined]
sys.modules["cocotb"] = cocotb
_spec.loader.exec_module(cocotb)

from pygpi.entry import load_entry  # noqa: E402

from .stub.manager import Mgr  # noqa: E402


def _initialize_simulator(xsim_design: str, wdb_file: str | None = None) -> None:
    toplevel_lang = os.getenv("TOPLEVEL_LANG", "verilog")
    mgr = Mgr.init(  # type: ignore[no-untyped-call]
        xsim_design, wdb_file=wdb_file, toplevel_lang=toplevel_lang
    )
    # pygpi.entry.load_entry runs the cocotb regression (reading sys.argv
    # itself) and handles pass/fail / exit-code on its own. Do not call
    # mgr.close() afterwards — cocotb's at-exit handlers still reach into
    # the simulator, and closing the XSI handle first crashes the process
    # with SIGSEGV during teardown.
    load_entry()
    mgr.run()


if __name__ == "__main__":
    snapshot_name = os.getenv("VIVADO_SNAPSHOT_NAME")
    if not snapshot_name:
        raise SystemExit(
            "ERROR: VIVADO_SNAPSHOT_NAME is unset. "
            "Launch via cocotb_vivado.runner.Vivado.test(), not directly."
        )

    design_so_file = f"xsim.dir/{snapshot_name}/xsimk.so"
    wdb_file = os.getenv("VIVADO_WDB_FILE") or None

    _initialize_simulator(design_so_file, wdb_file=wdb_file)

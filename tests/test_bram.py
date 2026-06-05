# Copyright cocotb-vivado contributors
# Copyright 2026 Kiran Vuksanaj
# SPDX-License-Identifier: Apache-2.0
#
# The clocks_only test is adopted from vicoco's test/sim/test_bram.py
# (https://github.com/kiran-vuksanaj/vicoco).

"""Block-RAM IP example: a ``blk_mem_gen`` instance wrapped by ``bram_wrap.sv``.

Exercises ``VivadoIp`` end-to-end. The XCI is *generated* by the
``builder_tcl`` hook on first build — the test fixture is the TCL
recipe, not a committed Vivado-version-locked XCI.
"""

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer

from cocotb_vivado.runner import get_runner
from cocotb_vivado.vivado import VivadoIp


@cocotb.test()
async def clocks_only(dut):
    dut.ena.value = 1
    dut.enb.value = 1

    cocotb.start_soon(Clock(dut.clka, 10, unit="ns").start())
    cocotb.start_soon(Clock(dut.clkb, 12, unit="ns").start())

    await Timer(200, unit="ns")


def test_bram(build_dir):
    proj_path = Path(__file__).resolve().parent
    runner = get_runner(os.getenv("SIM", "vivado"))
    runner.build(
        sources=[
            VivadoIp(
                "ip/blk_mem_kilobyte/blk_mem_kilobyte.xci",
                builder_tcl=proj_path / "ip" / "blk_mem_kilobyte" / "regen.tcl",
                part_num="xczu7eg-ffvc1156-2-e",
            ),
            proj_path / "bram_wrap.sv",
        ],
        hdl_toplevel="bram_wrap",
        timescale=("1ns", "1ps"),
        build_dir=str(build_dir),
    )
    runner.test(
        hdl_toplevel="bram_wrap",
        test_module="test_bram",
        hdl_toplevel_lang="verilog",
        build_dir=str(build_dir),
    )


if __name__ == "__main__":
    _build_dir = Path(__file__).resolve().parent / "sim_build" / Path(__file__).stem
    test_bram(_build_dir)

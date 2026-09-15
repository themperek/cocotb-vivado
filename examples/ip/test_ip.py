# Copyright cocotb-vivado contributors
# Copyright 2026 Kiran Vuksanaj
# SPDX-License-Identifier: Apache-2.0
#
# The clocks_only test is adopted from vicoco's test/sim/test_bram.py
# (https://github.com/kiran-vuksanaj/vicoco).

"""Vivado IP example: a ``blk_mem_gen`` instance wrapped by ``bram_wrap.sv``.

Shows ``VivadoIp`` end to end. The XCI is *generated* by the
``builder_tcl`` hook (``ip/blk_mem_kilobyte/regen.tcl``) on first build,
so this example carries no Vivado-version-locked XCI — it works on any
Vivado that has the ``blk_mem_gen`` IP.
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


def test_ip():
    here = Path(__file__).resolve().parent
    runner = get_runner(os.getenv("SIM", "vivado"))
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
        timescale=("1ns", "1ps"),
    )
    runner.test(
        hdl_toplevel="bram_wrap",
        test_module="test_ip",
        hdl_toplevel_lang="verilog",
    )


if __name__ == "__main__":
    test_ip()

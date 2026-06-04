"""Smoke test for a VHDL top-level design.

Exercises the std_logic 9-state encoding path in
:class:`cocotb_vivado.xsi.XSI`: with ``hdl_toplevel_lang="vhdl"`` the
runner exports ``TOPLEVEL_LANG=vhdl``, the in-sim manager opens the
snapshot with the VHDL encoding, and ``dut.q.value`` / ``dut.rst.value``
go through the byte-per-bit ``std_logic`` table.

The DUT is a trivially small synchronous counter (``tb_counter.vhd``)
so the test verifies the encoding round-trip, not anything subtle about
VHDL semantics.
"""

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer

from cocotb_vivado.runner import get_runner


@cocotb.test()
async def counter_vhdl_smoke(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start(start_high=False))

    dut.rst.value = 1
    # Hold reset until the falling edge of cycle 3 so the next rising
    # edge (the one we want to count from) sees rst=0 unambiguously.
    await Timer(33, units="ns")
    dut.rst.value = 0

    expected = 0
    for _ in range(8):
        await Timer(10, units="ns")
        expected = (expected + 1) & 0xFF
        actual = int(dut.q.value)
        assert actual == expected, (
            f"counter mismatch: got {actual}, expected {expected}"
        )


def test_counter_vhdl(build_dir):
    here = Path(__file__).resolve().parent
    runner = get_runner(os.getenv("SIM", "vivado"))
    runner.build(
        sources=[here / "tb_counter.vhd"],
        hdl_toplevel="tb_counter",
        always=False,
        timescale=("1ns", "1ps"),
        build_dir=str(build_dir),
    )
    runner.test(
        hdl_toplevel="tb_counter",
        hdl_toplevel_lang="vhdl",
        test_module="test_counter_vhdl",
        testcase="counter_vhdl_smoke",
        build_dir=str(build_dir),
    )


if __name__ == "__main__":
    test_counter_vhdl(Path("sim_build/test_counter_vhdl"))

"""Smoke test for the cocotb-vivado Python runner."""

import os
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

from cocotb_vivado.runner import get_runner


@cocotb.test()
async def simple_test(dut):
    dut.clk.value = 0
    await Timer(10, unit="ns")
    assert dut.out.value == 0
    dut.clk.value = 1
    await Timer(10, unit="ns")
    assert dut.out.value == 1


def test_simple(build_dir):
    """Build tb.v with the Python runner and run the cocotb test."""
    proj_path = Path(__file__).resolve().parent
    sources = [proj_path / "tb.v"]

    sim = os.getenv("SIM", "vivado")
    runner = get_runner(sim)

    runner.build(
        sources=sources,
        hdl_toplevel="tb",
        always=False,
        timescale=("1ns", "1ps"),
        build_dir=str(build_dir),
    )
    runner.test(
        hdl_toplevel="tb",
        test_module="test_simple",
        hdl_toplevel_lang="verilog",
        testcase="simple_test",
        build_dir=str(build_dir),
    )


if __name__ == "__main__":
    _build_dir = Path(__file__).resolve().parent / "sim_build" / Path(__file__).stem
    test_simple(_build_dir)

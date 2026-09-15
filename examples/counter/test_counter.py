"""Hello-world example: drive an 8-bit counter for a few cycles."""

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer

from cocotb_vivado.runner import get_runner


@cocotb.test()
async def counter_increments(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start(start_high=False))

    # The clock starts low, so rising edges land at t = 5, 15, 25, ... ns.
    # cocotb applies value deposits before the simulator evaluates a timestep,
    # so releasing reset at exactly t = 25 ns would already be visible to that
    # edge and the counter would start one cycle early. Release between edges
    # instead, which makes t = 35 ns plainly the first counted edge.
    dut.rst.value = 1
    await Timer(27, unit="ns")
    dut.rst.value = 0
    await Timer(3, unit="ns")

    expected = 0
    for _ in range(8):
        await Timer(10, unit="ns")
        expected = (expected + 1) & 0xFF
        assert int(dut.q.value) == expected, (
            f"expected q={expected}, got {int(dut.q.value)}"
        )


def test_counter():
    here = Path(__file__).resolve().parent
    build_dir = here / "sim_build"
    runner = get_runner(os.getenv("SIM", "vivado"))
    runner.build(
        sources=[here / "counter.v"],
        hdl_toplevel="counter",
        always=False,
        timescale=("1ns", "1ps"),
        build_dir=str(build_dir),
    )
    runner.test(
        hdl_toplevel="counter",
        test_module="test_counter",
        hdl_toplevel_lang="verilog",
        testcase="counter_increments",
        build_dir=str(build_dir),
    )


if __name__ == "__main__":
    test_counter()

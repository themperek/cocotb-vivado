"""Clock + vector-pin behavioral test, exercising the Python runner."""

import os
from pathlib import Path

import cocotb
import pytest
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotb.types import LogicArray  # replaces 1.x's cocotb.binary.BinaryValue

from cocotb_vivado.runner import get_runner


async def on_signal(signal, timer):
    prev = signal.value
    while True:
        await timer
        now = signal.value
        if prev != now:
            break
        prev = now


@cocotb.test()
async def cocotb_tb_test(dut):
    clk = Clock(dut.clk, 5, unit="ns")
    cocotb.start_soon(clk.start(start_high=False))

    await Timer(10, "ns")

    expected_out_transitions = ["0", "1"] * 5
    for _ in range(10):
        await on_signal(dut.out, Timer(1, "ns"))
        cocotb.log.info(f"out={dut.out.value}")
        assert expected_out_transitions.pop(0) == str(dut.out.value)

    await Timer(100, "ns")

    for v in ["1", "0", "x", "z", "X", "Z", "0"]:
        dut.vec_in.set(LogicArray(v * 100))
        await Timer(10, "ns")
        vec_out = dut.vec_out.value
        cocotb.log.info(f"dut.vec_out {vec_out}")
        assert (v * 100).lower() == str(vec_out).lower()


@cocotb.test()
async def cocotb_tb_test_fail(dut):
    await Timer(10, "ns")
    pytest.fail("deliberate failure to exercise the xfail path")


def _run_tb(build_dir, test_module="test_tb", testcase="cocotb_tb_test"):
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
        test_module=test_module,
        hdl_toplevel_lang="verilog",
        testcase=testcase,
        build_dir=str(build_dir),
    )


def test_tb(build_dir):
    _run_tb(build_dir, testcase="cocotb_tb_test")


@pytest.mark.xfail
def test_tb_fail(build_dir):
    _run_tb(build_dir, testcase="cocotb_tb_test_fail")


@pytest.mark.xfail
def test_tb_fail_init(build_dir):
    _run_tb(build_dir, test_module="no_existing")


if __name__ == "__main__":
    _build_dir = Path(__file__).resolve().parent / "sim_build" / Path(__file__).stem
    test_tb(_build_dir)

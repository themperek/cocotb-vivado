"""Verify ``runner.build(parameters=...)`` forwards values to xelab via ``-generic_top``.

Also probes the error path: an unknown parameter name should make xelab
fail with ``[XSIM 43-3281]``, which the runner surfaces as
``SystemExit``.
"""

import os
import subprocess
from pathlib import Path

import cocotb
import pytest
from cocotb.triggers import Timer

from cocotb_vivado.runner import get_runner


@cocotb.test()
async def cocotb_param_test(dut):
    expected_width = int(os.environ["EXPECTED_WIDTH"])
    expected_depth = int(os.environ["EXPECTED_DEPTH"])

    await Timer(1, "ns")

    assert len(dut.vec_out) == expected_width, (
        f"expected vec_out width {expected_width}, got {len(dut.vec_out)}"
    )
    assert len(dut.depth_out) == expected_depth, (
        f"expected depth_out width {expected_depth}, got {len(dut.depth_out)}"
    )


def _run(build_dir, parameters):
    proj_path = Path(__file__).resolve().parent
    sources = [proj_path / "tb_params.v"]

    sim = os.getenv("SIM", "vivado")
    runner = get_runner(sim)

    runner.build(
        sources=sources,
        hdl_toplevel="tb_params",
        always=False,
        timescale=("1ns", "1ps"),
        parameters=parameters,
        build_dir=str(build_dir),
    )
    runner.test(
        hdl_toplevel="tb_params",
        test_module="test_params",
        hdl_toplevel_lang="verilog",
        testcase="cocotb_param_test",
        build_dir=str(build_dir),
    )


def test_params_default(build_dir):
    os.environ["EXPECTED_WIDTH"] = "8"
    os.environ["EXPECTED_DEPTH"] = "4"
    _run(build_dir, parameters={})


def test_params_override(build_dir):
    os.environ["EXPECTED_WIDTH"] = "16"
    os.environ["EXPECTED_DEPTH"] = "7"
    _run(build_dir, parameters={"WIDTH": 16, "DEPTH": 7})


def test_params_unknown(build_dir):
    os.environ["EXPECTED_WIDTH"] = "8"
    os.environ["EXPECTED_DEPTH"] = "4"
    # cocotb 1.x's Simulator raised SystemExit on a subprocess failure;
    # cocotb 2.x's cocotb_tools.runner.Runner lets subprocess raise its
    # own CalledProcessError. Accept either to support both vintages.
    with pytest.raises((SystemExit, subprocess.CalledProcessError)):
        _run(build_dir, parameters={"NOT_A_REAL_PARAM": 1234})


if __name__ == "__main__":
    _build_dir = Path(__file__).resolve().parent / "sim_build" / Path(__file__).stem
    test_params_default(_build_dir)
    test_params_override(_build_dir)
    test_params_unknown(_build_dir)

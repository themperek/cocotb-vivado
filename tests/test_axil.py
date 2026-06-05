"""AXI-Lite RTL test exercising cocotbext-axi with the Python runner."""

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotbext.axi import AxiLiteBus, AxiLiteMaster, AxiLiteRam

from cocotb_vivado.runner import get_runner


@cocotb.test()
async def cocotb_axil_test(dut):
    clk = Clock(dut.clk, 200, unit="ns")
    cocotb.start_soon(clk.start())

    dut.rst.value = 1
    await Timer(500, "ns")
    dut.rst.value = 0

    axil_master = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "axil"), dut.clk, dut.rst)
    AxiLiteRam(AxiLiteBus.from_prefix(dut, "axil"), dut.clk, dut.rst, size=2**16)

    data_in = list(range(16))
    await axil_master.write(0, data_in)

    data_out = []
    data_out = list((await axil_master.read(12, 4)).data) + data_out
    data_out = list((await axil_master.read(8, 4)).data) + data_out
    data_out = list((await axil_master.read(4, 4)).data) + data_out
    data_out = list((await axil_master.read(0, 4)).data) + data_out

    assert data_in == data_out


def test_axil(build_dir):
    proj_path = Path(__file__).resolve().parent
    runner = get_runner(os.getenv("SIM", "vivado"))
    runner.build(
        sources=[proj_path / "test_axil.v"],
        hdl_toplevel="test_axil",
        always=False,
        timescale=("1ns", "1ps"),
        build_dir=str(build_dir),
    )
    runner.test(
        hdl_toplevel="test_axil",
        test_module="test_axil",
        hdl_toplevel_lang="verilog",
        testcase="cocotb_axil_test",
        build_dir=str(build_dir),
    )


if __name__ == "__main__":
    _build_dir = Path(__file__).resolve().parent / "sim_build" / Path(__file__).stem
    test_axil(_build_dir)

"""Block-diagram IP example: AXIS FIFO + AXI-Lite via cocotbext-axi.

``fw.tcl`` builds a Zynq UltraScale+ project. ``VivadoProject``
runs it on first call and then extracts simulation scripts via
``launch_simulation -scripts_only`` — exercising the project-build
hook end-to-end.
"""

import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotbext.axi import (
    AxiLiteBus,
    AxiLiteMaster,
    AxiStreamBus,
    AxiStreamSink,
    AxiStreamSource,
)

from cocotb_vivado.runner import get_runner
from cocotb_vivado.vivado import VivadoProject


async def reset(signal, timer):
    signal.value = 1
    await timer
    signal.value = 0


@cocotb.test()
async def cocotb_fw_test(dut):
    AXIS_FIFO_BASEADDR = 0x1000

    clk = Clock(dut.aclk, 200, unit="ns")
    cocotb.start_soon(clk.start())

    cocotb.start_soon(reset(dut.areset, Timer(520, "ns")))

    axil_master = AxiLiteMaster(
        AxiLiteBus.from_prefix(dut, "S_AXI"), dut.aclk, dut.areset
    )
    axis_rx = AxiStreamSource(
        AxiStreamBus.from_prefix(dut, "AXIS_RX"), dut.aclk, dut.areset
    )
    axis_tx = AxiStreamSink(
        AxiStreamBus.from_prefix(dut, "AXIS_TX"), dut.aclk, dut.areset
    )

    data_in = list(range(32))
    await axil_master.write(0x10, data_in)
    data_out = list((await axil_master.read(0x10, 32)).data)

    assert data_in == data_out

    rx_data_send = []
    for i in range(4):
        d = list(range((i + 1) * 4))
        rx_data_send += d
        await axis_rx.write(d)
        await axis_rx.wait()

    rx_size = list((await axil_master.read(AXIS_FIFO_BASEADDR + 0x1C, 4)).data)
    assert rx_size == [10, 0, 0, 0]

    rx_data = []
    for _ in range(10):
        rx_data += list((await axil_master.read(AXIS_FIFO_BASEADDR + 0x20, 4)).data)

    assert rx_data == rx_data_send

    for i in range(8):
        await axil_master.write(
            AXIS_FIFO_BASEADDR + 0x10, list(range(i * 4, i * 4 + 4))
        )
        await axil_master.wait()

    await axil_master.write(AXIS_FIFO_BASEADDR + 0x14, [0x20, 0, 0, 0])

    tx_data = (await axis_tx.recv()).tdata
    assert bytearray(range(8 * 4)) == tx_data

    dut.areset.value = 0


def test_fw(build_dir):
    proj_path = Path(__file__).resolve().parent
    runner = get_runner(os.getenv("SIM", "vivado"))
    runner.build(
        sources=[
            VivadoProject(
                xpr_path="fw/fw.xpr",
                builder_tcl=proj_path / "fw.tcl",
            ),
        ],
        hdl_toplevel="fw_wrapper",
        hdl_library="xil_defaultlib",
        always=False,
        timescale=("1ns", "1ps"),
        build_dir=str(build_dir),
    )
    runner.test(
        hdl_toplevel="fw_wrapper",
        hdl_toplevel_library="xil_defaultlib",
        test_module="test_fw",
        hdl_toplevel_lang="verilog",
        testcase="cocotb_fw_test",
        build_dir=str(build_dir),
    )


if __name__ == "__main__":
    _build_dir = Path(__file__).resolve().parent / "sim_build" / Path(__file__).stem
    test_fw(_build_dir)

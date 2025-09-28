from cocotb_vivado import run
import subprocess
import os
import pathlib
import shutil

import cocotb
from cocotb.triggers import Timer

import cocotb_vivado.mock_triggers

from cocotbext.axi import AxiLiteBus, AxiLiteMaster
from cocotbext.axi import AxiStreamSink, AxiStreamSource, AxiStreamBus


async def reset(signal, timer):
    signal.value = 1
    await timer
    signal.value = 0


@cocotb.test()
async def cocotb_fw_test(dut):
    AXIS_FIFO_BASEADDR = 0x1000

    clk_period = 200
    clk_timer = Timer(clk_period // 2, "ns")

    cocotb_vivado.mock_triggers.set_timer(clk_timer)

    cocotb.start_soon(cocotb_vivado.mock_triggers.clock(dut.aclk))

    cocotb.start_soon(reset(dut.areset, Timer(520, "ns")))

    axil_master = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "S_AXI"), dut.aclk, dut.areset)
    axis_rx = AxiStreamSource(AxiStreamBus.from_prefix(dut, "AXIS_RX"), dut.aclk, dut.areset)
    axis_tx = AxiStreamSink(AxiStreamBus.from_prefix(dut, "AXIS_TX"), dut.aclk, dut.areset)

    data_in = list(range(32))
    await axil_master.write(0x10, data_in)
    data_out = list((await axil_master.read(0x10, 32)).data)

    print(data_in)
    print(data_out)

    assert data_in == data_out

    #

    rx_data_send = []
    for i in range(4):
        d = list(range((i + 1) * 4))
        rx_data_send += d
        await axis_rx.write(d)
        await axis_rx.wait()

    # rx_data = range(10)
    rx_size = list((await axil_master.read(AXIS_FIFO_BASEADDR + 0x1C, 4)).data)
    assert rx_size == [10, 0, 0, 0]

    rx_data = []
    for _ in range(10):
        rx_data += list((await axil_master.read(AXIS_FIFO_BASEADDR + 0x20, 4)).data)

    assert rx_data == rx_data_send

    #

    for i in range(8):
        await axil_master.write(AXIS_FIFO_BASEADDR + 0x10, list(range(i * 4, i * 4 + 4)))
        await axil_master.wait()

    await axil_master.write(AXIS_FIFO_BASEADDR + 0x14, [0x20, 0, 0, 0])

    # tx_size = list((await axil_master.read(AXIS_FIFO_BASEADDR + 0xC, 4)).data)
    # print("tx_size", tx_size)

    tx_data = (await axis_tx.recv()).tdata
    assert bytearray(range(8 * 4)) == tx_data

    dut.areset.value = 0

def test_fw():
    src_path = pathlib.Path(__file__).parent.absolute()

    shutil.rmtree("fw", ignore_errors=True)
    if not os.path.exists("fw/fw.xpr"):
        subprocess.run(["vivado", "-nolog", "-mode", "tcl", "-source", src_path / "fw.tcl"])

    shutil.rmtree("xsim.dir", ignore_errors=True)
    if not os.path.exists("xsim.dir/fw_wrapper/xsimk.so"):
        subprocess.run(["xvlog", "-prj", f"{src_path}/fw/sim_export/xsim/vlog.prj"])
        subprocess.run(["xvhdl", "-prj", f"{src_path}/fw/sim_export/xsim/vhdl.prj"])
        subprocess.run(["./fw/sim_export/xsim/fw_wrapper.sh", "-step", "elaborate"])

    run(module="test_fw", xsim_design="xsim.dir/fw_wrapper/xsimk.so", top_level_lang="verilog")



if __name__ == "__main__":
    test_fw()

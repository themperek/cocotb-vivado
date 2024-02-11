from cocotb_vivado import run
import subprocess
import os
import pathlib

import cocotb
from cocotb.triggers import Timer


class OnFallingSignal:
    def __init__(self, signal):
        self.signal = signal
        self.timer = Timer(100, "ns")

    def __await__(self):
        return self._async_method().__await__()

    async def _async_method(self):
        prev = self.signal.value
        while True:
            await self.timer
            now = self.signal.value
            if prev == 1 and now == 0:
                break
            prev = now


class OnRisingSignal:
    def __init__(self, signal):
        self.signal = signal
        self.timer = Timer(100, "ns")

    def __await__(self):
        return self._async_method().__await__()

    async def _async_method(self):
        prev = self.signal.value
        while True:
            await self.timer
            now = self.signal.value
            if prev == 0 and now == 1:
                break
            prev = now


cocotb.triggers.FallingEdge = OnFallingSignal
cocotb.triggers.RisingEdge = OnRisingSignal

from cocotbext.axi import AxiLiteBus, AxiLiteMaster
from cocotbext.axi import AxiStreamSink, AxiStreamSource, AxiStreamBus

async def clock(signal, timer):
    signal.setimmediatevalue(0)
    while True:
        await timer
        signal.setimmediatevalue(1)
        await timer
        signal.setimmediatevalue(0)


async def reset(signal, timer):
    signal.setimmediatevalue(1)
    await timer
    signal.setimmediatevalue(0)


@cocotb.test()
async def cocotb_fw_test(dut):
    AXIS_FIFO_BASEADDR = 0x1000

    cocotb.start_soon(clock(dut.aclk, Timer(100, "ns")))
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
        d = list(range((i+1)*4))
        rx_data_send += d
        await axis_rx.write(d)
        await axis_rx.wait()

    # rx_data = range(10)
    rx_size = list((await axil_master.read(AXIS_FIFO_BASEADDR + 0x1C, 4)).data)
    assert rx_size == [10,0,0,0]

    rx_data = []
    for _ in range(10):
        rx_data += list((await axil_master.read(AXIS_FIFO_BASEADDR + 0x20, 4)).data)

    assert rx_data == rx_data_send

    #

    for i in range(8):
        await axil_master.write(AXIS_FIFO_BASEADDR + 0x10, list(range(i*4,i*4+4)))
        await axil_master.wait()

    await axil_master.write(AXIS_FIFO_BASEADDR + 0x14, [0x20,0,0,0])

    # tx_size = list((await axil_master.read(AXIS_FIFO_BASEADDR + 0xC, 4)).data)
    # print("tx_size", tx_size)

    tx_data = (await axis_tx.recv()).tdata
    assert bytearray(range(8*4)) == tx_data

    dut.areset.value = 0


def test_fw():
    src_path = pathlib.Path(__file__).parent.absolute()

    if not os.path.exists("xsim.dir/fw_wrapper_behav/xsimk.so"):
        # subprocess.run(["vivado", "-nolog", "-mode", "tcl", "-source", src_path / "fw.tcl"])
        subprocess.run(["xvlog", "-prj", "fw/fw.sim/sim_1/behav/xsim/fw_wrapper_vlog.prj"])
        subprocess.run(["xvhdl", "-prj", "fw/fw.sim/sim_1/behav/xsim/fw_wrapper_vhdl.prj"])
        subprocess.run(
            "xelab -L xil_defaultlib -L axi_bram_ctrl_v4_1_7 -L axi_lite_ipif_v3_0_4 -L lib_pkg_v1_0_2 -L fifo_generator_v13_2_7 -L lib_fifo_v1_0_16 -L axi_fifo_mm_s_v4_2_9 -L blk_mem_gen_v8_4_5 -L xlconstant_v1_1_7 -L lib_cdc_v1_0_2 -L proc_sys_reset_v5_0_13 -L smartconnect_v1_0 -L axi_infrastructure_v1_1_0 -L axi_register_slice_v2_1_27 -L axi_vip_v1_1_13 -L util_vector_logic_v2_0_2 -L uvm -L xilinx_vip -L unisims_ver -L unimacro_ver -L secureip -L xpm --snapshot fw_wrapper_behav xil_defaultlib.fw_wrapper xil_defaultlib.glbl -dll".split()
        )
    run(module="test_fw", xsim_design="xsim.dir/fw_wrapper_behav/xsimk.so", top_level_lang="verilog")


if __name__ == "__main__":
    test_fw()

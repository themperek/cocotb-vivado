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

from cocotbext.axi import AxiLiteBus, AxiLiteMaster, AxiLiteRam


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
async def cocotb_axil_test(dut):
    cocotb.start_soon(clock(dut.clk, Timer(100, "ns")))
    cocotb.start_soon(reset(dut.rst, Timer(500, "ns")))

    axil_master = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "axil"), dut.clk, dut.rst)
    axil_ram = AxiLiteRam(AxiLiteBus.from_prefix(dut, "axil"), dut.clk, dut.rst, size=2**16)

    data_in = list(range(16))
    await axil_master.write(0, data_in)

    data_out = []
    data_out = list((await axil_master.read(12, 4)).data) + data_out
    data_out = list((await axil_master.read(8, 4)).data) + data_out
    data_out = list((await axil_master.read(4, 4)).data) + data_out
    data_out = list((await axil_master.read(0, 4)).data) + data_out

    assert data_in == data_out


def test_axil():
    src_path = pathlib.Path(__file__).parent.absolute()

    if not os.path.exists("xsim.dir/work.test_axil/xsimk.so"):
        subprocess.run(["xvlog", src_path / "test_axil.v"])
        subprocess.run(["xelab", "work.test_axil", "-dll"])

    run(module="test_axil", xsim_design="xsim.dir/work.test_axil/xsimk.so", top_level_lang="verilog")


if __name__ == "__main__":
    test_axil()

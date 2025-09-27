import cocotb_vivado
import subprocess
import os
import pathlib
import shutil

import cocotb
from cocotb.triggers import Timer

import cocotb_vivado.mock_triggers

from cocotbext.axi import AxiLiteBus, AxiLiteMaster, AxiLiteRam


@cocotb.test()
async def cocotb_axil_test(dut):

    clk_period = 200
    clk_timer = Timer(clk_period // 2, "ns")

    cocotb_vivado.mock_triggers.set_timer(clk_timer)

    cocotb.start_soon(cocotb_vivado.mock_triggers.clock(dut.clk))

    dut.rst.value = 1
    await Timer(500, "ns")
    dut.rst.value = 0

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

    shutil.rmtree("xsim.dir", ignore_errors=True)

    if not os.path.exists("xsim.dir/work.test_axil/xsimk.so"):
        subprocess.run(["xvlog", src_path / "test_axil.v"])
        subprocess.run(["xelab", "work.test_axil", "-dll"])

    cocotb_vivado.run(module="test_axil", xsim_design="xsim.dir/work.test_axil/xsimk.so", top_level_lang="verilog")


if __name__ == "__main__":
    test_axil()

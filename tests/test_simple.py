import subprocess
import os
import pathlib
import shutil

import cocotb_vivado
import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def simple_test(dut):
    dut.clk.value = 0
    await Timer(10, units="ns")
    assert dut.out.value == 0
    dut.clk.value = 1
    await Timer(10, units="ns")
    assert dut.out.value == 1


def test_simple():
    src_path = pathlib.Path(__file__).parent.absolute()

    shutil.rmtree("xsim.dir", ignore_errors=True)

    if not os.path.exists("xsim.dir/work.tb/xsimk.so"):
        subprocess.run(["xvlog", src_path / "tb.v"])
        subprocess.run(["xelab", "work.tb", "-dll"])

    cocotb_vivado.run(module="test_simple", xsim_design="xsim.dir/work.tb/xsimk.so", top_level_lang="verilog")


if __name__ == "__main__":
    test_simple()

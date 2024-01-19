from cocotb_vivado import run
import subprocess
import os
import pathlib

from cocotb.triggers import Timer
import cocotb
from cocotb.binary import BinaryValue


async def on_edge(signal, timer):
    prev = signal.value
    while True:
        await timer
        now = signal.value
        if prev != now:
            break
        prev = now


async def clock(signal, timer):
    signal.setimmediatevalue(0)
    while True:
        await timer
        signal.setimmediatevalue(1)
        await timer
        signal.setimmediatevalue(0)


@cocotb.test()
async def cocotb_tb_test(dut):
    cocotb.start_soon(clock(dut.clk, Timer(5, "ns")))

    await Timer(10, "ns")

    for _ in range(10):
        await on_edge(dut.out, Timer(1, "ns"))
        cocotb.log.info(f"out={dut.out.value}")

    await Timer(100, "ns")

    for v in ["1", "0", "x", "z", "X", "Z", "0"]:
        dut.vec_in.setimmediatevalue(BinaryValue(v * 100))
        await Timer(10, "ns")
        vec_out = dut.vec_out.value
        cocotb.log.info(f"dut.vec_out {vec_out}")
        assert (v * 100).lower() == vec_out.binstr


def test_tb():
    src_path = pathlib.Path(__file__).parent.absolute()

    if not os.path.exists("xsim.dir/work.tb/xsimk.so"):
        subprocess.run(["xvlog", src_path / "tb.v"])
        subprocess.run(["xelab", "work.tb", "-dll"])

    run(module="test_tb", xsim_design="xsim.dir/work.tb/xsimk.so", top_level_lang="verilog")


if __name__ == "__main__":
    test_tb()

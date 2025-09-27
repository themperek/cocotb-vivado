import subprocess
import os
import pathlib
from cocotb_vivado import xsi
import random
import shutil


def test_xsi():
    src_path = pathlib.Path(__file__).parent.absolute()

    shutil.rmtree("xsim.dir", ignore_errors=True)
    if not os.path.exists("xsim.dir/work.tb/xsimk.so"):
        subprocess.run(["xvlog", src_path / "tb.v"])
        subprocess.run(["xelab", "work.tb", "-dll"])

    dut = xsi.XSI("xsim.dir/work.tb/xsimk.so")

    port_no = dut.ports_number()
    assert port_no == 4
    clk_no = dut.get_port_number("clk")
    out_no = dut.get_port_number("out")
    vec_in_no = dut.get_port_number("vec_in")
    vec_out_no = dut.get_port_number("vec_out")

    dut.put_value(clk_no, "0")
    dut.run(10)
    assert dut.get_value(out_no) == "0"
    dut.put_value(clk_no, "1")
    dut.run(10)
    assert dut.get_value(out_no) == "1"
    dut.put_value(clk_no, "0")
    dut.run(10)
    assert dut.get_value(out_no) == "0"

    time = dut.get_time()
    assert time == 30

    rand_bin_str = "".join(random.choice("01") for _ in range(100))
    dut.put_value(vec_in_no, "01" * 50)
    dut.run(5)
    assert dut.get_value(vec_out_no) == "01" * 50

    dut.put_value(vec_in_no, rand_bin_str)
    dut.run(5)
    assert dut.get_value(vec_out_no) == rand_bin_str

    time = dut.get_time()
    assert time == 40


if __name__ == "__main__":
    test_xsi()

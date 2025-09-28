# cocotb-vivado
[![PyPI version](https://badge.fury.io/py/cocotb-vivado.svg)](https://pypi.org/project/cocotb-vivado/)

A limited Python/[cocotb](https://github.com/cocotb/cocotb/) interface to the [Xilinx Vivado Simulator](https://docs.xilinx.com/v/u/en-US/dh0010-vivado-simulation-hub) simulator. 
Based on [cocotb-stub-sim](https://github.com/fvutils/cocotb-stub-sim).

---

## 🚧 Project Status
**Proof of Concept** – expect limitations (see below).  

- Only top-level ports are accessible (simulator limitation).  
- Only the `Timer` trigger is supported (simulator limitation).  
- Setting signal values is immediate (`setimmediatevalue` behavior).  
- Only **Verilog top-levels** are supported (VHDL support planned).  
- Direct access to the **XSI interface** is available.  

---

## Installation

```bash
pip install cocotb-vivado==0.0.3 (for VIVADO <= 2022.2)
pip install cocotb-vivado (for VIVADO >= 2023.1)
```

## Quickstart

```python
import subprocess

import cocotb_vivado
import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def simple_test(dut):
    dut.clk.value = 0
    await Timer(10, units="ns")
    dut.clk.value = 1
    await Timer(10, units="ns")
    assert dut.out.value == 1

def test_simple():
    subprocess.run(["xvlog", "tb.v"])
    subprocess.run(["xelab", "work.tb", "-dll"])

    cocotb_vivado.run(module="test_simple", xsim_design="xsim.dir/work.tb/xsimk.so", top_level_lang="verilog")
```

See `testes/test_simple.py` for full example.

## Usage

See the `tests` folder for examples.

```bash
source ../Vivado/202X.X/settings64.sh
export LD_LIBRARY_PATH=$XILINX_VIVADO/lib/lnx64.o
pytest -s
```

Extra feature: One does not need to recompile the project when running/changing tests .

## Direct `XSI` interface

You can use `XSI` interface directly see `tests/test_xsi.py` for an example.

## cocotb extensions

In order to use cocotb extension like [cocotbext-axi](https://github.com/alexforencich/cocotbext-axi)  one needs to mock the triggers (`XSI` limitations) by creating global clock timer and synchronizes all trigger events to it. See `tests/test_axil.py` for an example.

## Full Vivado design simulation

In order order to simulate full design you need create design, `export_simulation` files compile, elaborate and run. See `tests/fw.tcl` and `tests/test_fw.tcl` for an example.

## Dump waveforms

You can dump `vcd` file with verilog syntax in your testbench:

```verilog
initial begin
    $dumpfile("test.vcd");
    $dumpvars(0);
end
```

### Acknowledgment

We'd like to thank our employer, [Dectris](https://dectris.com/) for supporting this work.

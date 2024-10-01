# cocotb-vivado
[![PyPI version](https://badge.fury.io/py/cocotb-vivado.svg)](https://pypi.org/project/cocotb-vivado/)

A limited Python/[cocotb](https://github.com/cocotb/cocotb/) interface to the [Xilinx Vivado Simulator](https://docs.xilinx.com/v/u/en-US/dh0010-vivado-simulation-hub) simulator. 
Based on [cocotb-stub-sim](https://github.com/fvutils/cocotb-stub-sim).

## The project is at a proof of concept stage

- Only top-level ports are accessible (simulator limitation).
- It supports the `Timer` trigger (simulator limitation).
- Setting signal values is immediate, as one would use `setimmediatevalue` (simulator limitation). 
- Only `Verilog` at the top level is supported (to do).

## Installation

```cmd
pip install cocotb-vivado==0.0.3 (for VIVADO <= 2022.2)
pip install cocotb-vivado (for VIVADO >= 2023.1)
```

## Usage

See the `tests` folder for examples.

```cmd
source ../Vivado/202X.X/settings64.sh
export LD_LIBRARY_PATH=$XILINX_VIVADO/lib/lnx64.o
pytest -s
```

Extra future: One does not need to recompile the project when running/changing tests .

### Acknowledgment

We'd like to thank our employer, [Dectris](https://dectris.com/) for supporting this work.

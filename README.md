# cocotb-vivado

A very limited [cocotb](https://github.com/cocotb/cocotb/) interface to the [Xilinx Vivado Simulator](https://docs.xilinx.com/v/u/en-US/dh0010-vivado-simulation-hub) simulator. 
Based on [cocotb-stub-sim](https://github.com/fvutils/cocotb-stub-sim).

## The project is at a proof of concept stage

- Only top-level ports are accessible.
- It supports the `Timer` trigger.
- Setting signal values is immediate, as one would use `setimmediatevalue`. 
- Only `Verilog` at the top level is supported (to do).

## Install 

```cmd
pip install cocotb-vivado
```

## Usage

See the `tests` folder for examples.

```cmd
source ../Vivado/202X.X/settings64.sh
export LD_LIBRARY_PATH=$XILINX_VIVADO/lib/lnx64.o
pytest -s
```

### Acknowledgment

We'd like to thank our employer, [Dectris](https://dectris.com/) for supporting this work.

# cocotb-xsi

A very limited [cocotb](https://github.com/cocotb/cocotb/) interface to the [Xilinx XSIM](https://docs.xilinx.com/r/en-US/ug835-vivado-tcl-commands/xsim) simulator. 
Based on [cocotb-stub-sim](https://github.com/fvutils/cocotb-stub-sim).

## The project is at a proof of concept stage

- Only top-level ports are accessible.
- It supports the `Timer` trigger.
- Setting signal values is immediate, as one would use `setimmediatevalue`. 
- Only `Verilog` at the top level is supported (to do).

## Usage

See the `tests` folder for examples.

```cmd
source ../Vivado/202X.X/settings64.sh
cd tests
export LD_LIBRARY_PATH=$XILINX_VIVADO/lib/lnx64.o
pytest -s
```

### Acknowledgment

We'd like to thank our employer, [Dectris](https://dectris.com/) for supporting this work.

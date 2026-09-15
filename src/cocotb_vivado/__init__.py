"""cocotb-vivado package init.

Importing this package has no side effects. Simulations run in a
``python -m cocotb_vivado`` subprocess (see :mod:`cocotb_vivado.__main__`),
which installs the XSI GPI shim — replacing ``cocotb.simulator`` with the
in-process XSI stub — before it imports cocotb. A testbench's own import
order therefore never matters, and importing ``cocotb_vivado`` in a
process that does not simulate (e.g. the pytest driver) leaves cocotb
untouched.
"""

__version__ = "0.0.6"

"""cocotb-vivado package init.

Importing this package replaces ``cocotb.simulator`` in ``sys.modules``
with the in-process XSI stub — the GPI shim cocotb talks to.

**Import order is not a user concern.** Simulations run in a
``python -m cocotb_vivado`` subprocess (see :mod:`cocotb_vivado.__main__`),
which installs the stub before it imports cocotb. cocotb loads the test
modules afterwards, so a testbench's own import order is irrelevant —
importing ``cocotb`` before ``cocotb_vivado`` is fine.

With the GPI shim in place, cocotb's native ``Clock`` and
``RisingEdge`` / ``FallingEdge`` / ``Edge`` triggers work directly
against the in-process simulator.
"""

__version__ = "0.0.6"

import importlib
import sys

# Replace cocotb.simulator BEFORE cocotb is imported so the GPI shim is
# in place when cocotb wires up its callbacks.
sys.modules["cocotb.simulator"] = importlib.import_module(
    "cocotb_vivado.stub.simulator"
)

import cocotb  # noqa: E402

# cocotb 2.x caches ``cocotb.simulator`` as an attribute at module
# load; force the substitution explicitly so the C-extension simulator
# isn't bound after our sys.modules patch.
cocotb.simulator = sys.modules["cocotb.simulator"]

"""cocotb-vivado package init.

Importing this package has one global side effect: ``cocotb.simulator``
in ``sys.modules`` is replaced with the in-process XSI stub. This is
how the runner injects a GPI shim that cocotb can talk to.

Consequence — **import order matters**. Always import ``cocotb_vivado``
(or any ``cocotb_vivado.*`` submodule) before ``cocotb``. Importing
``cocotb`` first caches the real C-extension simulator and the patch
silently becomes a no-op:

.. code-block:: python

    # Correct
    import cocotb_vivado
    from cocotb_vivado.runner import get_runner
    import cocotb

    # Broken — cocotb caches the real simulator before our patch lands
    import cocotb
    import cocotb_vivado

With the GPI shim in place, cocotb's native ``Clock`` and
``RisingEdge`` / ``FallingEdge`` / ``Edge`` triggers work directly
against the in-process simulator.
"""

__version__ = "0.0.6"

import importlib
import os
import sys

# Replace cocotb.simulator BEFORE cocotb is imported so the GPI shim is
# in place when cocotb wires up its callbacks.
sys.modules["cocotb.simulator"] = importlib.import_module(
    "cocotb_vivado.stub.simulator"
)

import cocotb  # noqa: E402

from .stub.manager import Mgr  # noqa: E402


def run(module, xsim_design, top_level_lang):
    """Legacy direct-launch entry; superseded by ``cocotb_vivado.runner.Vivado``."""
    if top_level_lang != "verilog":
        raise Exception("Only verilog supported as top level languge")

    os.environ["MODULE"] = module

    mgr = Mgr.init(xsim_design)

    cocotb._initialise_testbench([])

    mgr.run()

    mgr.close()

    if cocotb.regression_manager.failures:
        sys.exit(1)

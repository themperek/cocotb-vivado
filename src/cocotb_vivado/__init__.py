import sys
import importlib
import traceback
import os

sys.modules["cocotb.simulator"] = importlib.import_module("cocotb_vivado.stub.simulator")

import cocotb
from .stub.mgr import Mgr


def run(module, xsim_design, top_level_lang):
    if top_level_lang != "verilog":
        raise Exception("Only verilog supported as top level languge")

    os.environ["MODULE"] = module

    mgr = Mgr.init(xsim_design)

    cocotb._initialise_testbench([])

    mgr.run()

    mgr.close()

    if cocotb.regression_manager.failures:
        exit(1)

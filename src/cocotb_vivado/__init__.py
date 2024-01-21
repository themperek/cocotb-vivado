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

    try:
        cocotb._initialise_testbench([])
    except Exception as e:
        print("Exception: %s" % str(e), flush=True)
        traceback.print_exc()

    mgr.run()

    mgr.close()

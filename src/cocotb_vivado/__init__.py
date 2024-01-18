import sys
import importlib
import traceback
import os

sys.modules["cocotb.simulator"] = importlib.import_module("cocotb_vivado.stub.simulator")

from cocotb import *


def run(module, xsim_design, top_level_lang):
    if top_level_lang != "verilog":
        raise Exception("Only verilog supported as top level languge")

    os.environ["COCOTB_VIVADO_DESIGN"] = xsim_design
    os.environ["MODULE"] = module

    import cocotb
    from .stub.mgr import Mgr

    try:
        cocotb._initialise_testbench([])
    except Exception as e:
        print("Exception: %s" % str(e), flush=True)
        traceback.print_exc()

    cocotb.log.info(f"Loadin design {xsim_design}")

    mgr = Mgr.inst()

    mgr.run()

    mgr.close()

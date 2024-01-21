import traceback

from .mgr import Mgr

# ********************************************************************
# * These constants are used by cocotb 'main'
# ********************************************************************
MODULE = 0
STRUCTURE = 1
REG = 1
NET = 3
NETARRAY = 4
REAL = 5
INTEGER = 6
ENUM = 8
STRING = 9
GENARRAY = 10


def log_msg(*args, **kwargs):
    raise Exception("cocotb-xsim: Calling cocotb log_msg is not supported")


def get_root_handle(root_name):
    return Mgr.inst().get_root_handle()


def register_timed_callback(t, cb, ud):
    # print("sim:register_timed_callback", t, cb, ud)
    try:
        return Mgr.inst().register_timed_callback(t, cb, ud)
    except Exception as e:
        print("Exception while registering timed callback: %s" % str(e))
        traceback.print_exc()


def register_value_change_callback(*args, **kwargs):
    raise Exception("cocotb-xsim: Setting cocotb value-change callbacks is not supported")


def register_readonly_callback(*args, **kwargs):
    raise Exception("cocotb-xsim: Setting cocotb readonly callbacks is not supported")


def register_nextstep_callback(*args, **kwargs):
    raise Exception("cocotb-xsim: Setting cocotb nextstep callbacks is not supported")


def register_rwsynch_callback(cb, ud):
    #
    # !!! SUPER HACK !!!
    # need propoer delta cycle executions
    # add 1 time step for values to be set
    #
    return Mgr.inst().register_timed_callback(1, cb, ud)


def stop_simulator():
    Mgr.inst().stop_simulator()


def log_level(level):
    pass


def is_running(*args, **kwargs):
    raise Exception("cocotb-xsim: Calling cocotb is_running is not supported")


def get_sim_time():
    return Mgr.inst().get_sim_time()


def get_precision():
    return Mgr.inst().get_precision()


def get_simulator_product():
    return f"cocotb-vivado-sim with design {Mgr.inst().get_design_name()}"


def get_simulator_version():
    return "0.0.1"


# This is needed for XsimRootHandle.iterate
OBJECTS = []

# Copyright cocotb-vivado contributors
# Copyright 2026 Kiran Vuksanaj
# Licensed under the Apache License 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Derived from vicoco's gpi_emulation
# (https://github.com/kiran-vuksanaj/vicoco); adapted for cocotb 1.x/2.x.

"""``cocotb.simulator`` replacement that talks to the XSI manager.

Forwards every callback registration and handle query to
:class:`cocotb_vivado.stub.manager.Mgr`, and provides the surface
cocotb 2.x's GPI shim expects at module load:

* Integer type / edge / iterator tags re-exported from
  ``cocotb_vivado._gpi_enums``.
* ``gpi_sim_hdl`` / ``gpi_cb_hdl`` / ``gpi_iterator_hdl`` ABCs (our
  concrete handle classes satisfy these structurally).
* ``clock_create`` returning ``None`` so cocotb's ``Clock`` uses its
  Python-coroutine implementation; XSI has no native GpiClock path.
* ``package_iterate`` / ``set_sim_event_callback`` /
  ``initialize_logger`` / ``set_gpi_log_level`` /
  ``gpi_has_registered_impl`` stubs.
"""

import abc
import traceback

from cocotb_vivado._gpi_enums import (  # noqa: F401
    DRIVERS,
    ENUM,
    FALLING,
    GENARRAY,
    INTEGER,
    LOADS,
    LOGIC,
    LOGIC_ARRAY,
    MEMORY,
    MODULE,
    NETARRAY,
    PACKAGE,
    PACKED_STRUCTURE,
    RANGE_DOWN,
    RANGE_NO_DIR,
    RANGE_UP,
    REAL,
    RISING,
    STRING,
    STRUCTURE,
    UNKNOWN,
    VALUE_CHANGE,
)

from .manager import Mgr

# Legacy aliases retained for code paths still expecting cocotb 1.x
# type-tag names.
REG = LOGIC_ARRAY
NET = LOGIC_ARRAY

# cocotb 2.x reads ``simulator.OBJECTS`` during iteration setup.
OBJECTS = []


# cocotb 2.x imports these ABCs from cocotb.simulator at module load.
# Our concrete handle classes (in ``stub/handles.py``) satisfy the
# protocol structurally; the ABCs here just unblock the imports.


class gpi_cb_hdl(abc.ABC):
    def deregister(self) -> None: ...


class gpi_iterator_hdl(abc.ABC):
    def __iter__(self) -> "gpi_iterator_hdl": ...

    def __next__(self) -> "gpi_sim_hdl": ...


class gpi_sim_hdl(abc.ABC):
    def get_const(self) -> bool: ...

    def get_definition_file(self) -> str: ...

    def get_definition_name(self) -> str: ...

    def get_handle_by_name(
        self, name: str, discovery_method: int = 1
    ) -> "gpi_sim_hdl | None": ...

    def get_indexable(self) -> bool: ...

    def get_name_string(self) -> str: ...

    def get_num_elems(self) -> int: ...

    def get_range(self) -> tuple: ...

    def get_signal_val_binstr(self) -> str: ...

    def get_signal_val_long(self) -> int: ...

    def get_signal_val_real(self) -> float: ...

    def get_signal_val_str(self) -> bytes: ...

    def get_type(self) -> int: ...

    def get_type_string(self) -> str: ...

    def iterate(self, mode: int) -> gpi_iterator_hdl: ...

    def set_signal_val_binstr(self, action: int, value: str) -> None: ...

    def set_signal_val_int(self, action: int, value: int) -> None: ...

    def set_signal_val_real(self, action: int, value: float) -> None: ...

    def set_signal_val_str(self, action: int, value: bytes) -> None: ...


def get_root_handle(root_name):
    return Mgr.inst().get_root_handle()


def register_timed_callback(t, cb, ud):
    try:
        return Mgr.inst().register_timed_callback(t, cb, ud)
    except Exception as e:
        print(f"Exception while registering timed callback: {e!s}")
        traceback.print_exc()


def register_value_change_callback(handle, callback, edge, ud):
    return Mgr.inst().register_value_change_callback(handle, callback, edge, ud)


def register_readonly_callback(cb, ud):
    return Mgr.inst().register_readonly_callback(cb, ud)


def register_nextstep_callback(cb, ud):
    return Mgr.inst().register_timed_callback(1, cb, ud)


def register_rwsynch_callback(cb, ud):
    return Mgr.inst().register_readwrite_callback(cb, ud)


def stop_simulator():
    Mgr.inst().stop_simulator()


def log_msg(*args, **kwargs):
    raise Exception("cocotb-xsim: Calling cocotb log_msg is not supported")


def log_level(level):
    pass


def set_gpi_log_level(level):
    pass


def is_running(*args, **kwargs):
    raise Exception("cocotb-xsim: Calling cocotb is_running is not supported")


def get_sim_time():
    time = Mgr.inst().get_sim_time()
    # cocotb expects a (upper32, lower32) tuple.
    return (time >> 32, time & 0xFFFFFFFF)


def get_precision():
    # cocotb expects an int log10 of the timestep in seconds. Delegate to
    # the kernel precision (xsiTimePrecisionKernel) so it stays consistent
    # with get_sim_time's tick count, whatever the design elaborated at.
    return Mgr.inst().get_precision()


def get_simulator_product():
    return f"cocotb-vivado-sim with design {Mgr.inst().get_design_name()}"


def get_simulator_version():
    return "0.0.1"


def package_iterate():
    """Empty iterator — XSim exposes no VHDL package introspection."""
    return iter([])


def set_sim_event_callback(cb):
    """No-op: XSim has no sim_event hooks we forward."""
    pass


def initialize_logger(log_func, get_logger):
    """No-op: cocotb routes its own logs; we don't intercept."""
    pass


def gpi_has_registered_impl():
    """Tell cocotb's GPI bootstrap there's a registered backend."""
    return 1


def clock_create(hdl):
    """No GPI-level clock; cocotb falls back to its Python clock impl."""
    return None


class GpiClock:
    """Stub — real GpiClock is C-level; we don't provide one."""

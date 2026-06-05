# Copyright cocotb-vivado contributors
# Copyright 2026 Kiran Vuksanaj
# Licensed under the Apache License 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Derived from vicoco's vivado_handles
# (https://github.com/kiran-vuksanaj/vicoco); adapted for cocotb 2.x.

"""Port handles and callback closures for the XSI manager.

:class:`XsiPortHandle` exposes a single XSI top-level port as a cocotb
handle, keyed by the numeric ``port_id`` from xsi's native API.
:class:`XsimRootHandle` wraps the design root for cocotb's name-based
lookup.

Type tags come from :mod:`cocotb_vivado._gpi_enums`, matching cocotb
2.x's GPI shim expectations. Single-bit ports report ``LOGIC``;
wider ports ``LOGIC_ARRAY``; the top-level scope reports ``MODULE``.

:class:`ValueChangeCbClosure` caches the last observed signal value
and fires its user callback on the next read whose value satisfies
the requested edge (rising / falling / any). The manager invokes
``change_condition_satisfied`` once per delta-cycle attempt so the
``previous_value`` cache stays consistent across the snapshot loop.
"""

import abc
from collections.abc import Callable
from typing import Any

from cocotb_vivado import _gpi_enums as _enums


class XsimRootHandle:
    def __init__(self, mgr):
        self.mgr = mgr

    def get_const(self):
        return True

    def get_type(self):
        return _enums.MODULE

    def get_name_string(self):
        return "top"

    def get_type_string(self):
        return "MODULE"

    def get_definition_name(self):
        return ""

    def get_definition_file(self):
        return ""

    def iterate(self, nothing):
        for name in self.mgr.ports:
            yield self.mgr.ports[name]

    def get_handle_by_name(self, name, discovery_method=1):
        if name not in self.mgr.ports:
            return
        return self.mgr.ports[name]


class XsiPortHandle:
    def __init__(self, mgr, name, port_id, size):
        self.name = name
        self.port_id = port_id
        self.size = size
        self.mgr = mgr

        # cocotb 2.x distinguishes single-bit (LOGIC) from multi-bit
        # (LOGIC_ARRAY) ports; cocotb 1.x's REG covered both. Tag once
        # at handle creation so get_type() lookups are constant-time.
        if size == 1:
            self.type_int = _enums.LOGIC
            self.type_str = "LOGIC"
        else:
            self.type_int = _enums.LOGIC_ARRAY
            self.type_str = "LOGIC_ARRAY"

    def get_const(self):
        return False

    def get_type(self):
        return self.type_int

    def get_name_string(self):
        return self.name

    def get_type_string(self):
        return self.type_str

    def get_definition_name(self):
        return ""

    def get_definition_file(self):
        return ""

    def get_num_elems(self):
        return self.size

    def get_range(self):
        return (self.size - 1, 0)

    def set_signal_val_int(self, action, value):
        str_value = f"{value:0{self.size}b}"
        self.set_signal_val_binstr(action, str_value)

    def set_signal_val_binstr(self, action, value):
        self.mgr.xsi.put_value(self.port_id, value)

    def get_signal_val_binstr(self):
        return self.mgr.xsi.get_value(self.port_id)

    def get_signal_val_int(self):
        value = self.get_signal_val_binstr()
        return int(value, 2)


class CbClosure(abc.ABC):
    def __init__(self) -> None:
        self.cb: Callable[[Any], None] | None = None
        self.ud: Any = None

    def __call__(self):
        if self.cb is not None:
            self.cb(self.ud)

    def deregister(self):
        self.cb = None


class TimedCbClosure(CbClosure):
    def __init__(self, time_off, cb, ud):
        self.time_off = time_off
        self.cb = cb
        self.ud = ud
        self.cb_id = 1


class ValueChangeCbClosure(CbClosure):
    def __init__(self, handle, edge, cb, ud):
        self.handle = handle
        self.cb = cb
        self.ud = ud
        self.edge = edge

        try:
            self.previous_value = handle.get_signal_val_int()
        except ValueError:
            self.previous_value = None

    def change_condition_satisfied(self):
        try:
            current_value = self.handle.get_signal_val_int()
        except ValueError:
            current_value = None

        if self.edge == _enums.RISING:
            out = (current_value == 1) and (
                self.previous_value == 0 or self.previous_value is None
            )
        elif self.edge == _enums.FALLING:
            out = (current_value == 0) and (
                self.previous_value == 1 or self.previous_value is None
            )
        else:
            # VALUE_CHANGE — any genuine transition.
            out = (
                current_value is not None
                and self.previous_value is not None
                and current_value != self.previous_value
            )

        self.previous_value = current_value
        return out


class ReadWriteCbClosure(CbClosure):
    def __init__(self, callback, trigger):
        self.cb = callback
        self.ud = trigger


class ReadOnlyCbClosure(CbClosure):
    def __init__(self, callback, trigger):
        self.cb = callback
        self.ud = trigger


__all__ = [
    "CbClosure",
    "ReadOnlyCbClosure",
    "ReadWriteCbClosure",
    "TimedCbClosure",
    "ValueChangeCbClosure",
    "XsiPortHandle",
    "XsimRootHandle",
]

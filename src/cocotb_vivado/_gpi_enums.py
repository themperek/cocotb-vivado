# Copyright cocotb-vivado contributors
# Licensed under the Apache License 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""GPI type / edge / discovery constants exported as ``cocotb.simulator``.

cocotb's GPI shim layer expects a fixed enumeration of integer constants
for handle types, value-change edges, and iterator modes. The exact
values are an internal, self-consistent enumeration: cocotb reads them
back from this shim (e.g. ``cocotb.handle`` builds its type map from
``cocotb.simulator.*``) and our handle layer reports the same values, so
they need only be distinct and cover every name cocotb references — they
need not match cocotb's own C-extension values.
"""

DRIVERS: int = 0
ENUM: int = 1
GENARRAY: int = 2
INTEGER: int = 3
LOADS: int = 4
LOGIC: int = 5
LOGIC_ARRAY: int = 6
MEMORY: int = 7
MODULE: int = 8
NETARRAY: int = 9
OBJECTS: int = 10
PACKAGE: int = 11
REAL: int = 12
STRING: int = 13
STRUCTURE: int = 14
PACKED_STRUCTURE: int = 15
UNKNOWN: int = 16
RISING: int = 17
FALLING: int = 18
VALUE_CHANGE: int = 19
RANGE_UP: int = 20
RANGE_DOWN: int = 21
RANGE_NO_DIR: int = 22
PACKED: int = 23
FIXED_STRING: int = 24

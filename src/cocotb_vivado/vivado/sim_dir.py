# Copyright cocotb-vivado contributors
# Licensed under the Apache License 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Parsing of Vivado-emitted simulation script directories.

Vivado's ``launch_simulation -scripts_only`` (project / BD designs) and
``export_ip_user_files`` (standalone IP) both emit the same essential
artifacts under ``xsim/``: ``*.prj`` files consumed by ``xvlog -prj`` /
``xvhdl -prj``, and a ``*.sh`` script whose ``xelab`` invocation lists
the precompiled libraries (``-L``) and any extra elab modules (``glbl``)
the design needs. :class:`SimDirInfo` is the distilled view;
:func:`read_sim_dir` is the parser. The ``.prj`` files are
self-contained (absolute paths, ``--include`` directives inline), so
no separate CSV index is consulted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PathLike = Path | str

# Single ``-L <name>`` pair on the xelab command line. Library names are
# bare identifiers per Xilinx convention.
_XELAB_LIB_RE = re.compile(r"-L\s+([A-Za-z_][A-Za-z0-9_]*)")

# ``<library>.glbl`` references on the xelab command line — Vivado lists
# them as extra top units after ``--snapshot <name>``.
_XELAB_GLBL_RE = re.compile(r"\b([A-Za-z_]\w*\.glbl)\b")


@dataclass
class SimDirInfo:
    """Distilled view of one Vivado-emitted ``xsim/`` script directory.

    Consumed by :class:`cocotb_vivado.runner.Vivado` to populate the
    elaboration library set, extra-top module list, and
    ``xvlog -prj`` / ``xvhdl -prj`` compile commands.
    """

    sim_scripts: Path
    libraries: set = field(default_factory=set)
    glbl_modules: list = field(default_factory=list)
    vhdl_prj: Path | None = None
    vlog_prj: Path | None = None


def _classify_prj(prj: Path) -> str | None:
    """Return ``"vlog"`` or ``"vhdl"`` based on the .prj's first directive."""
    for line in prj.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("verilog "):
            return "vlog"
        if stripped.startswith("vhdl "):
            return "vhdl"
        return None
    return None


def _parse_elab_script(xsim_root: Path) -> tuple[set, list]:
    """Extract ``-L`` libraries and ``<lib>.glbl`` modules from xelab scripts."""
    libs: set = set()
    glbls: list = []
    for script in xsim_root.glob("*.sh"):
        text = script.read_text(encoding="utf-8")
        if "xelab " not in text:
            continue
        libs.update(_XELAB_LIB_RE.findall(text))
        for module in _XELAB_GLBL_RE.findall(text):
            if module not in glbls:
                glbls.append(module)
    return libs, glbls


def read_sim_dir(sim_scripts: PathLike) -> SimDirInfo:
    """Distill a Vivado-emitted sim-scripts directory into :class:`SimDirInfo`.

    Discovers ``*.prj`` files by content sniff (first non-comment line
    starts with ``verilog`` → vlog .prj, ``vhdl`` → vhdl .prj) and the
    sibling ``*.sh`` xelab script for the library / glbl list.

    Args:
        sim_scripts: Either the ``xsim/`` directory itself, or a parent
            that contains an ``xsim/`` subdir (matches both Vivado layouts:
            project-level ``<xpr>.sim/sim_1/behav/`` and per-IP
            ``.ip_user_files/sim_scripts/<ip>/``).

    Returns:
        :class:`SimDirInfo` populated from whichever artifacts exist.
        Missing .prj files leave the corresponding field ``None``.
    """
    base = Path(sim_scripts)
    xsim_root = base / "xsim" if (base / "xsim").is_dir() else base

    vlog_prj: Path | None = None
    vhdl_prj: Path | None = None
    for prj in sorted(xsim_root.glob("*.prj")):
        kind = _classify_prj(prj)
        if kind == "vlog" and vlog_prj is None:
            vlog_prj = prj
        elif kind == "vhdl" and vhdl_prj is None:
            vhdl_prj = prj

    libraries, glbl_modules = _parse_elab_script(xsim_root)

    return SimDirInfo(
        sim_scripts=base,
        libraries=libraries,
        glbl_modules=glbl_modules,
        vhdl_prj=vhdl_prj,
        vlog_prj=vlog_prj,
    )

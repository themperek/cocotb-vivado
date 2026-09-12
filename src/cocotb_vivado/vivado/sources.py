# Copyright cocotb-vivado contributors
# Copyright 2026 Kiran Vuksanaj
# Licensed under the Apache License 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# The IP/BD/project source preparation is derived from vicoco's Vivado
# runner (https://github.com/kiran-vuksanaj/vicoco).

"""Vivado-managed source classes for use in ``runner.build(sources=[...])``.

Four concrete subclasses of :class:`VivadoSource`, one per Vivado input
format:

* :class:`VivadoIp` — ``.xci`` IP sources, runs
  ``export_ip_user_files``.
* :class:`VivadoBd` — ``.bd`` block designs, runs ``make_wrapper`` +
  ``launch_simulation -scripts_only`` to flatten interface ports.
* :class:`VivadoProject` — ``.xpr`` project sources, runs
  ``launch_simulation -scripts_only -absolute_path``.
* :class:`VivadoExportedSim` — user-supplied TCL that produces a
  ``sim_export``-style directory itself.
"""

from __future__ import annotations

import hashlib
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from cocotb.runner import outdated

from ._tcl import EXPORT_SCRIPTS_TCL, ensure_xsim_ini, execute_tcl
from .part import _resolve_part_num
from .sim_dir import SimDirInfo, read_sim_dir

PathLike = Path | str


def _hash_file(path: Path) -> str:
    """SHA-256 hex digest of file contents. Empty string if missing."""
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_dir(root: Path) -> str:
    """SHA-256 of a sorted ``(relpath, sha256)`` manifest under ``root``."""
    if not root.is_dir():
        return ""
    items: list = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            items.append(f"{p.relative_to(root)}\0{_hash_file(p)}")
    return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()


class VivadoSource(ABC):
    """Abstract Vivado-managed source for :meth:`Vivado.build`.

    Subclasses know how to produce a Vivado simulation-scripts
    directory (with ``*.prj`` files and a sibling xelab ``*.sh``
    script) and return a :class:`SimDirInfo` view of it. Caching
    via mtime checks is the subclass's responsibility; the runner's
    Tier 1 cache consults :meth:`fingerprint` to detect input
    changes that mtime can't see (content-vs-mtime divergence).
    """

    @abstractmethod
    def prepare(
        self, build_dir: Path, hdl_library: str, force: bool = False
    ) -> SimDirInfo:
        """(Re)generate the simulation scripts and return their distilled view.

        ``force=True`` bypasses the subclass's mtime check, used by the
        runner on a Tier 1 cache miss to ensure Vivado re-runs even
        when the inputs' content changed without their mtimes changing
        (e.g., post ``git checkout``).
        """

    @abstractmethod
    def fingerprint(self) -> dict:
        """JSON-serializable identity for the runner's Tier 1 cache signature.

        Captures the source's *inputs* (constructor kwargs + content
        hashes of file inputs) — not its derived outputs. When
        ``builder_tcl`` is set, the TCL is the canonical input; the
        artifacts it produces are derived and not hashed here.
        """


class VivadoIp(VivadoSource):
    """One or more ``.xci`` IP sources.

    On :meth:`prepare`, runs ``vivado -mode batch`` with
    ``set_part {part_num}; add_files -norecurse {paths}; export_ip_user_files``
    when an IP source is newer than its prior
    ``sim_scripts/<ip>/xsim/README.txt`` (mtime check). Copies any
    emitted ``mem_init_files/*`` into the build directory so downstream
    xvlog/xvhdl invocations find them.

    Block designs (``.bd``) are handled by :class:`VivadoBd`, not here:
    they need an RTL wrapper to flatten interface ports, which
    ``export_ip_user_files`` does not produce.

    Args:
        *paths: ``.xci`` source paths. Relative paths resolve under the
            build directory — useful when the XCI is itself produced by
            ``builder_tcl``.
        builder_tcl: Optional TCL that produces the XCI files on its
            first run (e.g. ``create_ip ... -module_name X`` +
            ``generate_target simulation``). Re-run when the TCL is
            newer than any XCI it produces, or when an XCI is missing.
            Lets the test fixture stay Vivado-version-agnostic at the
            cost of one extra ``vivado -mode batch`` on first build.
        part_num: Xilinx part name (e.g. ``"xczu7eg-ffvc1156-2-e"``).
            Falls back to ``COCOTB_DEFAULT_PART_NUM`` env. Required.
            See :func:`discover_default_part` for an opt-in helper.
    """

    def __init__(
        self,
        *paths: PathLike,
        builder_tcl: PathLike | None = None,
        part_num: str | None = None,
    ) -> None:
        if not paths:
            raise ValueError("VivadoIp requires at least one .xci path")
        self.paths: list[Path] = [Path(p) for p in paths]
        for p in self.paths:
            if p.suffix != ".xci":
                raise ValueError(
                    f"VivadoIp expects .xci sources, got {p} "
                    "(use VivadoBd for .bd block designs)"
                )
        self.builder_tcl: Path | None = (
            Path(builder_tcl) if builder_tcl is not None else None
        )
        self._part_num = part_num

    def fingerprint(self) -> dict:
        # builder_tcl, when set, is the canonical input; the XCIs it
        # produces are derived. Hash the TCL only; treat XCI paths as
        # identifiers (path strings). Without builder_tcl, the XCIs
        # are the canonical inputs and must be hashed.
        paths_field: object
        if self.builder_tcl is not None:
            paths_field = [str(p) for p in self.paths]
            builder = {
                "path": str(self.builder_tcl),
                "sha256": _hash_file(self.builder_tcl),
            }
        else:
            paths_field = [
                {"path": str(p), "sha256": _hash_file(p)} for p in self.paths
            ]
            builder = None
        return {
            "kind": "VivadoIp",
            "paths": paths_field,
            "builder_tcl": builder,
            "part_num": _resolve_part_num(self._part_num) or "",
        }

    def prepare(
        self, build_dir: Path, hdl_library: str, force: bool = False
    ) -> SimDirInfo:
        part_num = _resolve_part_num(self._part_num)
        if not part_num:
            raise SystemExit(
                "ERROR: VivadoIp requires a part_num. Pass part_num= to its "
                "constructor, set COCOTB_DEFAULT_PART_NUM, or call "
                "cocotb_vivado.vivado.discover_default_part()."
            )

        resolved_paths = [
            p if p.is_absolute() else (build_dir / p).resolve() for p in self.paths
        ]

        if self.builder_tcl is not None:
            needs_build = force or any(
                not p.exists() or outdated(p, [self.builder_tcl])
                for p in resolved_paths
            )
            if needs_build:
                execute_tcl([self.builder_tcl], cwd=build_dir)

        outdated_paths = (
            resolved_paths if force else self._outofdate(build_dir, resolved_paths)
        )
        if outdated_paths:
            tcl_path = self._write_generation_tcl(outdated_paths, build_dir, part_num)
            execute_tcl([tcl_path], cwd=build_dir)
            self._copy_mem_init_files(build_dir)

        ensure_xsim_ini(build_dir)

        # Merge each IP's discovered libraries / glbl modules / .prj refs.
        merged = SimDirInfo(sim_scripts=build_dir / ".ip_user_files" / "sim_scripts")
        for path in resolved_paths:
            info = read_sim_dir(
                build_dir / ".ip_user_files" / "sim_scripts" / path.stem
            )
            merged.libraries.update(info.libraries)
            merged.glbl_modules.extend(info.glbl_modules)
            # Multiple IPs would each have their own vlog.prj / vhdl.prj. The
            # runner gets at all of them by iterating sources at the call
            # site; here we surface the last one so a single-IP build works.
            if info.vlog_prj is not None:
                merged.vlog_prj = info.vlog_prj
            if info.vhdl_prj is not None:
                merged.vhdl_prj = info.vhdl_prj
        return merged

    @staticmethod
    def _outofdate(build_dir: Path, ip_paths: list) -> list:
        """Filter ``ip_paths`` to those needing regeneration."""
        outofdate: list = []
        for ip_path in ip_paths:
            readme = (
                build_dir
                / ".ip_user_files"
                / "sim_scripts"
                / ip_path.stem
                / "xsim"
                / "README.txt"
            )
            if outdated(readme, [ip_path]):
                outofdate.append(ip_path)
        return outofdate

    @staticmethod
    def _write_generation_tcl(ip_paths: list, build_dir: Path, part_num: str) -> Path:
        path = build_dir / "build_ip.tcl"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"set_part {part_num}\n")
            for ip in ip_paths:
                f.write(f"add_files -norecurse {ip}\n")
            f.write("export_ip_user_files\n")
        return path

    @staticmethod
    def _copy_mem_init_files(build_dir: Path) -> None:
        src_dir = build_dir / ".ip_user_files" / "mem_init_files"
        if not src_dir.is_dir():
            return
        for item in src_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, build_dir / item.name)


class VivadoProject(VivadoSource):
    """A Vivado project (``.xpr``) source.

    On :meth:`prepare`, runs ``open_project; launch_simulation
    -scripts_only -absolute_path`` when the ``.xpr`` (or its
    ``builder_tcl``) is newer than the resulting ``elaborate.sh``
    (mtime check). The project carries its own target part;
    ``part_num`` is only needed to *retarget* it for simulation
    (e.g. when the original device isn't installed locally). The
    override is applied in-memory via ``set_part`` and never saved
    back to the ``.xpr``.

    ``launch_simulation -scripts_only`` is Vivado's canonical
    "generate the simulator launch scripts without launching"
    command. It emits per-language ``.prj`` files (consumed via
    ``xvlog -prj`` / ``xvhdl -prj``) and a ``elaborate.sh`` script
    whose ``xelab`` invocation lists the required ``-L`` libraries.

    Output location: ``{xpr_parent}/{xpr_stem}.sim/sim_1/behav/xsim/``
    — Vivado's default for the ``sim_1`` simset in behavioral mode.
    Projects with non-default simsets or simulation modes should be
    handled via :class:`VivadoExportedSim` and user-controlled TCL.

    Args:
        xpr_path: Path to the ``.xpr`` project file. Relative paths
            resolve under the build directory — useful when the
            project is itself produced by ``builder_tcl``.
        builder_tcl: Optional TCL that produces the ``.xpr`` on its
            first run (e.g. ``create_project`` + BD construction).
            Re-run when the TCL is newer than the resulting ``.xpr``.
        part_num: Optional Xilinx part to retarget the project to
            at script-extraction time. Injected as ``set_part`` after
            ``open_project``, before ``launch_simulation``.
    """

    def __init__(
        self,
        xpr_path: PathLike,
        builder_tcl: PathLike | None = None,
        part_num: str | None = None,
    ) -> None:
        path = Path(xpr_path)
        if path.suffix != ".xpr":
            raise ValueError(f"VivadoProject expects a .xpr path, got {path}")
        self.xpr_path = path
        self.builder_tcl: Path | None = (
            Path(builder_tcl) if builder_tcl is not None else None
        )
        self._part_num = part_num

    def fingerprint(self) -> dict:
        # builder_tcl, when set, is the canonical input; the .xpr it
        # produces is derived. Without builder_tcl, the .xpr is the
        # canonical input and must be hashed.
        if self.builder_tcl is not None:
            xpr_field: object = str(self.xpr_path)
            builder = {
                "path": str(self.builder_tcl),
                "sha256": _hash_file(self.builder_tcl),
            }
        else:
            xpr_field = {
                "path": str(self.xpr_path),
                "sha256": _hash_file(self.xpr_path),
            }
            builder = None
        return {
            "kind": "VivadoProject",
            "xpr": xpr_field,
            "builder_tcl": builder,
            "part_num": self._part_num or "",
        }

    def prepare(
        self, build_dir: Path, hdl_library: str, force: bool = False
    ) -> SimDirInfo:
        xpr_path = (
            self.xpr_path
            if self.xpr_path.is_absolute()
            else (build_dir / self.xpr_path).resolve()
        )

        if self.builder_tcl is not None and (
            force or outdated(xpr_path, [self.builder_tcl])
        ):
            execute_tcl([self.builder_tcl], cwd=build_dir)

        export_dir = xpr_path.parent / f"{xpr_path.stem}.sim" / "sim_1" / "behav"
        result_file = export_dir / "xsim" / "elaborate.sh"

        rebuild_inputs: list = [xpr_path]
        if self.builder_tcl is not None:
            rebuild_inputs.append(self.builder_tcl)

        if force or outdated(result_file, rebuild_inputs):
            tcl_path = build_dir / "launch_xpr.tcl"
            lines = [f"open_project {xpr_path}"]
            if self._part_num:
                lines.append(f"set_part {self._part_num}")
            lines.append("launch_simulation -scripts_only -absolute_path")
            lines.append("exit")
            tcl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            execute_tcl([tcl_path], cwd=build_dir)

        ensure_xsim_ini(build_dir)
        return read_sim_dir(export_dir)


class VivadoExportedSim(VivadoSource):
    """A user-supplied TCL script that itself produces a sim-scripts directory.

    Use for project flows where one TCL drives ``launch_simulation
    -scripts_only -absolute_path``. The TCL is re-run only when it is
    newer than ``result_file`` (an artifact inside ``result_dir``,
    typically ``xsim/elaborate.sh``).

    Args:
        tcl_file: Path to the TCL script. May be ``None`` for an
            already-extracted sim-scripts directory; in that case
            nothing is re-run and only ``result_dir`` is consulted.
        result_dir: Directory the sim scripts land in. Relative paths
            resolve under the build directory.
        result_file: Artifact under ``result_dir`` whose mtime
            controls the re-run decision. Defaults to
            ``xsim/elaborate.sh`` under ``result_dir``.
        force_extract: If ``True``, follow the user's TCL with a
            helper that runs ``launch_simulation -scripts_only`` and
            exits. Useful for TCL files produced by ``write_bd_tcl``
            that don't extract sim scripts themselves.
    """

    def __init__(
        self,
        tcl_file: PathLike | None = None,
        result_dir: PathLike = "sim_export",
        result_file: PathLike | None = None,
        force_extract: bool = False,
    ) -> None:
        self.tcl_file: Path | None = Path(tcl_file) if tcl_file is not None else None
        self.result_dir: Path = Path(result_dir)
        self.result_file: Path | None = (
            Path(result_file) if result_file is not None else None
        )
        self.force_extract: bool = force_extract

    def fingerprint(self) -> dict:
        # tcl_file, when set, is the canonical input. Without it the
        # source is content-defined by whatever's already in result_dir,
        # so hash that directory's manifest instead.
        if self.tcl_file is not None:
            tcl_field: object = {
                "path": str(self.tcl_file),
                "sha256": _hash_file(self.tcl_file),
            }
            result_field: object = str(self.result_dir)
        else:
            tcl_field = None
            result_field = {
                "path": str(self.result_dir),
                "sha256": _hash_dir(self.result_dir),
            }
        return {
            "kind": "VivadoExportedSim",
            "tcl_file": tcl_field,
            "result_dir": result_field,
            "result_file": str(self.result_file) if self.result_file else None,
            "force_extract": self.force_extract,
        }

    def prepare(
        self, build_dir: Path, hdl_library: str, force: bool = False
    ) -> SimDirInfo:
        export_dir = (
            self.result_dir
            if self.result_dir.is_absolute()
            else build_dir / self.result_dir
        )
        result_file = (
            self.result_file
            if self.result_file is not None and self.result_file.is_absolute()
            else (
                build_dir / self.result_file
                if self.result_file is not None
                else export_dir / "xsim" / "elaborate.sh"
            )
        )

        if self.tcl_file is not None and (
            force or outdated(result_file, [self.tcl_file])
        ):
            tcl_paths: list = [self.tcl_file]
            if self.force_extract:
                forced = build_dir / "extract_scripts.tcl"
                forced.write_text(EXPORT_SCRIPTS_TCL, encoding="utf-8")
                tcl_paths.append(forced)
            execute_tcl(tcl_paths, cwd=build_dir)

        ensure_xsim_ini(build_dir)
        return read_sim_dir(export_dir)


class VivadoBd(VivadoSource):
    """A Vivado block design (``.bd``) source, with interface flattening.

    On :meth:`prepare`, builds a throwaway Vivado project under the
    build directory, adds the ``.bd``, optionally generates an RTL
    wrapper via ``make_wrapper -top -import`` to flatten interface
    ports, and runs ``launch_simulation -scripts_only -absolute_path``
    to emit the per-language ``.prj`` files plus the xelab ``*.sh``
    script — the same canonical interface :class:`VivadoProject`
    produces.

    Why a wrapper, and why not :class:`VivadoIp`'s
    ``export_ip_user_files``: a block design whose top is built from
    ``create_bd_intf_port`` (AXI / AXIS / BRAM interfaces) is not
    directly drivable — XSI exposes only top-level *scalar* ports, with
    no hierarchical or interface access. Vivado's generated wrapper
    flattens each interface bundle into discrete scalar ports, which is
    the only form cocotb / cocotbext can bind to. ``make_wrapper`` needs
    a project + fileset, so this class always uses the project +
    ``launch_simulation`` path (not ``export_ip_user_files``); the
    ``wrapper`` flag only toggles whether the wrapper is generated.

    The throwaway project lives under ``build_dir`` — a regenerated
    build artifact, not a user-managed ``.xpr``. ``launch_simulation``
    needs a real on-disk project (an ``-in_memory`` project has nowhere
    to write its sim scripts), and ``make_wrapper`` needs that project's
    fileset; one project serves both.

    Args:
        bd_path: Path to the ``.bd`` block design. Relative paths
            resolve under the build directory — useful when the BD is
            itself produced by ``builder_tcl``.
        builder_tcl: Optional TCL that constructs and ``save_bd_design``
            the ``.bd`` on its first run. Re-run when the TCL is newer
            than the ``.bd`` it produces, or when the ``.bd`` is
            missing. Lets a test fixture commit only the recipe, not the
            generated (Vivado-version-specific) ``.bd``.
        part_num: Xilinx part name (e.g. ``"xczu7eg-ffvc1156-2-e"``).
            Falls back to ``COCOTB_DEFAULT_PART_NUM`` env. Required.
        wrapper: When ``True`` (default), generate and elaborate the RTL
            wrapper — this flattens interface ports and makes the
            toplevel ``<bd>_wrapper``. When ``False``, elaborate the
            block-design module directly (only viable when the BD's top
            ports are all plain signals, ``create_bd_port``).
        top: Escape hatch to override the *reported* :attr:`top` for the
            rare case where the BD design name differs from the ``.bd``
            filename. Does **not** rename the wrapper — Vivado fixes that
            to ``<design>_wrapper``; this only changes what name callers
            are told to elaborate.
    """

    def __init__(
        self,
        bd_path: PathLike,
        builder_tcl: PathLike | None = None,
        part_num: str | None = None,
        wrapper: bool = True,
        top: str | None = None,
    ) -> None:
        path = Path(bd_path)
        if path.suffix != ".bd":
            raise ValueError(f"VivadoBd expects a .bd path, got {path}")
        self.bd_path = path
        self.builder_tcl: Path | None = (
            Path(builder_tcl) if builder_tcl is not None else None
        )
        self._part_num = part_num
        self.wrapper = wrapper
        self._top_override = top

    @property
    def top(self) -> str:
        """Toplevel module name to pass as ``hdl_toplevel``.

        ``<bd-stem>_wrapper`` when :attr:`wrapper` is set (Vivado's
        ``make_wrapper`` naming convention), else the bare ``<bd-stem>``.
        A ``top=`` constructor arg overrides the stem for the
        design-name-not-equal-filename edge case.
        """
        base = self._top_override or self.bd_path.stem
        return f"{base}_wrapper" if self.wrapper else base

    @property
    def library(self) -> str:
        """HDL library the generated BD / wrapper sources land in.

        Vivado puts block-design structural HDL in ``xil_defaultlib``;
        pass this as ``hdl_library`` so the call has no hand-typed magic
        string: ``hdl_toplevel=bd.top, hdl_library=bd.library``.
        """
        return "xil_defaultlib"

    def fingerprint(self) -> dict:
        # builder_tcl, when set, is the canonical input; the .bd it
        # produces is derived. Without builder_tcl, the .bd is the
        # canonical input and must be hashed. wrapper / top change the
        # generated toplevel, so they belong in the identity.
        if self.builder_tcl is not None:
            bd_field: object = str(self.bd_path)
            builder = {
                "path": str(self.builder_tcl),
                "sha256": _hash_file(self.builder_tcl),
            }
        else:
            bd_field = {
                "path": str(self.bd_path),
                "sha256": _hash_file(self.bd_path),
            }
            builder = None
        return {
            "kind": "VivadoBd",
            "bd": bd_field,
            "builder_tcl": builder,
            "part_num": _resolve_part_num(self._part_num) or "",
            "wrapper": self.wrapper,
            "top": self._top_override,
        }

    def prepare(
        self, build_dir: Path, hdl_library: str, force: bool = False
    ) -> SimDirInfo:
        part_num = _resolve_part_num(self._part_num)
        if not part_num:
            raise SystemExit(
                "ERROR: VivadoBd requires a part_num. Pass part_num= to its "
                "constructor, set COCOTB_DEFAULT_PART_NUM, or call "
                "cocotb_vivado.vivado.discover_default_part()."
            )

        bd_path = (
            self.bd_path
            if self.bd_path.is_absolute()
            else (build_dir / self.bd_path).resolve()
        )

        if self.builder_tcl is not None and (
            force or outdated(bd_path, [self.builder_tcl])
        ):
            execute_tcl([self.builder_tcl], cwd=build_dir)

        proj_name = self.bd_path.stem
        proj_dir = build_dir / f"{proj_name}_bd_prj"
        export_dir = proj_dir / f"{proj_name}.sim" / "sim_1" / "behav"
        result_file = export_dir / "xsim" / "elaborate.sh"

        rebuild_inputs: list = [bd_path]
        if self.builder_tcl is not None:
            rebuild_inputs.append(self.builder_tcl)

        if force or outdated(result_file, rebuild_inputs):
            tcl_path = self._write_generation_tcl(
                bd_path, proj_dir, proj_name, part_num, build_dir
            )
            execute_tcl([tcl_path], cwd=build_dir)

        ensure_xsim_ini(build_dir)
        info = read_sim_dir(export_dir)
        self._assert_top_present(info)
        return info

    def _write_generation_tcl(
        self,
        bd_path: Path,
        proj_dir: Path,
        proj_name: str,
        part_num: str,
        build_dir: Path,
    ) -> Path:
        lines = [
            f"create_project -force {proj_name} {proj_dir} -part {part_num}",
            f"add_files -norecurse {bd_path}",
        ]
        if self.wrapper:
            lines.append(
                "make_wrapper -files "
                '[get_files -filter {FILE_TYPE == "Block Designs"}] -top -import'
            )
        lines += [
            f"set_property top {self.top} [current_fileset -simset]",
            f"generate_target simulation [get_files {bd_path}]",
            "launch_simulation -scripts_only -absolute_path",
            "exit",
        ]
        tcl_path = build_dir / f"build_bd_{proj_name}.tcl"
        tcl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return tcl_path

    def _assert_top_present(self, info: SimDirInfo) -> None:
        """Fail early and actionably if the expected top isn't generated.

        ``make_wrapper`` names the wrapper ``<design>_wrapper``, where
        ``<design>`` is the BD design name (normally the ``.bd`` stem).
        If the design name differs, :attr:`top` is wrong and xelab would
        otherwise fail downstream with an opaque "unit not found". Catch
        it here while we can point at the fix. Heuristic: the expected
        name appears as a path component in a generated ``.prj``.
        """
        prjs = [p for p in (info.vlog_prj, info.vhdl_prj) if p is not None]
        if not prjs:
            return  # nothing generated; a different error will surface
        combined = "\n".join(p.read_text(encoding="utf-8") for p in prjs)
        if self.top in combined:
            return
        raise SystemExit(
            f"ERROR: VivadoBd expected toplevel '{self.top}' but no matching "
            "source was found in the generated .prj files. If your BD design "
            "name differs from the .bd filename, pass top= to VivadoBd."
        )

# Copyright cocotb-vivado contributors
# Copyright 2026 Kiran Vuksanaj
# Licensed under the Apache License 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Derived from vicoco's Vivado runner (https://github.com/kiran-vuksanaj/vicoco),
# restructured to delegate IP/BD/project handling to cocotb_vivado.vivado.

"""Python runner subclass driving Vivado's XSim binaries.

This module orchestrates XSim binary invocations only: ``xvlog``,
``xvhdl``, and ``xelab``. Anything that runs the full ``vivado`` tool
(TCL execution, IP regeneration, project export, part discovery) lives
in :mod:`cocotb_vivado.vivado` and is reached via Vivado-managed
source objects (:class:`cocotb_vivado.vivado.VivadoSource` subclasses)
passed in the runner's ``sources=[...]`` list.

The contract for finding Vivado:

* The XSim binaries must be on ``PATH`` (source ``settings64.sh``).
* ``LD_LIBRARY_PATH`` must be set before the test subprocess runs.
  If unset and ``XILINX_VIVADO`` is set, the runner synthesizes a
  ``LD_LIBRARY_PATH`` from it as a courtesy fallback.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from os import environ
from pathlib import Path
from typing import Literal

from cocotb import runner
from cocotb.runner import VHDL, Simulator, Verilog

from .vivado import VivadoSource

PathLike = Path | str
Command = list[str]
Timescale = tuple

WaveFormat = Literal["wdb", "vcd", "fst"]

SIGNATURE_SCHEMA_VERSION = 1
SIGNATURE_FILENAME = "build_signature.json"

cache_log = logging.getLogger("cocotb_vivado.runner.cache")

_FILE_DUMP_WAVES = """\
{timescale_declaration}
module cocotb_vivado_dump();
  initial begin
    $dumpfile("{waveform_filename}");
    $dumpvars(0,{toplevel});
  end
endmodule
"""


def _hash_file(path: Path) -> str:
    """SHA-256 hex digest of file contents. Empty string if missing."""
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@functools.cache
def get_xsim_tool_versions() -> dict[str, str]:
    """Capture xelab/xvlog/xvhdl --version output, cached for the session."""
    versions: dict[str, str] = {}
    for tool in ("xelab", "xvlog", "xvhdl"):
        try:
            result = subprocess.run(
                [tool, "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            lines = result.stdout.strip().splitlines()
            versions[tool] = lines[0] if lines else ""
        except (FileNotFoundError, subprocess.TimeoutExpired):
            versions[tool] = ""
    return versions


def _load_signature(sig_path: Path) -> dict | None:
    """Read and parse a stored build_signature.json, or None if absent/corrupt."""
    if not sig_path.exists():
        return None
    try:
        return json.loads(sig_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _save_signature(sig_path: Path, sig: dict) -> None:
    """Write a signature dict as JSON. Atomic via tmp-and-rename."""
    tmp = sig_path.with_suffix(sig_path.suffix + ".tmp")
    tmp.write_text(json.dumps(sig, sort_keys=True, indent=2), encoding="utf-8")
    tmp.replace(sig_path)


class Vivado(Simulator):  # type: ignore[no-any-unimported]
    """cocotb Python runner for the Vivado XSim simulator (XSI only)."""

    supported_gpi_interfaces = {"verilog": ["xsi"], "vhdl": ["xsi"]}
    LAUNCHING_MODULE = "cocotb_vivado"

    def __init__(self) -> None:
        self.extra_global_modules: list[str] = []
        self.wave_format: WaveFormat | None = None
        self.elab_modules: list[str] = []
        self.xilinx_libraries: set = set()
        self.snapshot_name: str = ""
        self.wave_paths: dict = {}
        self.vivado_sources: list[VivadoSource] = []
        self._pending_signature: dict | None = None
        self._force_prepare: bool = False
        self.log = logging.getLogger(__name__)
        super().__init__()

    # ------------------------------------------------------------------
    # build / test overrides
    # ------------------------------------------------------------------

    def build(
        self,
        *args: object,
        wave_format: WaveFormat | None = None,
        extra_global_modules: Sequence[str] | None = None,
        **kwargs: object,
    ) -> None:
        """Build the HDL design with the XSim binaries.

        Accepts every kwarg of :meth:`cocotb.runner.Simulator.build`,
        plus:

        Args:
            wave_format: Waveform format to emit. ``None`` disables
                waves. ``"fst"`` post-processes the VCD into FST via
                ``vcd2fst`` (auto-downgrades to ``"vcd"`` with a
                warning when ``vcd2fst`` is missing). Setting this
                forces ``waves=True`` for the base build step.
            extra_global_modules: Additional top-level global modules
                to elaborate (e.g. user-supplied ``glbl`` shims).
                Forwarded to ``xelab`` after the design top.

        ``sources=[...]`` may contain plain HDL paths, cocotb's
        :class:`cocotb.runner.Verilog` / :class:`cocotb.runner.VHDL`
        tagged paths, or
        :class:`cocotb_vivado.vivado.VivadoSource` instances
        (:class:`~cocotb_vivado.vivado.VivadoIp`,
        :class:`~cocotb_vivado.vivado.VivadoProject`,
        :class:`~cocotb_vivado.vivado.VivadoExportedSim`). The latter
        self-orchestrate their Vivado-tool invocations and return
        :class:`~cocotb_vivado.vivado.SimDirInfo` views the runner
        consumes (``.prj`` files, ``-L`` libraries, glbl modules).
        """
        self.wave_format = self._resolve_wave_format(wave_format)
        self.extra_global_modules = list(extra_global_modules or [])
        if self.wave_format is not None:
            kwargs.setdefault("waves", True)

        # cocotb's base build() calls get_abs_paths(sources) which only
        # accepts os.PathLike. Strip VivadoSource instances out and stash
        # them; _build_command handles them via self.vivado_sources below.
        sources_in = kwargs.get("sources") or []
        assert isinstance(sources_in, Sequence), (
            f"sources= must be a sequence, got {type(sources_in).__name__}"
        )
        self.vivado_sources = [s for s in sources_in if isinstance(s, VivadoSource)]
        kwargs["sources"] = [s for s in sources_in if not isinstance(s, VivadoSource)]

        self._pending_signature = None
        self._force_prepare = False

        super().build(*args, **kwargs)

        # Build succeeded (no exception). Persist the new signature on a
        # cache miss. On a hit, _pending_signature stays None — the
        # already-on-disk signature is still authoritative.
        if self._pending_signature is not None:
            _save_signature(
                self.build_dir / SIGNATURE_FILENAME, self._pending_signature
            )

    def test(
        self,
        *args: object,
        wave_format: WaveFormat | None = None,
        **kwargs: object,
    ) -> None:
        """Run the cocotb test. ``wave_format``: same semantics as in :meth:`build`."""
        if wave_format is not None:
            self.wave_format = self._resolve_wave_format(wave_format)
            kwargs.setdefault("waves", True)
        super().test(*args, **kwargs)
        if not self.waves:
            # XSI always writes a waveform DB on open (default name
            # ``xsi.wdb``); with no waves requested it holds only the
            # contentless design hierarchy. Drop it so build_dir keeps
            # only real, traced captures — the ``<snapshot>.wdb`` a
            # ``waves=True`` run produces.
            (self.build_dir / "xsi.wdb").unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Simulator-binary contract
    # ------------------------------------------------------------------

    @staticmethod
    def _simulator_in_path() -> None:
        """Verify XSim binaries are on ``PATH``."""
        for exe in ("xelab", "xvlog", "xvhdl"):
            if shutil.which(exe) is None:
                raise SystemExit(
                    f"ERROR: '{exe}' executable not found in PATH. "
                    "Source your Vivado settings64.sh."
                )

    # ------------------------------------------------------------------
    # Build / test command assembly
    # ------------------------------------------------------------------

    def _build_command(self) -> Sequence[Command]:
        self._derive_snapshot_name()

        verilog_build_args = [
            str(arg) for arg in self.build_args if type(arg) in (str, Verilog)
        ]
        vhdl_build_args = [
            str(arg) for arg in self.build_args if type(arg) in (str, VHDL)
        ]
        define_args = self._define_args()

        if self.waves:
            self._init_wave_paths()
            if self.wave_format in ("vcd", "fst"):
                self._write_wavedump_file()

        # Tier 1 cache probe: skip the whole pipeline when the input
        # signature matches a prior successful build and its snapshot
        # artifacts are still on disk.
        current_signature = self._compute_signature()
        if not self.always and self._cache_hit(current_signature):
            cache_log.info("cache hit: skipping prepare + xvlog/xvhdl/xelab")
            return []
        self._pending_signature = current_signature
        # Tier 1 missed (or always=True). Force each VivadoSource to
        # re-run its Vivado batch even if its mtime check would have
        # skipped — guards against content-change-without-mtime-change.
        self._force_prepare = True

        cmds: list[Command] = []

        # Vivado-managed sources first: their .prepare() may run vivado batch
        # and emit .prj files plus the elab script the runner reads for
        # the precompiled-library set and glbl modules xelab needs.
        for vivado_source in self.vivado_sources:
            cmds.extend(self._consume_vivado_source(vivado_source))

        for raw_source in self.sources:
            source = Path(raw_source)
            if runner.is_verilog_source(source):
                cmds.append(
                    self._compile_cmd(source, "verilog")
                    + define_args
                    + verilog_build_args
                )
            elif runner.is_vhdl_source(source):
                cmds.append(
                    self._compile_cmd(source, "vhdl") + define_args + vhdl_build_args
                )
            else:
                raise ValueError(
                    f"Unknown file type: {source!s} cannot be compiled. "
                    "Use a cocotb_vivado.vivado.VivadoSource subclass for "
                    "Vivado-managed sources (.xci, .bd, .xpr, exported TCL)."
                )

        cmds.append(self._elab_command())
        return cmds

    def _consume_vivado_source(self, source: VivadoSource) -> list[Command]:
        """Run a Vivado source's ``.prepare()`` and return its compile commands.

        Side effects: extends ``self.xilinx_libraries`` and
        ``self.elab_modules`` from the returned :class:`SimDirInfo`.
        """
        info = source.prepare(
            self.build_dir, self.hdl_library, force=self._force_prepare
        )
        self.xilinx_libraries.update(info.libraries)
        self.elab_modules.extend(info.glbl_modules)
        cmds: list[Command] = []
        if info.vlog_prj is not None:
            cmds.append(self._compile_cmd(info.vlog_prj, "verilog", prj=True))
        if info.vhdl_prj is not None:
            cmds.append(self._compile_cmd(info.vhdl_prj, "vhdl", prj=True))
        return cmds

    def _test_command(self) -> Sequence[Command]:
        if self.waves and self.hdl_toplevel_lang == "vhdl":
            self.log.warning(
                "Waveform dump via $dumpfile/$dumpvars is not reachable on a "
                "VHDL top. Only the Vivado WDB output is available."
            )

        cmd: list[Command] = [["python3", "-m", self.LAUNCHING_MODULE]]

        self._populate_test_env()

        if self.waves and self.wave_format == "fst":
            vcd_path = self.wave_paths.get("vcd")
            fst_path = self.wave_paths.get("fst")
            if vcd_path is not None and fst_path is not None:
                cmd.append(["vcd2fst", str(vcd_path), str(fst_path)])

        return cmd

    # ------------------------------------------------------------------
    # Tier 1 build cache
    # ------------------------------------------------------------------

    def _compute_signature(self) -> dict:
        """Build the JSON-serializable signature for the current build."""
        return {
            "schema_version": SIGNATURE_SCHEMA_VERSION,
            "tool_versions": get_xsim_tool_versions(),
            "kwargs": {
                "hdl_toplevel": self.hdl_toplevel,
                "hdl_library": self.hdl_library,
                "parameters": dict(sorted(self.parameters.items())),
                "defines": dict(sorted(self.defines.items())),
                "build_args": [str(a) for a in self.build_args],
                "includes": [
                    {"path": str(p), "sha256": _hash_file(Path(p))}
                    for p in self.includes
                ],
                "timescale": list(self.timescale) if self.timescale else None,
                "waves": bool(self.waves),
                "wave_format": self.wave_format,
                "extra_global_modules": list(self.extra_global_modules),
            },
            "user_sources": [
                {"path": str(p), "sha256": _hash_file(Path(p))} for p in self.sources
            ],
            "vivado_sources": [s.fingerprint() for s in self.vivado_sources],
        }

    def _cache_hit(self, current: dict) -> bool:
        """Return True iff a valid cache exists and all artifacts are present."""
        sig_path = self.build_dir / SIGNATURE_FILENAME
        stored = _load_signature(sig_path)
        if stored is None:
            cache_log.info("cache miss: signature absent or unreadable")
            return False
        if stored != current:
            cache_log.info("cache miss: signature mismatch")
            return False
        snapshot = self.build_dir / "xsim.dir" / self.snapshot_name / "xsimk.so"
        if not snapshot.exists():
            cache_log.info("cache miss: snapshot artifact missing (%s)", snapshot)
            return False
        if self.waves and self.wave_format in ("vcd", "fst"):
            dump_file = self.build_dir / "cocotb_vivado_dump.v"
            if not dump_file.exists():
                cache_log.info("cache miss: wavedump file missing")
                return False
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_wave_format(self, wave_format: WaveFormat | None) -> WaveFormat | None:
        if wave_format is None:
            return None
        if wave_format == "fst" and shutil.which("vcd2fst") is None:
            self.log.warning(
                "wave_format='fst' requested but 'vcd2fst' is not on PATH "
                "(install gtkwave). Falling back to wave_format='vcd'."
            )
            return "vcd"
        return wave_format

    def _derive_snapshot_name(self) -> None:
        top = self.hdl_toplevel or "top"
        self.snapshot_name = top.split(".")[-1]

    def _init_wave_paths(self) -> None:
        base = self.snapshot_name
        self.wave_paths = {
            "wdb": self.build_dir / f"{base}.wdb",
            "vcd": self.build_dir / f"{base}.vcd",
            "fst": self.build_dir / f"{base}.fst",
        }

    def _compile_cmd(self, src_file: Path, language: str, prj: bool = False) -> Command:
        compiler = {"vhdl": "xvhdl", "verilog": "xvlog"}[language]
        cmd: Command = [compiler, "--incr", "--relax", "-work", self.hdl_library]
        if prj:
            cmd.append("-prj")
        elif language == "verilog" and src_file.suffix == ".sv":
            cmd.append("-sv")
        cmd.append(str(src_file.resolve()))
        if language == "verilog":
            cmd += self._get_include_options(self.includes)
        return cmd

    def _elab_command(self) -> Command:
        toplevel = self.hdl_toplevel or ""
        if "." not in toplevel:
            toplevel = f"{self.hdl_library}.{toplevel}"

        elab_args: Command = [
            "xelab",
            "-top",
            toplevel,
            "-snapshot",
            self.snapshot_name,
            *self._get_include_options(self.includes),
            *self._define_args(),
            *self._get_parameter_options(self.parameters),
        ]

        elab_args.extend(self.elab_modules)
        elab_args.extend(self.extra_global_modules)

        for library_name in sorted(self.xilinx_libraries):
            elab_args.extend(["-L", library_name])

        elab_args.extend(["-dll", "-debug", "wave"])

        return elab_args

    def _define_args(self) -> Command:
        out: Command = []
        for key, val in self.defines.items():
            out.extend(["-d", f"{key}={val}"])
        return out

    def _get_parameter_options(self, parameters: Mapping[str, object]) -> Command:
        out: Command = []
        for name, value in parameters.items():
            out.extend(["-generic_top", f"{name}={value}"])
        return out

    @staticmethod
    def _get_include_options(includes: Sequence[Path]) -> Command:
        out: Command = []
        for incl in includes:
            out.extend(["-i", str(incl)])
        return out

    def _write_wavedump_file(self) -> None:
        """Inject a Verilog module that calls ``$dumpfile``/``$dumpvars``."""
        toplevel = self.snapshot_name
        vcd_path = self.wave_paths["vcd"]
        timescale_declaration = ""
        if self.timescale is not None:
            stepsize, precision = self.timescale
            timescale_declaration = f"`timescale {stepsize} / {precision}"

        text = _FILE_DUMP_WAVES.format(
            waveform_filename=str(vcd_path),
            toplevel=toplevel,
            timescale_declaration=timescale_declaration,
        )
        dump_path = self.build_dir / "cocotb_vivado_dump.v"
        dump_path.write_text(text, encoding="utf-8")

        self.elab_modules.append(f"{self.hdl_library}.cocotb_vivado_dump")
        self.sources.append(dump_path)

    def _populate_test_env(self) -> None:
        """Stage env vars the cocotb subprocess relies on."""
        self.env["VIVADO_SNAPSHOT_NAME"] = self.snapshot_name
        self.env["TOPLEVEL_LANG"] = self.hdl_toplevel_lang or "verilog"
        if self.waves:
            wdb = self.wave_paths.get("wdb")
            if wdb is not None:
                self.env["VIVADO_WDB_FILE"] = str(wdb)

        if "LD_LIBRARY_PATH" not in os.environ:
            xilinx_root = environ.get("XILINX_VIVADO")
            if xilinx_root is None:
                raise SystemExit(
                    "ERROR: LD_LIBRARY_PATH is not set and XILINX_VIVADO is not "
                    "set as a fallback. Source your Vivado settings64.sh so the "
                    "XSI shared libraries can be loaded."
                )
            self.env["LD_LIBRARY_PATH"] = (
                f"{xilinx_root}/lib/lnx64.o:{xilinx_root}/lib/lnx64.o/Default"
            )


def get_runner(simulator_name: str, **kwargs: object) -> Simulator:  # type: ignore[no-any-unimported]
    """``get_runner`` shim that returns the Vivado runner for ``"vivado"``.

    Delegates to :func:`cocotb.runner.get_runner` for any other name so
    the same factory works for projects that mix simulators.
    """
    if simulator_name == "vivado":
        return Vivado(**kwargs)
    return runner.get_runner(simulator_name)

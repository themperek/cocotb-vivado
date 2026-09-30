"""Local test matrix for cocotb-vivado.

The full suite needs Vivado's XSim, and no hosted CI runner has it, so this
matrix runs locally. It sweeps three axes:

* **cocotb**  — driven by nox (``COCOTB_VERSIONS``), a fresh env per version.
* **Python**  — driven by nox (``PYTHON_VERSIONS``); the ``uv`` backend
                provisions the interpreters, so no pyenv/conda is needed.
* **Vivado**  — from the ``VIVADO_SETTINGS`` env var: a ``os.pathsep``-joined
                list of ``settings64.sh`` paths. Each is sourced in an
                isolated shell and its environment captured, so combos never
                share a shell — the "two settings64.sh in one shell pollutes
                PATH" hazard cannot occur here. If ``VIVADO_SETTINGS`` is
                unset, the matrix runs once against whatever Vivado is already
                on ``PATH`` (and fails fast if none is).

Launch nox from a shell with *no* Vivado sourced, so each captured Vivado
environment starts from a clean PATH::

    export VIVADO_SETTINGS=/opt/Xilinx/Vivado/2023.1/settings64.sh:/opt/Xilinx/2025.1/Vivado/settings64.sh
    nox                 # tests/ across every cocotb version x every Vivado
    nox -s pythons      # tests/ across Python versions on the newest cocotb
    nox -s examples     # examples/ smoke on the newest cocotb

Requires ``uv`` (https://docs.astral.sh/uv/) and ``nox``.

The static, Vivado-free GPI-contract check is separate:
``scripts/check_cocotb_compat.py``.
"""

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import nox

nox.options.default_venv_backend = "uv"
# Plain `nox` runs the shim gate; the others are opt-in.
nox.options.sessions = ["sim"]

# cocotb 2.x releases the shim is verified against. 2.0.0 is the declared
# floor (see pyproject). Extend as new releases land, then re-run this matrix
# and update the "Tested versions" table before widening the bound.
COCOTB_VERSIONS = ["2.0.0", "2.0.1", "2.1.0"]

# requires-python floor and a current release. uv fetches these.
PYTHON_VERSIONS = ["3.10", "3.13"]

EXAMPLES = ["counter", "parameters", "ip"]

# Vivado axis: settings64.sh paths from the environment. Empty -> a single
# run against the ambient toolchain (None sentinel).
_SETTINGS = [p for p in os.environ.get("VIVADO_SETTINGS", "").split(os.pathsep) if p]
VIVADO_PARAMS = _SETTINGS or [None]


def _vivado_id(settings: str | None) -> str:
    """Short parametrize id: the version token, else the parent dir, else 'ambient'."""
    if settings is None:
        return "ambient"
    m = re.search(r"20\d\d\.\d+", settings)
    return m.group(0) if m else Path(settings).parent.name


def _vivado_env(settings: str | None) -> dict[str, str] | None:
    """Source a Vivado settings64.sh in an isolated shell and capture its env.

    Returns None for the ambient case (inherit nox's own environment). The
    captured env fully replaces the child's, so nothing leaks between combos.
    """
    if settings is None:
        return None
    script = (
        f"source {shlex.quote(settings)} >/dev/null 2>&1 && "
        "export LD_LIBRARY_PATH=$XILINX_VIVADO/lib/lnx64.o && env -0"
    )
    out = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=True
    ).stdout
    return dict(kv.split("=", 1) for kv in out.split("\0") if "=" in kv)


def _require_vivado(session: nox.Session, env: dict[str, str] | None) -> None:
    """Fail fast with a clear message if no Vivado toolchain is reachable."""
    path = None if env is None else env.get("PATH")
    if shutil.which("xelab", path=path) is None:
        session.error(
            "xelab not found — set VIVADO_SETTINGS to one or more "
            "settings64.sh paths, or source a Vivado before running nox."
        )
    xilinx = (env or os.environ).get("XILINX_VIVADO", "<unknown>")
    session.log(f"Vivado: {xilinx}")


def _install(session: nox.Session, cocotb: str) -> None:
    """Install the project pinned to one cocotb version.

    ``--no-deps`` on the project keeps pyproject's ``cocotb`` range from
    resolving over the version under test; the pinned cocotb is installed
    explicitly. cocotb is the project's only runtime dependency.
    """
    session.install(".", "--no-deps")
    session.install("pytest", "cocotbext-axi", f"cocotb=={cocotb}")


@nox.session
@nox.parametrize("vivado", VIVADO_PARAMS, ids=[_vivado_id(v) for v in VIVADO_PARAMS])
@nox.parametrize("cocotb", COCOTB_VERSIONS)
def sim(session: nox.Session, cocotb: str, vivado: str | None) -> None:
    """Run ``tests/`` across cocotb x Vivado (the shim compatibility gate)."""
    env = _vivado_env(vivado)
    _require_vivado(session, env)
    _install(session, cocotb)
    session.run("pytest", "-q", "tests", env=env)


@nox.session(python=PYTHON_VERSIONS)
@nox.parametrize("vivado", VIVADO_PARAMS, ids=[_vivado_id(v) for v in VIVADO_PARAMS])
def pythons(session: nox.Session, vivado: str | None) -> None:
    """Run ``tests/`` across Python versions on the newest supported cocotb."""
    env = _vivado_env(vivado)
    _require_vivado(session, env)
    _install(session, COCOTB_VERSIONS[-1])
    session.run("pytest", "-q", "tests", env=env)


@nox.session
@nox.parametrize("vivado", VIVADO_PARAMS, ids=[_vivado_id(v) for v in VIVADO_PARAMS])
def examples(session: nox.Session, vivado: str | None) -> None:
    """Smoke-run the ``examples/`` snippets on the newest supported cocotb."""
    env = _vivado_env(vivado)
    _require_vivado(session, env)
    _install(session, COCOTB_VERSIONS[-1])
    for example in EXAMPLES:
        session.run("pytest", "-q", f"examples/{example}", env=env)

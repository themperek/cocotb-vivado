"""Shared pytest fixtures.

Per-test ``build_dir`` keeps each test's compile/elab artifacts and
build signature isolated under ``tests/sim_build/<test_module>/``, so
the Tier 1 build cache holds across full-suite reruns. Without
isolation, the suite would share one ``sim_build/`` and each test
overwrites the previous test's signature, defeating the cache for any
subsequent suite run.
"""

import ctypes
from pathlib import Path

import pytest


def _xsi_kernel_loadable() -> bool:
    """Can Vivado's XSI kernel library be dlopened in *this* process?

    ``xsimk.so`` carries ``DT_NEEDED`` entries on Vivado's simulator-kernel
    libraries, which the dynamic loader resolves through ``LD_LIBRARY_PATH``
    *as captured when the process started*. Exporting it from inside Python
    is useless, and preloading the kernel library by absolute path does not
    help either -- it pulls its own transitive dependencies out of the same
    directory. So this is an environment precondition a test cannot arrange
    for itself, and Vivado's ``settings64.sh`` does not always export it.

    Runner-based tests are unaffected: the runner exports LD_LIBRARY_PATH for
    the ``python -m cocotb_vivado`` subprocess, deriving it from
    ``XILINX_VIVADO`` when the shell has not set it.
    """
    for name in ("librdi_simulator_kernel.so", "libxv_simulator_kernel.so"):
        try:
            ctypes.CDLL(name)
        except OSError:
            continue
        return True
    return False


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip in-process XSI tests when the kernel library is not loadable."""
    if _xsi_kernel_loadable():
        return
    skip = pytest.mark.skip(
        reason=(
            "Vivado's XSI kernel library is not on the dynamic loader path. "
            "This test dlopens xsimk.so in the pytest process, so "
            "LD_LIBRARY_PATH must be exported before Python starts: "
            "export LD_LIBRARY_PATH=$XILINX_VIVADO/lib/lnx64.o"
        )
    )
    for item in items:
        if "in_process_xsi" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def build_dir(request: pytest.FixtureRequest) -> Path:
    """``tests/sim_build/<test_module>/`` — co-located with the test file."""
    test_file = Path(request.path)
    return test_file.parent / "sim_build" / test_file.stem

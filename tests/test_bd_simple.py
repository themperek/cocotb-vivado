"""Pure block-design example: ``VivadoBd`` ingests a ``.bd`` directly.

Builds a minimal BD (single 8-bit NOT gate, plain-signal ports — no
interfaces) via VivadoBd's builder_tcl hook, then drives ``dut.data_in``
and reads ``dut.data_out``.

Locks in two empirical facts about the BD path:

1. ``VivadoBd("design.bd", builder_tcl=...)`` produces compilable sim
   sources — the BD's structural HDL lands in ``xil_defaultlib`` (hence
   ``bd.library`` below).
2. With ``wrapper=False`` the block-design module itself is the
   toplevel, and its plain-signal ports (``create_bd_port``) are
   reachable as ``dut.<name>`` with no RTL wrapper. Interface ports
   (``create_bd_intf_port`` — AXI/AXIS/etc.) instead need the default
   ``wrapper=True`` to flatten them; see ``test_bd_axi.py``.
"""

import os
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

from cocotb_vivado.runner import get_runner
from cocotb_vivado.vivado import VivadoBd


@cocotb.test()
async def inverter_smoke(dut):
    for value in (0x00, 0xA5, 0xFF, 0x5A):
        dut.data_in.value = value
        await Timer(10, unit="ns")
        expected = (~value) & 0xFF
        assert int(dut.data_out.value) == expected, (
            f"data_in=0x{value:02x} → data_out=0x{int(dut.data_out.value):02x}, "
            f"expected 0x{expected:02x}"
        )


def test_bd_simple(build_dir):
    proj_path = Path(__file__).resolve().parent
    runner = get_runner(os.getenv("SIM", "vivado"))
    bd = VivadoBd(
        "ip/bd_simple/bd_simple.bd",
        builder_tcl=proj_path / "ip" / "bd_simple" / "regen.tcl",
        part_num="xczu7eg-ffvc1156-2-e",
        wrapper=False,
    )
    runner.build(
        sources=[bd],
        hdl_toplevel=bd.top,
        hdl_library=bd.library,
        timescale=("1ns", "1ps"),
        build_dir=str(build_dir),
    )
    runner.test(
        hdl_toplevel=bd.top,
        hdl_toplevel_library=bd.library,
        test_module="test_bd_simple",
        hdl_toplevel_lang="verilog",
        build_dir=str(build_dir),
    )


if __name__ == "__main__":
    _build_dir = Path(__file__).resolve().parent / "sim_build" / Path(__file__).stem
    test_bd_simple(_build_dir)

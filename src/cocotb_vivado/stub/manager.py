# Copyright cocotb-vivado contributors
# Copyright 2026 Kiran Vuksanaj
# Licensed under the Apache License 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
#
# Derived from vicoco's value-change manager
# (https://github.com/kiran-vuksanaj/vicoco); adapted for cocotb 1.x/2.x.

"""XSI simulation manager — singleton driving simulator + callback queues.

Owns the four-queue scheduling layout cocotb's GPI shim expects:

* ``_timerqueue`` — time-keyed map of timed callbacks; the run loop
  advances simulation to the next non-empty key and fires its entry
  list in registration order.
* ``_vcqueue`` — value-change closures evaluated after every kernel
  advance; satisfied closures fire and are removed in the same pass.
* ``_readwrite_queue`` / ``_readonly_queue`` — per-delta-cycle phases
  drained between timed steps so writes settle before reads.

``self.time`` is the authoritative step counter in kernel ticks;
``get_sim_time`` returns it directly and the
:mod:`~cocotb_vivado.stub.simulator` shim wraps it for cocotb's
``(upper32, lower32)`` contract.
"""

from cocotb_vivado import xsi

from .handles import (
    ReadOnlyCbClosure,
    ReadWriteCbClosure,
    TimedCbClosure,
    ValueChangeCbClosure,
    XsimRootHandle,
    XsiPortHandle,
)


class Mgr:
    _inst = None

    def __init__(self, xsim_design, wdb_file=None, toplevel_lang="verilog"):
        self.xsim_design = xsim_design
        self.toplevel_lang = toplevel_lang
        self.xsi = xsi.XSI(
            self.xsim_design, wdb_file=wdb_file, toplevel_lang=toplevel_lang
        )

        self.ports = {}
        self.init_ports()

        self._timerqueue = {0: []}
        self._vcqueue = []
        self._readwrite_queue = []
        self._readonly_queue = []

        self.time = 0
        self.is_running = True

    def get_design_name(self):
        return self.xsim_design

    def init_ports(self):
        ports_num = self.xsi.ports_number()
        for port_id in range(ports_num):
            name = self.xsi.get_port_name(port_id)
            size = self.xsi.get_port_size(port_id)
            self.ports[name] = XsiPortHandle(self, name, port_id, size)

    def _sim_advance(self, steps):
        self.time += steps
        self.xsi.run(steps)

    def _attempt_valuechange_callbacks(self):
        """Fire any value-change callbacks whose condition is now met.

        User callbacks fired inline may register *new* closures (the
        natural cocotb pattern: ``await RisingEdge(...)`` from inside a
        coroutine resumed by another ``RisingEdge`` fire). The three
        phases make iteration order independent of those re-entrant
        registrations:

        1. Snapshot the queue and *check* every closure. Each
           ``change_condition_satisfied`` call also updates the
           closure's ``previous_value`` — that must happen for *every*
           live closure exactly once per attempt.
        2. *Fire* the satisfied closures. Inline registrations from
           those callbacks land in ``self._vcqueue`` but are not in
           our snapshot, so they're deferred to the next attempt.
        3. Rebuild the queue, dropping the fired closures and, with them,
           any closure deregistered without ever firing. ``deregister``
           only sets ``cb = None`` (cocotb's ``GPITrigger._unprime`` drops
           its own reference in the same breath), so such a closure can
           never fire or be re-primed and is pure residue — every ``First``
           / ``with_timeout`` loser and every task killed while parked on
           an edge leaves one behind. Retaining them grows the queue
           without bound and makes each attempt cost more than the last
           (quadratic in simulated time).
        """
        snapshot = list(self._vcqueue)
        fired = []
        for vc in snapshot:
            if vc.cb is not None and vc.change_condition_satisfied():
                fired.append(vc)
        for vc in fired:
            vc()
        fired_ids = {id(vc) for vc in fired}
        self._vcqueue[:] = [
            vc for vc in self._vcqueue if vc.cb is not None and id(vc) not in fired_ids
        ]

    def _any_callbacks_primed(self, callback_list):
        for callback in callback_list:
            if callback.cb is not None:
                return True
        return False

    def run(self):
        next_time = 0
        while len(self._timerqueue) > 0:
            # first normal state: execute all callbacks scheduled for this
            # timestep (in order they were registered)
            for cb in self._timerqueue[next_time]:
                if cb is not None:
                    cb()

            self._timerqueue.pop(next_time)
            self._attempt_valuechange_callbacks()

            if not self.is_running:
                break

            while self._readwrite_queue:
                # release for readwrite phase, values will be set
                self._sim_advance(0)
                released_rw_cb = self._readwrite_queue.pop(0)
                if released_rw_cb is not None:
                    released_rw_cb()
                # once ReadWrite callback executes, all pending writes are
                # complete so, in new stable state, re-attempt value-change cbs
                self._attempt_valuechange_callbacks()

            # once this exits, there are no more readwrite stages so readonly
            # callbacks can run (cannot register value-sets)
            self._sim_advance(0)
            self._attempt_valuechange_callbacks()
            for cb in self._readonly_queue:
                if cb is not None:
                    cb()

            self._readwrite_queue = []
            self._readonly_queue = []

            if len(self._timerqueue) == 0:
                continue

            next_time = min(self._timerqueue.keys())
            while not self._any_callbacks_primed(self._timerqueue[next_time]):
                self._timerqueue.pop(next_time)
                if len(self._timerqueue) == 0:
                    break
                next_time = min(self._timerqueue.keys())

            if len(self._timerqueue) == 0:
                break

            time_to_run = next_time - self.get_sim_time()
            self._sim_advance(time_to_run)

    def get_root_handle(self):
        return XsimRootHandle(self)

    def get_sim_time(self):
        return self.time

    def stop_simulator(self):
        self.is_running = False
        error = self.xsi.close()
        print(f"End simulation with status {xsi.XSI.status[error]}")

    def get_precision(self):
        return self.xsi.get_precision()

    def register_timed_callback(self, t, cb, ud):
        ret = TimedCbClosure(t, cb, ud)
        time_to_fire = self.get_sim_time() + t

        if time_to_fire in self._timerqueue:
            self._timerqueue[time_to_fire].append(ret)
        else:
            self._timerqueue[time_to_fire] = [ret]

        return ret

    def register_value_change_callback(self, handle, callback, edge, ud):
        closure = ValueChangeCbClosure(handle, edge, callback, ud)
        self._vcqueue.append(closure)
        return closure

    def register_readwrite_callback(self, callback, trigger):
        closure = ReadWriteCbClosure(callback, trigger)
        self._readwrite_queue.append(closure)
        return closure

    def register_readonly_callback(self, callback, trigger):
        closure = ReadOnlyCbClosure(callback, trigger)
        self._readonly_queue.append(closure)
        return closure

    @classmethod
    def inst(cls):
        if cls._inst is None:
            raise Exception("Simulation manager (Mgr) not initialized")
        return cls._inst

    @classmethod
    def init(cls, xsim_design, wdb_file=None, toplevel_lang="verilog"):
        cls._inst = Mgr(xsim_design, wdb_file=wdb_file, toplevel_lang=toplevel_lang)
        return cls._inst

    @classmethod
    def close(cls):
        cls._inst = None


__all__ = ["Mgr"]

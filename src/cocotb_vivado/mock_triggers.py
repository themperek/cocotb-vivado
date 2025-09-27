"""
Mock triggers for Vivado simulation.

Creates one global clock timer and synchronizes all trigger events to it.
Since we cannot directly trigger on HDL clock events in Vivado, all triggers
(FallingEdge, RisingEdge, Edge) are mocked to poll signal changes using the
shared timer, providing consistent timing behavior across the simulation.
"""

import cocotb


class TimerSingleton:
    """Singleton class that provides a single reusable Timer(100, "ns") instance."""

    _instance = None
    _timer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TimerSingleton, cls).__new__(cls)
        return cls._instance

    def set_timer(self, timer_set):
        """Set a custom timer instance."""
        self._timer = timer_set

    def get_timer(self):
        """Get the timer instance, creating it if it doesn't exist."""
        if self._timer is None:
            raise Exception("Timer not set. Use set_timer() to set a custom timer instance.")
        return self._timer


# Create a global instance for easy access
_timer_singleton = TimerSingleton()


def set_timer(timer_set):
    """Set a custom timer instance."""
    _timer_singleton.set_timer(timer_set)


def get_timer():
    """Get the timer instance."""
    return _timer_singleton.get_timer()


class OnFallingSignal:
    def __init__(self, signal):
        self.signal = signal
        self.timer = _timer_singleton.get_timer()

    def __await__(self):
        return self._async_method().__await__()

    async def _async_method(self):
        prev = self.signal.value
        while True:
            await self.timer
            now = self.signal.value
            if prev.is_resolvable and now.is_resolvable and prev == 1 and now == 0:
                break
            prev = now


class OnRisingSignal:
    def __init__(self, signal):
        self.signal = signal
        self.timer = _timer_singleton.get_timer()

    def __await__(self):
        return self._async_method().__await__()

    async def _async_method(self):
        prev = self.signal.value
        while True:
            await self.timer
            now = self.signal.value
            if prev.is_resolvable and now.is_resolvable and prev == 0 and now == 1:
                break
            prev = now


class OnSignal:
    def __init__(self, signal):
        self.signal = signal
        self.timer = _timer_singleton.get_timer()

    def __await__(self):
        return self._async_method().__await__()

    async def _async_method(self):
        prev = self.signal.value
        while True:
            await self.timer
            now = self.signal.value
            if prev.is_resolvable and now.is_resolvable and prev != now:
                break
            prev = now


cocotb.triggers.FallingEdge = OnFallingSignal
cocotb.triggers.RisingEdge = OnRisingSignal
cocotb.triggers.Edge = OnSignal

async def clock(signal):
    signal.setimmediatevalue(0)
    while True:
        await _timer_singleton.get_timer()
        signal.setimmediatevalue(1)
        await _timer_singleton.get_timer()
        signal.setimmediatevalue(0)

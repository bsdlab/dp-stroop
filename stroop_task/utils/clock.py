# Custom sleep expecting python 3.11 because of:
# https://docs.python.org/3.11/library/time.html#time.sleep

import time
from typing import Callable


def sleep_s(s: float):
    """Sleep for s seconds."""

    start = time.perf_counter_ns()
    if s > 0.1:
        # If not yet reached 90% of the sleep duration, sleep in 10% increments
        # The 90% threshold is somewhat arbitrary but when testing intervals
        # with 1 ms to 500ms this produced very accurate results with deviation
        # less than 0.1% of the desired target value. On Mac M1 with python 3.11
        while time.perf_counter_ns() - start < (s * 1e9 * 0.9):
            time.sleep(s / 10)

    # Sleep for the remaining time
    while time.perf_counter_ns() - start < s * 1e9:
        pass


def benchmark_sleep(
    sleep_func: Callable, nrep: int = 1000, tsleep: float = 0.001
):
    start = time.perf_counter_ns()
    for _ in range(nrep):
        sleep_func(tsleep)
    end = time.perf_counter_ns()

    print(f"Sleeping {nrep=} times for {tsleep=} s took {end - start} ns")
    print(f"Average time per sleep: {(end - start) / (nrep * 1e9)} s")

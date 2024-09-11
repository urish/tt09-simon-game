# SPDX-FileCopyrightText: © 2023 Uri Shaked <uri@wokwi.com>
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock, Timer
from cocotb.triggers import ClockCycles, Edge, FallingEdge, RisingEdge
import os

GAME_SEQUENCE_TEST_LENGTH = int(os.getenv("GAME_SEQUENCE_TEST_LENGTH", "5"))


def decode_7seg(value: int):
    """Decode a 7-segment value to a digit"""
    decode_map = {
        0x3F: "0",
        0x06: "1",
        0x5B: "2",
        0x4F: "3",
        0x66: "4",
        0x6D: "5",
        0x7D: "6",
        0x07: "7",
        0x7F: "8",
        0x6F: "9",
        0x00: " ",
    }
    if value in decode_map:
        return decode_map[value]
    return "?"


class SimonDriver:
    def __init__(self, dut, clock):
        self._dut = dut
        self._clock = clock
        self._dut.btn.value = 0
        self._dut.seginv.value = 0

    async def press_button(self, index):
        """Press a button for 100 clock cycle, index is zero based"""
        self._dut.btn.value = 1 << index
        await ClockCycles(self._clock, 100)
        self._dut.btn.value = 0
        await ClockCycles(self._clock, 100)

    async def read_one_led(self):
        """Returns the index of the currently lit LED, or None if no LED is lit"""
        leds = self._dut.led.value.integer
        if leds == 0b0000:
            return None
        elif leds == 0b0001:
            return 0
        elif leds == 0b0010:
            return 1
        elif leds == 0b0100:
            return 2
        elif leds == 0b1000:
            return 3
        raise ValueError(f"Unexpected value for leds: {self._dut.led.value}")

    async def wait_for_led(self):
        """Wait until one of the LEDs is lit"""
        while await self.read_one_led() is None:
            await Edge(self._dut.led)

    async def wait_for_leds_off(self):
        """Wait until all LEDs are off"""
        while await self.read_one_led() is not None:
            await Edge(self._dut.led)

    async def read_segments(self):
        """Read the current segment value"""
        diginv = 0x7F if self._dut.seginv.value.integer else 0
        if self._dut.seginv.value.integer:
            await RisingEdge(self._dut.dig1)
        else:
            await FallingEdge(self._dut.dig1)
        await Timer(10, units="ns")
        dig1 = decode_7seg(self._dut.seg.value.integer ^ diginv)
        if self._dut.seginv.value.integer:
            await RisingEdge(self._dut.dig2)
        else:
            await FallingEdge(self._dut.dig2)
        await Timer(10, units="ns")
        dig2 = decode_7seg(self._dut.seg.value.integer ^ diginv)
        return f"{dig1}{dig2}"


@cocotb.test()
async def test_simon(dut):
    dut._log.info("start")
    clock = Clock(dut.clk, 20, units="us")  # 50 kHz clock
    ticks_per_ms = 50  # Clock ticks per millisecond (at 50 kHz)
    cocotb.start_soon(clock.start())

    simon = SimonDriver(dut, dut.clk)

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 100)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)

    # Should display empty score before game starts
    assert await simon.read_segments() == "  "

    # Press some button to start the game
    await simon.press_button(0)

    # Wait 510ms for the game to be started
    await ClockCycles(dut.clk, 510 * ticks_per_ms)

    assert await simon.read_segments() == "00"
    initial_led_index = await simon.read_one_led()
    assert initial_led_index in [0, 1, 2, 3]
    dut._log.info(f"Initial LED index: {initial_led_index}")

    # Wait 300ms for the LED to go off
    await ClockCycles(dut.clk, 300 * ticks_per_ms)
    assert await simon.read_one_led() is None

    # Wait another 100ms for the game to be ready for input
    await ClockCycles(dut.clk, 100 * ticks_per_ms)

    # Press the correct button, check the the LED is lit
    await simon.press_button(initial_led_index)
    assert await simon.read_one_led() == initial_led_index

    # Wait for 310ms for the input to be registered
    await ClockCycles(dut.clk, 310 * ticks_per_ms)
    assert await simon.read_one_led() is None

    # Check that the score is updated
    assert await simon.read_segments() == "01"

    # Invert the segment polarity, check the the score is still appearing correctly
    dut.seginv.value = 1
    await ClockCycles(dut.clk, 1)
    assert await simon.read_segments() == "01"


@cocotb.test()
async def test_long_game_sequence(dut):
    dut._log.info("Start")
    clock = Clock(dut.clk, 20, units="us")  # 50 kHz clock
    ticks_per_ms = 50  # Clock ticks per millisecond (at 50 kHz)
    cocotb.start_soon(clock.start())

    simon = SimonDriver(dut, dut.clk)

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 100)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 1)

    # Should display empty score before game starts
    assert await simon.read_segments() == "  "

    # Press some button to start the game
    await simon.press_button(0)

    # Wait 510ms for the game to be started
    await ClockCycles(dut.clk, 510 * ticks_per_ms)

    sequence = []

    for i in range(GAME_SEQUENCE_TEST_LENGTH):
        dut._log.info(f"Testing round {i + 1}")

        assert await simon.read_segments() == f"{i:02}"

        # Compare the sequence with the LEDs
        for i in range(len(sequence)):
            led_index = await simon.read_one_led()
            assert led_index == sequence[i]
            await simon.wait_for_leds_off()
            await simon.wait_for_led()

        led_index = await simon.read_one_led()
        sequence.append(led_index)

        # Wait for the LED to go off
        await ClockCycles(dut.clk, 310 * ticks_per_ms)
        assert await simon.read_one_led() is None

        for i in range(len(sequence)):
            # Wait another 100ms for the game to be ready for input
            await ClockCycles(dut.clk, 100 * ticks_per_ms)
            await simon.press_button(sequence[i])
            assert await simon.read_one_led() == sequence[i]
            # Wait for 310ms for the input to be registered
            await ClockCycles(dut.clk, 310 * ticks_per_ms)
            assert await simon.read_one_led() is None

        # Wait for the next round (until one LED is lit)
        await simon.wait_for_led()


# Skipped by default, as it takes a long time to run. To run it, use:
#
#     make TESTCASE=test_pseudo_randomness
@cocotb.test(skip=True)
async def test_pseudo_randomness(dut):
    dut._log.info("start")
    clock = Clock(dut.clk, 20, units="us")  # 50 kHz clock
    ticks_per_ms = 50  # Clock ticks per millisecond (at 50 kHz)
    cocotb.start_soon(clock.start())

    simon = SimonDriver(dut, dut.clk)

    # Reset
    dut.ena.value = 1
    dut.uio_in.value = 0

    led_bins = [0, 0, 0, 0]

    def normalize_bins(bins):
        return [count / sum(bins) for count in bins]

    def format_bins(bins):
        return "[" + ", ".join([f"{count:.2f}" for count in normalize_bins(bins)]) + "]"

    for i in range(500):
        dut.rst_n.value = 0
        await ClockCycles(dut.clk, 100)
        dut.rst_n.value = 1
        await ClockCycles(dut.clk, 1)

        await ClockCycles(dut.clk, i * ticks_per_ms)

        # Press some button to start the game
        await simon.press_button(0)

        # Wait 510ms for the game to be started
        await ClockCycles(dut.clk, 510 * ticks_per_ms)
        led_index = await simon.read_one_led()
        assert led_index in [0, 1, 2, 3]
        led_bins[led_index] += 1
        dut._log.info(
            f"Iteration: {i}, LED index: {led_index}, bins: {format_bins(led_bins)}"
        )

    dut._log.info(f"LED bins: {format_bins(led_bins)} (raw: {led_bins})")
    assert all(0.2 <= count <= 0.3 for count in normalize_bins(led_bins))

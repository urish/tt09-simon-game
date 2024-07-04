# SPDX-FileCopyrightText: © 2023 Uri Shaked <uri@wokwi.com>
# SPDX-License-Identifier: MIT

import cocotb
from cocotb.clock import Clock, Timer
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge


def decode_7seg(value: int):
    """ Decode a 7-segment value to a digit """
    decode_map = {
        0x3f: "0",
        0x06: "1",
        0x5b: "2",
        0x4f: "3",
        0x66: "4",
        0x6d: "5",
        0x7d: "6",
        0x07: "7",
        0x7f: "8",
        0x6f: "9",
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
        """ Press a button for 100 clock cycle, index is zero based """
        self._dut.btn.value = 1 << index
        await ClockCycles(self._clock, 100)
        self._dut.btn.value = 0
        await ClockCycles(self._clock, 100)

    async def read_one_led(self):
        """ Returns the index of the currently lit LED, or None if no LED is lit """
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

    async def read_segments(self):
        """ Read the current segment value """
        diginv = 0x7f if self._dut.seginv.value.integer else 0
        if self._dut.seginv.value.integer:
            await RisingEdge(self._dut.dig1)
        else:
            await FallingEdge(self._dut.dig1)
        await Timer(10, units='ns')
        dig1 = decode_7seg(self._dut.seg.value.integer ^ diginv)
        if self._dut.seginv.value.integer:
            await RisingEdge(self._dut.dig2)
        else:
            await FallingEdge(self._dut.dig2)
        await Timer(10, units='ns')
        dig2 = decode_7seg(self._dut.seg.value.integer ^ diginv)
        return f"{dig1}{dig2}"


@cocotb.test()
async def test_simon(dut):
    dut._log.info("start")
    clock = Clock(dut.clk, 20, units="us") # 50 kHz clock
    ticks_per_ms = 50 # Clock ticks per millisecond (at 50 kHz)
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

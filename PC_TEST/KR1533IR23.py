#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR1533IR23.py — functional tester for the KR1533IR23 (KA1533IR23)
(DIP-20, equivalent of SN74ALS374A / 74ALS374, TI datasheet SDAS167C).

Octal D-type edge-triggered flip-flop with 3-state outputs.

Pinout (top view):
  1  - ~OE (output enable, active low)             20 - VCC (+5 V)
  2  - Q0                                          19 - Q7
  3  - 1D                                          18 - 8D
  4  - 2D                                          17 - 7D
  5  - Q1                                          16 - Q6
  6  - Q2                                          15 - Q5
  7  - 3D                                          14 - 6D
  8  - 4D                                          13 - 5D
  9  - Q3                                          12 - Q4
  10 - GND                                         11 - CLK (clock, rising edge)

Input-to-output mapping: nD -> Q(n-1), i.e.
  channel 0: 1D (pin 3)  -> Q0 (pin 2)
  channel 1: 2D (pin 4)  -> Q1 (pin 5)
  channel 2: 3D (pin 7)  -> Q2 (pin 6)
  channel 3: 4D (pin 8)  -> Q3 (pin 9)
  channel 4: 5D (pin 13) -> Q4 (pin 12)
  channel 5: 6D (pin 14) -> Q5 (pin 15)
  channel 6: 7D (pin 17) -> Q6 (pin 16)
  channel 7: 8D (pin 18) -> Q7 (pin 19)

Function table (per flip-flop):
  ~OE | CLK        | D | Q
  ----+------------+---+-----
   L  | 0 -> 1     | H | H
   L  | 0 -> 1     | L | L
   L  | H or L     | X | Q0 (hold)
   H  | X          | X | Z  (outputs disabled)

Operation:
  * Data is latched ONLY on the positive transition of CLK (0 -> 1).
    This is NOT a transparent latch (not 1533IR22 / 74ALS373): while CLK is
    not transitioning, the outputs do not change.
  * ~OE does not affect the internal flip-flops. New data can be clocked in
    while the outputs are disabled, then read back after ~OE=0.
  * In the Z state the external pull-ups make a read line return logic 1.

Usage:
    python KR1533IR23.py                  # full test, port COM11 by default
    python KR1533IR23.py --port COM7      # choose the port explicitly
    python KR1533IR23.py --quick          # skip the 0x00..0xFF sweep
    python KR1533IR23.py -v               # print every value
    python KR1533IR23.py --diagnose 0     # diagnose channel 0 (D input, Q line, Q output)
    python KR1533IR23.py --check-lines    # test every rig line (remove the IC first)
    python KR1533IR23.py --mask 0x81      # exclude the faulty channels Q0 and Q7

Diagnostic pipeline for a faulty channel:
    1. --check-lines   — confirm the rig lines are good (IC removed);
    2. --diagnose N    — for channel N, separate a rig fault from an IC fault;
    3. --mask ...      — test the rest of the IC without wasting time on a dead channel.

Bit convention: the value is 8-bit, bit i corresponds to channel i,
i.e. bit 0 -> Q0, ..., bit 7 -> Q7.

Note on --mask: the mask is ALWAYS supplied manually and is never derived
automatically from the results — otherwise a faulty IC would hide itself.
"""

import argparse
import os
import sys

import serial.tools.list_ports

import base_test
from arduino_to_pins import pin20
from base_test import TestSimplController, check
from simpl_macros import OUTPUT_MODE, INPUT_PULLUP_MODE, INPUT_MODE

# Arduino Mega port of the test-socket controller
DEFAULT_PORT = "COM11"
COM_BAUD = 2000000

# --- DIP-20 pinout: list order = pin numbers 1..20 ---
pins = [
    "~OE",  # 1  output enable (active low)
    "Q0",  # 2
    "D0",  # 3  1D
    "D1",  # 4  2D
    "Q1",  # 5
    "Q2",  # 6
    "D2",  # 7  3D
    "D3",  # 8  4D
    "Q3",  # 9
    "GND",  # 10
    "CLK",  # 11 clock input (rising edge)
    "Q4",  # 12
    "D4",  # 13 5D
    "D5",  # 14 6D
    "Q5",  # 15
    "Q6",  # 16
    "D6",  # 17 7D
    "D7",  # 18 8D
    "Q7",  # 19
    "VCC",  # 20
]

# Cross-check table of pin numbers — guards against a typo in the list above
_PIN_CHECK = {
    1: "~OE", 2: "Q0", 3: "D0", 4: "D1", 5: "Q1", 6: "Q2", 7: "D2",
    8: "D3", 9: "Q3", 10: "GND", 11: "CLK", 12: "Q4", 13: "D4", 14: "D5",
    15: "Q5", 16: "Q6", 17: "D6", 18: "D7", 19: "Q7", 20: "VCC",
}

if len(pins) != 20:
    raise RuntimeError("pins must contain 20 pins (DIP-20)")
if len(set(pins)) != 20:
    raise RuntimeError("pins contains duplicates")
for _pin, _name in _PIN_CHECK.items():
    if pins[_pin - 1] != _name:
        raise RuntimeError(
            f"pinout: pin {_pin} = {pins[_pin - 1]!r}, expected {_name!r}"
        )

# Bit i -> channel i
D_PINS = [pin20[pins.index(f"D{i}")] for i in range(8)]
Q_PINS = [pin20[pins.index(f"Q{i}")] for i in range(8)]

VCC_PIN = pin20[pins.index("VCC")]
GND_PIN = pin20[pins.index("GND")]
CLK_PIN = pin20[pins.index("CLK")]
OE_PIN = pin20[pins.index("~OE")]

# Every pin of the IC under test: used to bring it to a safe state
ALL_PINS = [pin20[pins.index(name)] for name in pins]

# A single SIMPL command reads all eight outputs at once: "16diq18diq..."
READ_CMD = "".join(f"{p}diq" for p in Q_PINS)

# Maximum length of one SIMPL command in the firmware (txtRead(buf, 255))
CMD_LIMIT = 240

# Delays for the ALS family (tsu = 10 ns, th = 0..4 ns, tw = 14 ns).
# 20 us on this rig covers those requirements with a huge margin, and holding
# the data on the inputs while clocking is mandatory.
SETUP_DELAY = "20u"
HOLD_DELAY = "20u"
# Pause before reading the outputs: covers switching out of Z (tPZH/tPZL
# <= 21 ns), the propagation delay (tPLH/tPHL <= 17 ns) and the settling of
# the rig wiring.
SETTLE_DELAY = "100u"


def expected_bits(value):
    """Expected Q0..Q7 string for a written byte (bit 0 — Q0)."""
    return bytes([ord("1") if (value >> bit) & 1 else ord("0") for bit in range(8)])


def mask_bits(data, mask):
    """Replace the characters at positions where a mask bit is 1 with '*'.

    Used to localise a faulty channel: a masked channel is excluded from the
    comparison, while all remaining channels are checked strictly.
    """
    out = bytearray(data)
    for bit in range(8):
        if (mask >> bit) & 1:
            out[bit] = ord("*")
    return bytes(out)


def masked_check(actual, expected, mask, value):
    """Compare while honouring the mask of faulty channels."""
    if mask == 0:
        check(actual, expected)
        return
    a, e = mask_bits(actual, mask), mask_bits(expected, mask)
    if a != e:
        print(
            f"FAILED!!! {value:02X}h actual: {actual!r} expected: {expected!r} "
            f"(mask {mask:02X}h)",
            file=sys.stderr,
        )
        raise SystemExit(1)


def bits_to_byte(data):
    """Inverse conversion: the Q0..Q7 string -> number."""
    value = 0
    for bit, ch in enumerate(data):
        if ch == ord("1"):
            value |= 1 << bit
    return value


class TestKR1533IR23(TestSimplController):
    #: Bit mask of channels excluded from the comparison (for a faulty IC).
    #: 0 — all eight channels are checked.
    mask = 0

    def __init__(self, port=DEFAULT_PORT, quiet=False):
        # The port is passed through the base_test module; base_test.py itself
        # is not modified.
        base_test.COM_PORT = port
        self.port = port
        if not quiet:
            print(f"[i] IC: KR1533IR23 (DIP-20), port {port}")
        super().__init__()

        # 1) Every IC pin to high impedance, power removed
        self.send_command("".join(f"{p}d{INPUT_MODE}" for p in ALL_PINS))

        # 2) Control inputs to their passive state: CLK = 0,
        #    ~OE = 1 (outputs disabled), data = 0
        cmd = f"{CLK_PIN}d{OUTPUT_MODE}0o" f"{OE_PIN}d{OUTPUT_MODE}1o"
        cmd += "".join(f"{p}d{OUTPUT_MODE}0o" for p in D_PINS)
        self.send_command(cmd)

        # 3) Power-up: ground first, then +5 V
        self.send_command(f"{GND_PIN}d{OUTPUT_MODE}0o")
        self.send_command(f"{VCC_PIN}d{OUTPUT_MODE}1o")

        # 4) Outputs Q0..Q7 as inputs with pull-up (in the Z state they read 1)
        self.send_command("".join(f"{p}d{INPUT_PULLUP_MODE}" for p in Q_PINS))

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------
    def set_data(self, value):
        """Drive the byte onto inputs D0..D7 (bit i -> Di -> Qi)."""
        self.send_command(
            "".join(
                f"{pin}d{OUTPUT_MODE}{(value >> bit) & 1}o"
                for bit, pin in enumerate(D_PINS)
            )
        )

    def clock_pulse(self):
        """One clock cycle: a guaranteed positive transition of CLK (0 -> 1).

        CLK is first forced low so that the transition does not depend on the
        previous state of the line; the data on inputs D must already be set
        by this point.
        """
        return self.send_command(
            f"{CLK_PIN}d{OUTPUT_MODE}0o"
            + SETUP_DELAY
            + f"{CLK_PIN}h"
            + SETUP_DELAY
            + f"{CLK_PIN}l"
            + HOLD_DELAY
        )

    def write_byte(self, value, prev_value=None):
        """Write a byte: data -> CLK pulse, in a single SIMPL command.

        prev_value — the previous value on inputs D; when it is known and equal,
        sending the data is skipped (the inputs already hold it).
        Returns the written value.
        """
        data_cmd = ""
        if prev_value is None or ((prev_value ^ value) & 0xFF):
            data_cmd = "".join(
                f"{pin}d{OUTPUT_MODE}{(value >> bit) & 1}o"
                for bit, pin in enumerate(D_PINS)
            )

        self.send_command(
            data_cmd
            # Force the initial CLK=0 level so that the next transition is
            # exactly 0 -> 1 (the data is already set at this point)
            + f"{CLK_PIN}d{OUTPUT_MODE}0o"
            + "1m"
            + f"{CLK_PIN}h"
            + SETUP_DELAY
            + f"{CLK_PIN}l"
            + HOLD_DELAY
        )
        return value

    def set_output_enable(self, enabled):
        """~OE=0 — outputs active, ~OE=1 — high-impedance state (Z)."""
        self.send_command(f"{OE_PIN}d{OUTPUT_MODE}{0 if enabled else 1}o")

    def read_outputs(self):
        """Read Q0..Q7. Returns a byte string of 8 characters '0'/'1'."""
        return self.send_command(f"{SETTLE_DELAY}" + READ_CMD)

    def read_byte(self):
        """Read Q0..Q7 as a number."""
        return bits_to_byte(self.read_outputs())

    def __del__(self):
        # Safe state: every pin to input first (which removes power), then the
        # normal cleanup through the base class.
        try:
            if getattr(self, "_ser", None) is not None:
                self.send_command("".join(f"{p}d{INPUT_MODE}" for p in ALL_PINS))
        except Exception as e:
            print(f"Safe state error: {e}")
        super().__del__()


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------
def expect_q(uc, value, result):
    """Compare the value read against the expected one, honouring the channel mask."""
    masked_check(result, expected_bits(value), uc.mask, value)


def test_reference_levels(uc):
    """Test 0: rig sanity — active 0 and 1 on the outputs are read correctly."""
    print("=== Test 0: rig reference levels ===")
    uc.set_output_enable(True)

    uc.write_byte(0x00)
    expect_q(uc, 0x00, uc.read_outputs())

    uc.write_byte(0xFF, prev_value=0x00)
    expect_q(uc, 0xFF, uc.read_outputs())
    print("OK")


def test_walking(uc):
    """Test 1: walking one, walking zero and checkerboard codes."""
    print("=== Test 1: walking one/zero and checkerboard codes ===")
    uc.set_output_enable(True)

    scenarios = [
        ("Walking one", [1 << i for i in range(8)]),
        ("Walking zero", [0xFF ^ (1 << i) for i in range(8)]),
        ("0xAA", [0xAA]),
        ("0x55", [0x55]),
        ("0x0F", [0x0F]),
        ("0xF0", [0xF0]),
    ]

    prev = None
    for name, values in scenarios:
        print(f"--- {name} ---")
        for value in values:
            prev = uc.write_byte(value, prev_value=prev)
            result = uc.read_outputs()
            print(f"Write {value:02X}h -> Q0..Q7 = {result.decode()}")
            expect_q(uc, value, result)

    print("OK")


def test_hold(uc):
    """Test 2: a flip-flop, not a latch — data passes only on a CLK edge.

    Three properties are checked:
      * while CLK=0, changing the data on inputs D does not change the register;
      * while CLK is held at 1, changing the data does not change the register
        either — this is exactly what distinguishes a flip-flop from a
        transparent latch (1533IR22/74ALS373);
      * a positive transition 0 -> 1 latches the data present on the inputs at
        that moment; a negative transition 1 -> 0 latches nothing.

    Important: the "data did not pass" check is done BEFORE the edge is applied.
    As soon as a 0 -> 1 transition is applied to CLK, the flip-flop must latch
    the current data — that is correct behaviour, not a fault.
    """
    print("=== Test 2: edge triggering (no transparency) ===")
    uc.set_output_enable(True)

    def clk(level):
        """Set the CLK level and let the lines settle."""
        uc.send_command(f"{CLK_PIN}d{OUTPUT_MODE}{level}o")
        uc.send_command("1m")

    def check(label, expected):
        """Read the outputs and compare them with the expected register content."""
        result = uc.read_outputs()
        expect_q(uc, expected, result)
        print(f"  {label:58s} Q = {result.decode()}")

    def pulse_and_check(value, label):
        """Clock the value in and verify the result."""
        uc.set_data(value)
        uc.clock_pulse()
        check(label, value)

    # Preparation: CLK=0, register guaranteed to be 0x00
    clk(0)
    pulse_and_check(0x00, "preparation: 00h clocked in")

    # --- 1. With CLK=0 a data change does NOT pass (checked before the edge) ---
    uc.set_data(0x5A)
    check("D=5Ah with CLK=0, no edge applied", 0x00)
    uc.set_data(0xA5)
    check("D=A5h with CLK=0, no edge applied", 0x00)

    # --- 2. A positive transition latches the data ---
    uc.clock_pulse()
    check("after the 0 -> 1 edge (A5h latched)", 0xA5)

    # --- 3. Again, with CLK=0 a data change does not pass ---
    uc.set_data(0x3C)
    check("D=3Ch with CLK=0, no edge applied", 0xA5)

    # --- 4. Key transparency check: CLK is held at 1 ---
    uc.set_data(0x5A)
    clk(1)
    check("CLK=1, data still 5Ah (edge occurred at 5Ah)", 0x5A)
    uc.set_data(0x00)
    check("D=00h with CLK=1, no transparency", 0x5A)
    uc.set_data(0xFF)
    check("D=FFh with CLK=1, no transparency", 0x5A)
    uc.set_data(0x3C)
    check("D=3Ch with CLK=1, no transparency", 0x5A)

    # --- 5. A negative transition 1 -> 0 latches nothing ---
    clk(0)
    check("after the 1 -> 0 edge (latches nothing)", 0x5A)

    # --- 6. Data already present at CLK=0: the edge latches exactly that ---
    pulse_and_check(0x3C, "after the 0 -> 1 edge (3Ch latched)")

    # --- 7. Repeat, to confirm reproducibility ---
    uc.set_data(0x96)
    check("D=96h with CLK=0, no edge applied", 0x3C)
    uc.clock_pulse()
    check("after the 0 -> 1 edge (96h latched)", 0x96)

    # --- 8. Two consecutive edges latch two different values ---
    uc.set_data(0x69)
    uc.clock_pulse()
    check("first edge (69h latched)", 0x69)
    uc.set_data(0xC3)
    uc.clock_pulse()
    check("second edge (C3h latched)", 0xC3)
    uc.set_data(0x00)
    check("D=00h with CLK=0, no edge applied", 0xC3)

    print("OK")


def test_output_enable(uc):
    """Test 3: the third state (~OE=1 -> Z, ~OE=0 -> active levels)."""
    print("=== Test 3: third state (~OE) ===")
    uc.set_output_enable(True)
    uc.write_byte(0x00)
    expect_q(uc, 0x00, uc.read_outputs())

    # Disable the outputs: the pull-ups must give all ones
    uc.set_output_enable(False)
    expect_q(uc, 0xFF, uc.read_outputs())
    print("  ~OE=1 -> Z, all ones via pull-ups: OK")

    # Re-enable the outputs — the internal register data is preserved
    uc.set_output_enable(True)
    expect_q(uc, 0x00, uc.read_outputs())
    print("  ~OE=0 -> data preserved: OK")

    # 0x80 also reads as all ones in Z (no output pin is pulled to 0)
    uc.write_byte(0x80, prev_value=0x00)
    uc.set_output_enable(False)
    expect_q(uc, 0xFF, uc.read_outputs())
    uc.set_output_enable(True)
    expect_q(uc, 0x80, uc.read_outputs())
    print("  0x80 in Z reads as 0xFF, and as 0x80 once enabled: OK")

    # ~OE does not control writing: data can be clocked in while outputs are off
    uc.set_output_enable(False)
    uc.write_byte(0x3C, prev_value=0x80)
    expect_q(uc, 0xFF, uc.read_outputs())
    uc.set_output_enable(True)
    expect_q(uc, 0x3C, uc.read_outputs())
    print("  write with ~OE=1, read back after ~OE=0: OK")

    print("OK")


def reverse_bits8(value):
    """Reverse the bit order in a byte: 0b10000000 -> 0b00000001."""
    result = 0
    for bit in range(8):
        if (value >> bit) & 1:
            result |= 1 << (7 - bit)
    return result


def gray_code8(index):
    """Gray code: any two consecutive values differ in exactly one bit."""
    return index ^ (index >> 1)


def first_mismatch(actual, expected):
    """Channel numbers where the value read did not match the expected one.

    For example [1, 6] — this points directly at the specific IC pins and rig
    lines that need checking.
    """
    return [bit + 1 for bit in range(8) if actual[bit] != expected[bit]]


def sweep_once(uc, values, name, verbose=False):
    """One sweep pass: apply every value in the given order."""
    print(f"--- {name} ---")
    prev = None
    for index, value in enumerate(values):
        prev = uc.write_byte(value, prev_value=prev)
        result = uc.read_outputs()
        if verbose:
            print(f"Write {value:02X}h -> Q0..Q7 = {result.decode()}")
        expected = expected_bits(value)
        if mask_bits(result, uc.mask) != mask_bits(expected, uc.mask):
            bad = first_mismatch(result, expected)
            print(
                f"FAILED!!! {value:02X}h: read {result.decode()}, "
                f"expected {expected.decode()}, mismatched channels: "
                + ", ".join(f"Q{n}" for n in bad),
                file=sys.stderr,
            )
            raise SystemExit(1)
        if not verbose and (index + 1) % 64 == 0:
            print(f"  ... {index + 1}/256 (up to {value:02X}h)")


def test_full_sweep(uc, verbose=False):
    """Test 4: exhaustive sweep of all 256 codes in three different orders.

    Random values are unnecessary: a sweep by definition covers every 8-bit
    combination. The different orders give extra confidence because they load
    the transitions between neighbouring codes differently:

      * ascending — the low-order bits toggle one after another;
      * bit-reversed — the same codes in a mirrored sequence;
      * Gray code — between any two neighbouring codes exactly one bit changes,
        which is convenient for spotting crosstalk between channels.
    """
    print("=== Test 4: sweep of all 256 codes ===")
    uc.set_output_enable(True)

    sweep_once(uc, range(256), "ascending 00h..FFh", verbose)
    sweep_once(
        uc,
        (reverse_bits8(v) for v in range(256)),
        "bit-reversed order",
        verbose,
    )
    sweep_once(
        uc,
        (gray_code8(v) for v in range(256)),
        "Gray code (one bit per step)",
        verbose,
    )

    print("  total: 3 passes x 256 values = 768 checks")
    print("OK")


def run_all(uc, verbose=False):
    test_reference_levels(uc)
    test_walking(uc)
    test_hold(uc)
    test_output_enable(uc)
    test_full_sweep(uc, verbose=verbose)
    print("ALL OK")


def check_rig_lines(uc):
    """Test EVERY rig line independently of the IC.

    Drives a rig pin as an output, runs 0 -> 1 -> 0 and reads it back. If a line
    does not toggle, the rig (driver/socket) is faulty, not the IC.
    Remove the IC before running this, otherwise the readings depend on its
    output drivers.
    """
    print("=== Rig line check (better with the IC removed) ===")
    uc.send_command("".join(f"{p}d{INPUT_MODE}" for p in ALL_PINS))

    bad = []
    for name in pins:
        p = pin20[pins.index(name)]
        got = []
        for level in (0, 1, 0):
            uc.send_command(f"{p}d{OUTPUT_MODE}{level}o")
            uc.send_command("500u")
            r = uc.send_command(f"{p}diq")
            got.append((r or b"?").decode(errors="replace"))
        ok = got == ["0", "1", "0"]
        if not ok:
            bad.append(name)
        print(
            f"  pin {pins.index(name) + 1:2d} {name:4s} (Arduino {p:2d}): "
            f"0->{got[0]} 1->{got[1]} 0->{got[2]}  {'OK' if ok else '<<< FAULTY'}"
        )

    uc.send_command("".join(f"{p}d{INPUT_MODE}" for p in ALL_PINS))
    if bad:
        print(f"RESULT: faulty lines: {', '.join(bad)}")
        if "GND" in bad or "VCC" in bad:
            print(
                "[i] GND/VCC often 'fail' this test while the IC is still in the\n"
                "    socket: the powered IC holds those rails. Remove the IC and\n"
                "    re-run --check-lines to test them properly."
            )
        return False
    print("RESULT: all rig lines are good")
    return True


def diagnose_channel(uc, bit):
    """Localise a fault in one channel: the D input, the Q line or the IC.

    Returns one of: 'ok', 'data-line', 'output-line', 'chip'.
    """
    q_name = f"Q{bit}"
    d_name = f"D{bit}"
    print(
        f"=== Channel {bit} diagnosis: {d_name} (pin {pins.index(d_name) + 1}, "
        f"Arduino {D_PINS[bit]}), {q_name} (pin {pins.index(q_name) + 1}, "
        f"Arduino {Q_PINS[bit]}) ==="
    )

    # Initial state: outputs disabled
    uc.set_output_enable(False)

    # 1. What does input D read with an external 0 and 1?
    uc.send_command(f"{D_PINS[bit]}d{INPUT_PULLUP_MODE}")
    uc.send_command("1m")
    d0 = uc.send_command(f"{D_PINS[bit]}d{OUTPUT_MODE}0o" f"1m" f"{D_PINS[bit]}diq")
    d1 = uc.send_command(f"{D_PINS[bit]}d{OUTPUT_MODE}1o" f"1m" f"{D_PINS[bit]}diq")
    d_ok = d0 == b"0" and d1 == b"1"
    print(
        f"  input {d_name}: external 0 -> {d0!r}, external 1 -> {d1!r}  "
        f"{'OK' if d_ok else '<<< FAULTY'}"
    )

    # 2. Can the rig itself toggle the Q output line (is the driver good)?
    q_drive = []
    for level in (0, 1, 0):
        uc.send_command(f"{Q_PINS[bit]}d{OUTPUT_MODE}{level}o")
        uc.send_command("500u")
        q_drive.append((uc.send_command(f"{Q_PINS[bit]}diq") or b"?").decode(errors="replace"))
    q_line_ok = q_drive == ["0", "1", "0"]
    print(
        f"  line {q_name} driven by the rig: {q_drive}  "
        f"{'OK' if q_line_ok else '<<< RIG LINE FAULTY'}"
    )

    # 3. Clock 0x00 and 0xFF into the register and look at the output
    uc.send_command(f"{Q_PINS[bit]}d{INPUT_PULLUP_MODE}")
    uc.set_output_enable(True)
    seen = {}
    for value in (0x00, 0xFF):
        uc.set_data(value)
        uc.clock_pulse()
        seen[value] = uc.send_command("200u" + f"{Q_PINS[bit]}diq")
    q_ok = seen[0x00] == b"0" and seen[0xFF] == b"1"
    print(
        f"  output {q_name}: register 0x00 -> {seen[0x00]!r}, 0xFF -> {seen[0xFF]!r}  "
        f"{'OK' if q_ok else '<<< FAULTY'}"
    )

    if d_ok and q_line_ok and q_ok:
        verdict = "ok"
    elif not q_line_ok:
        verdict = "output-line"
    elif not d_ok:
        verdict = "data-line"
    else:
        verdict = "chip"

    notes = {
        "ok": "channel is good",
        "data-line": "input D does not toggle — the rig is faulty",
        "output-line": "line Q is not toggled by the rig — the rig is faulty",
        "chip": "the input is good and the line is good, but the output does not "
                "follow the register — the IC is faulty or the Q pin has no "
                "contact in the socket",
    }
    print(f"  VERDICT: {notes[verdict]}")
    return verdict


def main(argv=None):
    parser = argparse.ArgumentParser(description="KR1533IR23 (DIP-20) tester")
    parser.add_argument("--port", default=DEFAULT_PORT, help="Arduino port (COM11 by default)")
    parser.add_argument("--list-ports", action="store_true", help="list the available ports and exit")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="skip the 0x00..0xFF sweep (fast tests only)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print every written/read value",
    )
    parser.add_argument(
        "--mask",
        default="0x00",
        help="mask of faulty channels (hex, e.g. 0x01 excludes Q0)",
    )
    parser.add_argument(
        "--diagnose",
        metavar="N",
        type=int,
        help="diagnose channel N (0..7): D input, Q line, Q output",
    )
    parser.add_argument(
        "--check-lines",
        action="store_true",
        help="test every rig line (better with the IC removed)",
    )
    args = parser.parse_args(argv)

    port_names = [p.device for p in serial.tools.list_ports.comports()]
    if args.list_ports:
        print("Available ports:", port_names)
        return 0

    if args.diagnose is not None and not 0 <= args.diagnose <= 7:
        print("[!] --diagnose accepts 0..7", file=sys.stderr)
        return 2

    print(f"Available ports: {port_names}")
    if args.port not in port_names:
        print(
            f"[!] Port {args.port} not found. Pass the correct one via --port",
            file=sys.stderr,
        )
        return 2

    uc = TestKR1533IR23(port=args.port)

    if args.check_lines:
        return 0 if check_rig_lines(uc) else 1

    if args.diagnose is not None:
        return 0 if diagnose_channel(uc, args.diagnose) == "ok" else 1

    uc.mask = int(args.mask, 0)
    if uc.mask:
        bad = [f"Q{i}" for i in range(8) if (uc.mask >> i) & 1]
        print(f"[!] Channels excluded from the check: {', '.join(bad)} (mask {uc.mask:#04x})")

    if args.quick:
        # Quick mode: no 256-code sweep — keeps the reference levels, the
        # walking codes, the clocking check and the third state.
        test_reference_levels(uc)
        test_walking(uc)
        test_hold(uc)
        test_output_enable(uc)
        print("ALL OK (quick, without the 0x00..0xFF sweep)")
    else:
        run_all(uc, verbose=args.verbose)

    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Z80.py — functional tester for the Zilog Z80 microprocessor (DIP-40)
based on Mega-IC-Tester (PC mode, SIMPL).

Idea
====
The tester has no memory of its own: the host PC **is the bus**.
The ZIF-40 pins are driven one at a time through the Arduino, so the PC acts
as the clock generator, the memory, and the I/O devices:

  * CLK      — generated manually: each "tick" is a rise and a fall;
  * A0..A15  — read entirely by one SIMPL command (one round-trip);
  * D0..D7   — driven to the chip when it requests a read;
  * MREQ/RD/WR/M1/RFSH/IORQ/HALT — read together with the address.

Single-tick algorithm:

  1. raise CLK and, with two identical commands, read the whole address +
     control (two matching samples confirm reliability);
  2. drive the byte from "memory" or release the data bus, and only
     THEN lower CLK.

The order in step 2 is essential. The firmware changes the 8 data pins one
at a time (8 separate `o` commands, about 280 us), so driving the byte
after the falling edge of the tick would leave only ~40 us until the latching
edge — and the Z80 would periodically catch a half-assembled value (for
example, 6Bh instead of 6Fh). Driving it in advance gives nearly a whole
tick of margin.
Because of the low frequency (on the order of 1 kHz), the Z80 operates as a
fully static device, and the host has time to respond to every machine
cycle. This makes it possible to execute **real programs** on the Z80 and
observe the result on the address bus.

How the result is verified
=========================
The internal registers of the Z80 are not visible from outside, so a trick
is used: "output the result onto the address bus":

    LD  H, 02h
    LD  L, A
    JP  (HL)        ; the next fetch will be at address 0200h + A

Thus, by looking at which address the CPU fetched the next byte from, one can
determine the register contents. This provides a genuine test of the ALU, the
registers, the flags, the conditional jumps, and the entire 16-bit address bus.

Data bus safety
================
The Arduino must NEVER hold the data bus as an output while the Z80 is
driving it (memory/port write cycles) — otherwise two drivers would be
enabled against each other. Therefore:

  * the byte is driven only while (MREQ&RD) or (IORQ&RD) is active;
  * when a write cycle is detected (MREQ&WR or IORQ&WR), the data bus is
    released immediately and the run stops;
  * all tests in this file use read-only programs
    (NOP, LD r,n, LD rr,nn, LD A,(nn), ALU, JP, JR, HALT) — no write
    cycles occur at all.

The project's existing files are not modified: the module only imports
base_test / arduino_to_pins / simpl_macros.

Usage
======
    python Z80.py                  # the full test suite
    python Z80.py --port COM11     # specify the port explicitly
    python Z80.py --monitor        # just observe the bus state
    python Z80.py --test alu       # run a single test
"""

import argparse
import sys

import base_test
from arduino_to_pins import pin40
from base_test import TestSimplController
from simpl_macros import INPUT_MODE, INPUT_PULLUP_MODE, OUTPUT_MODE

DEFAULT_PORT = "COM11"

# ---------------------------------------------------------------------------
# Z80 pinout (DIP-40). The order of the elements = the chip pin number,
# i.e. the position in the ZIF-40. Value = Arduino pin from arduino_to_pins.pin40.
# ---------------------------------------------------------------------------
Z80_SIGNALS = [
    "A11", "A12", "A13", "A14", "A15",   # 1..5
    "CLK",                                # 6
    "D4", "D3", "D5", "D6",               # 7..10
    "VCC",                                # 11
    "D2", "D7", "D0", "D1",               # 12..15
    "INT", "NMI", "HALT",                 # 16..18
    "MREQ", "IORQ", "RD", "WR", "BUSACK",  # 19..23
    "WAIT", "BUSREQ", "RESET",            # 24..26
    "M1", "RFSH", "GND",                  # 27..29
    "A0", "A1", "A2", "A3", "A4", "A5",   # 30..35
    "A6", "A7", "A8", "A9", "A10",        # 36..40
]

# Cross-check table: a safeguard against a typo in the list above.
_PIN_CHECK = {
    1: "A11", 2: "A12", 3: "A13", 4: "A14", 5: "A15", 6: "CLK",
    7: "D4", 8: "D3", 9: "D5", 10: "D6", 11: "VCC", 12: "D2",
    13: "D7", 14: "D0", 15: "D1", 16: "INT", 17: "NMI", 18: "HALT",
    19: "MREQ", 20: "IORQ", 21: "RD", 22: "WR", 23: "BUSACK",
    24: "WAIT", 25: "BUSREQ", 26: "RESET", 27: "M1", 28: "RFSH",
    29: "GND", 30: "A0", 31: "A1", 32: "A2", 33: "A3", 34: "A4",
    35: "A5", 36: "A6", 37: "A7", 38: "A8", 39: "A9", 40: "A10",
}

if len(Z80_SIGNALS) != 40:
    raise RuntimeError("Z80_SIGNALS must contain 40 pins")
if len(set(Z80_SIGNALS)) != 40:
    raise RuntimeError("Z80_SIGNALS contains duplicates")
for _pin, _name in _PIN_CHECK.items():
    if Z80_SIGNALS[_pin - 1] != _name:
        raise RuntimeError(
            f"pinout: pin {_pin} = {Z80_SIGNALS[_pin - 1]!r}, expected {_name!r}"
        )

# Z80 pin name -> Arduino pin
P = {name: pin40[i] for i, name in enumerate(Z80_SIGNALS)}

# Bits in read order: address (least significant first), then control.
ADDR_BITS = [f"A{i}" for i in range(16)]
CTRL_BITS = ["M1", "MREQ", "RD", "WR", "IORQ", "RFSH", "HALT", "BUSACK"]
DATA_BITS = [f"D{i}" for i in range(8)]
READ_BITS = ADDR_BITS + CTRL_BITS

# A single SIMPL command reads all 24 signals at once: "43diq35diq..." (120 characters).
READ_CMD = "".join(f"{P[n]}diq" for n in READ_BITS)

# Pins driven by the Z80 itself (the Arduino only reads them, with pull-up).
Z80_OUTPUTS = ADDR_BITS + DATA_BITS + CTRL_BITS

# Command limit: the firmware reads the line via txtRead(buf, 255).
CMD_LIMIT = 240


def check(condition, message):
    if not condition:
        raise AssertionError(message)


# ---------------------------------------------------------------------------
# Bus state at one point in time (after the rising edge of CLK)
# ---------------------------------------------------------------------------
class Bus:
    """A single bus sample. The fields hold the LOGICAL pin level, so for
    active-low signals a value of 0 means "active"."""

    __slots__ = ("bits", "addr", "m1", "mreq", "rd", "wr", "iorq", "rfsh",
                 "halt", "busack")

    def __init__(self, bits):
        self.bits = bits
        addr = 0
        for i in range(16):
            if bits[i:i + 1] == b"1":
                addr |= (1 << i)
        self.addr = addr
        off = 16
        # 0 = low level (active for MREQ/RD/WR/IORQ/M1/RFSH/HALT/BUSACK)
        self.m1 = 0 if bits[off + 0:off + 1] == b"0" else 1
        self.mreq = 0 if bits[off + 1:off + 2] == b"0" else 1
        self.rd = 0 if bits[off + 2:off + 3] == b"0" else 1
        self.wr = 0 if bits[off + 3:off + 4] == b"0" else 1
        self.iorq = 0 if bits[off + 4:off + 5] == b"0" else 1
        self.rfsh = 0 if bits[off + 5:off + 6] == b"0" else 1
        self.halt = 0 if bits[off + 6:off + 7] == b"0" else 1
        self.busack = 0 if bits[off + 7:off + 8] == b"0" else 1

    @property
    def mem_read(self):
        return self.mreq == 0 and self.rd == 0

    @property
    def io_read(self):
        return self.iorq == 0 and self.rd == 0

    @property
    def mem_write(self):
        return self.mreq == 0 and self.wr == 0

    @property
    def io_write(self):
        return self.iorq == 0 and self.wr == 0

    @property
    def is_fetch(self):
        """Opcode fetch: M1 is active and a memory read is in progress."""
        return self.m1 == 0 and self.mreq == 0 and self.rd == 0

    def __str__(self):
        flags = []
        if self.m1 == 0:
            flags.append("M1")
        if self.mreq == 0:
            flags.append("RFSH" if self.rfsh == 0 else "MREQ")
        if self.rd == 0:
            flags.append("RD")
        if self.wr == 0:
            flags.append("WR")
        if self.iorq == 0:
            flags.append("IORQ")
        if self.halt == 0:
            flags.append("HALT")
        return f"A={self.addr:04X} D={'|'.join(flags) if flags else '-'}"


class RunResult:
    def __init__(self, fetches, halt_seen, write_events, samples,
                 stopped_on_write=False):
        self.fetches = fetches          # opcode fetch addresses (M1)
        self.halt_seen = halt_seen      # whether HALT was active
        self.write_events = write_events  # detected write cycles (must be empty)
        self.samples = samples          # all sampled states
        self.stopped_on_write = stopped_on_write

    @property
    def periods(self):
        return len(self.samples)

    def result_addr(self, limit=0x0200):
        """The first fetch address above limit is the result of 'JP (HL)'."""
        for a in self.fetches:
            if a >= limit:
                return a
        return None

    def why(self):
        """A short explanation for diagnosing a failed run."""
        if self.stopped_on_write:
            w = self.write_events[0]
            return (f"run interrupted by a write cycle at address {w.addr:04X} "
                    f"({w}) at tick {self.periods}")
        return f"ticks {self.periods}, fetches {len(self.fetches)}"


# ---------------------------------------------------------------------------
# Z80 controller
# ---------------------------------------------------------------------------
class TestZ80(TestSimplController):
    def __init__(self, port=DEFAULT_PORT, quiet=False):
        # The port is set through the base_test module; the file itself is not modified.
        base_test.COM_PORT = port
        self.port = port
        self._closed = False
        if not quiet:
            print(f"[i] Device: Zilog Z80 (DIP-40), port {port}")
        super().__init__()
        self._power_up()

    # ---------------- low level ----------------

    def _send(self, parts):
        """Send a list of command fragments without exceeding the firmware limit."""
        buf = ""
        for part in parts:
            if len(buf) + len(part) > CMD_LIMIT:
                self.send_command(buf)
                buf = ""
            buf += part
        if buf:
            self.send_command(buf)

    def _power_up(self):
        """Safe power-up: first all Z80 pins are inputs (no power)."""
        # 1. All 40 Z80 pins are put into the high-impedance state (VCC and GND too),
        #    so that nothing is present on the chip pins before power is applied.
        self._send([f"{P[n]}d{INPUT_MODE}" for n in Z80_SIGNALS])

        # 2. The control inputs are set to the passive state; RESET is held
        #    active (low) until the first tick.
        self._send([
            f"{P['CLK']}d{OUTPUT_MODE}0o",
            f"{P['RESET']}d{OUTPUT_MODE}0o",
            f"{P['INT']}d{OUTPUT_MODE}1o",
            f"{P['NMI']}d{OUTPUT_MODE}1o",
            f"{P['WAIT']}d{OUTPUT_MODE}1o",
            f"{P['BUSREQ']}d{OUTPUT_MODE}1o",
        ])

        # 3. Power: first ground, then +5 V.
        self.send_command(f"{P['GND']}d{OUTPUT_MODE}0o")
        self.send_command(f"{P['VCC']}d{OUTPUT_MODE}1o")

        # 4. Only now are the pins driven by the Z80 switched to input
        #    WITH PULL-UP: otherwise they "float" and are read arbitrarily.
        self._send([f"{P[n]}d{INPUT_PULLUP_MODE}" for n in Z80_OUTPUTS])

    def _data_cmd(self, value):
        """SIMPL command: drive a byte onto D0..D7 or release the bus (value=None)."""
        if value is None:
            return "".join(f"{P[n]}d{INPUT_PULLUP_MODE}" for n in DATA_BITS)
        return "".join(
            f"{P[n]}d{OUTPUT_MODE}{(value >> i) & 1}o"
            for i, n in enumerate(DATA_BITS)
        )

    def _release_data(self):
        self._send([f"{P[n]}d{INPUT_PULLUP_MODE}" for n in DATA_BITS])

    def _read_raw(self, prefix=""):
        """A single bus sample. Returns the bit string, or None if the response
        is incomplete / contains extraneous characters."""
        resp = self.send_command(prefix + READ_CMD)
        if not resp or len(resp) != len(READ_BITS):
            return None
        if set(resp) - {ord("0"), ord("1")}:
            return None
        return resp

    def _rise_and_sample(self):
        """Rising edge of CLK + read of the whole bus.

        While CLK is held high, the Z80 does not change the bus state, so two
        consecutive samples MUST match. A mismatch means a reception failure
        (at 2 Mbit/s this happens) — in that case the sample is repeated. This
        comparison also protects against accidentally driving a byte during a write cycle.
        """
        first = self._read_raw(f"{P['CLK']}h")
        for _ in range(3):
            if first is None:
                first = self._read_raw()
                continue
            second = self._read_raw()
            if second == first:
                return Bus(first)
            first = second
        raise IOError("the bus reads unstably: two consecutive samples did not match")

    def _fall_and_serve(self, bus, memory, io_map):
        """Falling edge of CLK + driving/releasing the data bus.

        The order MATTERS: the byte is set up BEFORE the tick falls. The
        firmware changes the data pins one at a time (8 `o` commands in a row,
        ~280 us), so driving after the fall would leave only ~40 us until the
        latching edge and the Z80 would periodically catch a half-assembled
        byte. Driving it in advance gives nearly a whole tick of margin.
        """
        if bus.mem_read:
            value = memory.get(bus.addr, 0x00)
        elif bus.io_read:
            value = io_map.get(bus.addr & 0xFF, 0xFF)
        else:
            value = None
        self.send_command(self._data_cmd(value) + f"{P['CLK']}l")

    # ---------------- clocking ----------------

    def reset(self, cycles=10):
        """Hold RESET active for several ticks and then release it.

        Important: after RESET is released, no more ticks are issued. The Z80
        samples RESET on the rising edge, so the very first tick inside run()
        will be that edge which releases the CPU from reset — and it is
        already served with data from memory.
        """
        self.send_command(f"{P['RESET']}d{OUTPUT_MODE}0o")
        for _ in range(cycles):
            self.send_command(f"{P['CLK']}h")
            self._release_data()
            self.send_command(f"{P['CLK']}l")
        self.send_command(f"{P['RESET']}d{OUTPUT_MODE}1o")

    def run(self, memory, periods=120, io_map=None, stop_on_write=True):
        """
        Run the Z80 for periods ticks, serving the bus as memory/IO.

        memory : dict {address: byte}; missing addresses are read as 0x00 (NOP)
        io_map : dict {port: byte} for IN instructions
        """
        if io_map is None:
            io_map = {}
        fetches = []
        samples = []
        write_events = []
        halt_seen = False
        prev_fetch = False
        stopped_on_write = False

        for _ in range(periods):
            bus = self._rise_and_sample()
            samples.append(bus)

            if bus.halt == 0:
                halt_seen = True

            # A new opcode fetch is recorded on the edge (within a single
            # M1 cycle the condition may be observed for more than one tick).
            fetch = bus.is_fetch
            if fetch and not prev_fetch:
                fetches.append(bus.addr)
            prev_fetch = fetch

            if bus.mem_write or bus.io_write:
                self._release_data()
                write_events.append(bus)
                if stop_on_write:
                    stopped_on_write = True
                    break

            self._fall_and_serve(bus, memory, io_map)

        return RunResult(fetches, halt_seen, write_events, samples,
                         stopped_on_write)

    # ---------------- shutdown ----------------

    def close(self):
        """Remove power from the Z80, release all pins, and close the port."""
        if getattr(self, "_closed", True):
            return
        self._closed = True
        try:
            self._send([f"{P[n]}d{INPUT_MODE}" for n in Z80_SIGNALS])
            print("[i] Socket switched to a safe state, Z80 unpowered")
        except Exception:
            pass
        try:
            if getattr(self, "_ser", None) is not None and self._ser.is_open:
                self._ser.close()
        except Exception:
            pass
        finally:
            self._ser = None

    def __del__(self):
        # Override the base class destructor: it is not idempotent and fails
        # on an already closed port when called a second time.
        try:
            self.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Program builder helpers
# ---------------------------------------------------------------------------
def build(code, addr=0, extra=None):
    """Build a memory map from a program byte string."""
    memory = {addr + i: b for i, b in enumerate(code)}
    if extra:
        for a, v in extra.items():
            if a in memory:
                raise ValueError(f"address {a:04X} is occupied by both the program and the data")
        memory.update(extra)
    return memory


def build_multi(*chunks):
    """Build memory from several independent fragments: (address, bytes)."""
    memory = {}
    for addr, code in chunks:
        for i, b in enumerate(code):
            a = addr + i
            if a in memory:
                raise ValueError(f"address {a:04X} is specified twice")
            memory[a] = b
    return memory


def prog_ldhl_jphl(value):
    """LD HL,value ; JP (HL)  -> the next fetch is at address value."""
    return bytes([0x21, value & 0xFF, (value >> 8) & 0xFF, 0xE9])


def prog_lda_jphl(src=0x0100):
    """LD A,(src) ; LD H,02h ; LD L,A ; JP (HL) -> fetch at 0200h+A."""
    return bytes([0x3A, src & 0xFF, (src >> 8) & 0xFF, 0x26, 0x02, 0x6F, 0xE9])


def prog_jphl_tail():
    """Tail 'LD DE,0200h ; ADD HL,DE ; JP (HL)'.

    Adds the offset 0200h to HL so that the result of the 16-bit ALU always
    falls outside the program code area (0x0000..0x00FF) and can be
    unambiguously identified on the address bus.
    """
    return bytes([0x11, 0x00, 0x02, 0x19, 0xE9])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_nop_walk(t, periods=80):
    """[1] Reset + consecutive NOP fetches: PC must go 0000,0001,0002..."""
    print("\n[1] Reset and NOP fetch (checking PC, A0..A15, MREQ/RD/M1/RFSH)")
    t.reset()
    res = t.run({}, periods=periods)
    got = res.fetches[:10]
    print("    fetches:", " ".join(f"{a:04X}" for a in res.fetches[:16]))
    check(res.write_events == [], "a write cycle was detected")
    check(got == list(range(10)),
          f"expected the sequence 0000..0009, got {[f'{a:04X}' for a in got]}")
    print(f"    OK — {len(res.fetches)} fetches, PC increments linearly")


def test_instruction_lengths(t):
    """[2] Instruction lengths: the PC after each instruction must equal its length."""
    print("\n[2] Instruction decoding (lengths/operand fetch)")
    code = bytes([
        0x3E, 0x55,        # 0000  LD A,55h      2 bytes -> 0002
        0x06, 0xAA,        # 0002  LD B,AAh      2       -> 0004
        0x21, 0x34, 0x12,  # 0004  LD HL,1234h   3       -> 0007
        0x11, 0x78, 0x56,  # 0007  LD DE,5678h   3       -> 000A
        0x31, 0x00, 0x90,  # 000A  LD SP,9000h   3       -> 000D
        0x01, 0x11, 0x22,  # 000D  LD BC,2211h   3       -> 0010
        0x3A, 0x00, 0x01,  # 0010  LD A,(0100h)  3       -> 0013
        0x00,              # 0013  NOP           1       -> 0014
        0x76,              # 0014  HALT
    ])
    t.reset()
    res = t.run(build(code), periods=140)
    expected = [0x0000, 0x0002, 0x0004, 0x0007, 0x000A, 0x000D, 0x0010, 0x0013, 0x0014]
    got = res.fetches[:len(expected)]
    print("    fetches:", " ".join(f"{a:04X}" for a in res.fetches[:14]))
    check(got == expected,
          f"expected {[f'{a:04X}' for a in expected]}, got {[f'{a:04X}' for a in got]}")
    check(res.halt_seen, "the HALT output did not become active after the HALT instruction")
    print(f"    OK — instruction lengths are correct, HALT is active")


def test_control_flow(t):
    """[3] Absolute and relative jumps."""
    print("\n[3] Jumps: JP nn, JR e, JR Z")
    code = build_multi(
        # 0000  JP 2000h
        (0x0000, bytes([0xC3, 0x00, 0x20])),
        # 2000  subroutine/loop
        (0x2000, bytes([
            0x3E, 0x01,        # 2000  LD A,01h  -> 2002
            0x3E, 0x02,        # 2002  LD A,02h  -> 2004
            0x18, 0x00,        # 2004  JR +0     -> 2006
            0x18, 0xFC,        # 2006  JR -4     -> 2004 (loop)
        ])),
    )
    t.reset()
    res = t.run(code, periods=200)
    expected = [0x0000, 0x2000, 0x2002, 0x2004, 0x2006, 0x2004, 0x2006]
    got = res.fetches[:len(expected)]
    print("    fetches:", " ".join(f"{a:04X}" for a in res.fetches[:12]))
    if got != expected:
        raise AssertionError(
            f"expected {[f'{a:04X}' for a in expected]}, "
            f"got {[f'{a:04X}' for a in got]} ({res.why()})"
        )

    # Flags and conditional jumps. Program layout (11 bytes, start 0000h):
    #   LD A,val ; <flag setup> ; JR cc,+2 ; LD A,05h
    #   LD H,02h ; LD L,A ; JP (HL)
    # If the jump is taken, the 05h load is skipped and the original val
    # appears on the address bus; if it is not taken, 05h appears.
    print("    Flags and conditional jumps:")
    flag_cases = [
        # label,                        A,    flags, JR,   expected target
        ("Z=1 (A=00h), JR Z  — taken",    0x00, 0xB7, 0x28, 0x0200),
        ("Z=0 (A=01h), JR Z  — not taken", 0x01, 0xB7, 0x28, 0x0205),
        ("Z=1 (A=00h), JR NZ — not taken", 0x00, 0xB7, 0x20, 0x0205),
        ("Z=0 (A=01h), JR NZ — taken",    0x01, 0xB7, 0x20, 0x0201),
        ("C=1 (SCF),  JR C  — taken",     0x11, 0x37, 0x38, 0x0211),
        ("C=0 (OR A), JR C  — not taken",  0x11, 0xB7, 0x38, 0x0205),
        ("C=0 (OR A), JR NC — taken",     0x11, 0xB7, 0x30, 0x0211),
        ("C=1 (SCF),  JR NC — not taken",  0x11, 0x37, 0x30, 0x0205),
    ]
    bad = 0
    for label, val, set_flags, jr, want in flag_cases:
        code = bytes([0x3E, val, set_flags, jr, 0x02, 0x3E, 0x05,
                      0x26, 0x02, 0x6F, 0xE9])
        t.reset()
        res = t.run(build(code), periods=110)
        got = res.result_addr()
        ok = got == want
        bad += 0 if ok else 1
        print(f"      {'OK ' if ok else 'FAIL'} {label:30s} -> "
              f"{'none' if got is None else format(got, '04X')} (expected {want:04X})")
        if not ok:
            print(f"           {res.why()}")
            print("           fetches:", " ".join(f"{a:04X}" for a in res.fetches[:10]))
    check(bad == 0, f"flag checks failed: {bad}")
    print("    OK — jumps and flags work")


def test_alu_8bit(t):
    """[4] ALU: the result is output onto the address bus via JP (HL)."""
    print("\n[4] ALU (8-bit): checking ADD/ADC/SUB/SBC/AND/OR/XOR/CP/INC/DEC/...")
    print("    result = address of the first fetch above 0200h minus 0200h")

    def acc2(a, b, op, prelude=()):
        return bytes([0x3E, a, 0x06, b, *prelude, op, 0x26, 0x02, 0x6F, 0xE9])

    def acc1(a, op, prelude=()):
        return bytes([0x3E, a, *prelude, op, 0x26, 0x02, 0x6F, 0xE9])

    SCF = (0x37,)   # set carry
    ORA = (0xB7,)   # clear carry (OR A)

    cases = [
        ("ADD A,B   05+03", acc2(0x05, 0x03, 0x80), 0x08),
        ("ADD A,B   FF+01", acc2(0xFF, 0x01, 0x80), 0x00),
        ("ADD A,B   7F+01", acc2(0x7F, 0x01, 0x80), 0x80),
        ("ADC A,B   0F+01+C", acc2(0x0F, 0x01, 0x88, SCF), 0x11),
        ("ADC A,B   FF+00+C", acc2(0xFF, 0x00, 0x88, SCF), 0x00),
        ("SUB B     10-03", acc2(0x10, 0x03, 0x90), 0x0D),
        ("SUB B     03-10", acc2(0x03, 0x10, 0x90), 0xF3),
        ("SBC A,B   10-01-C", acc2(0x10, 0x01, 0x98, SCF), 0x0E),
        ("AND B     F0&3C", acc2(0xF0, 0x3C, 0xA0), 0x30),
        ("OR  B     F0|0F", acc2(0xF0, 0x0F, 0xB0), 0xFF),
        ("XOR B     FF^0F", acc2(0xFF, 0x0F, 0xA8), 0xF0),
        ("CP  B     42,42 (A unchanged)", acc2(0x42, 0x42, 0xB8), 0x42),
        ("CP  B     42,43 (A unchanged)", acc2(0x42, 0x43, 0xB8), 0x42),
        ("INC A     7F", acc1(0x7F, 0x3C), 0x80),
        ("INC A     FF", acc1(0xFF, 0x3C), 0x00),
        ("DEC A     80", acc1(0x80, 0x3D), 0x7F),
        ("DEC A     00", acc1(0x00, 0x3D), 0xFF),
        ("CPL       55", acc1(0x55, 0x2F), 0xAA),
        ("RLCA      81", acc1(0x81, 0x07), 0x03),
        ("RRCA      03", acc1(0x03, 0x0F), 0x81),
        ("RLA(C=0)  80", acc1(0x80, 0x17, ORA), 0x00),
        ("RLA(C=1)  80", acc1(0x80, 0x17, SCF), 0x01),
        ("RRA(C=1)  01", acc1(0x01, 0x1F, SCF), 0x80),
        ("RRA(C=0)  01", acc1(0x01, 0x1F, ORA), 0x00),
        ("DAA       9A", acc1(0x9A, 0x27, ORA), 0x00),
    ]

    failed = 0
    for label, code, want in cases:
        t.reset()
        res = t.run(build(code), periods=90)
        got = res.result_addr()
        actual = None if got is None else got - 0x0200
        if actual != want:
            failed += 1
        mark = "OK " if actual == want else "FAIL"
        shown = "no fetch" if actual is None else f"{actual:02X}"
        print(f"    {mark} {label:22s} -> {shown:>10s} (expected {want:02X})")
        if actual != want:
            print(f"         {res.why()}")
            print("         fetches:", " ".join(f"{a:04X}" for a in res.fetches[:10]))
    check(failed == 0, f"ALU cases failed: {failed}")
    print(f"    OK — all {len(cases)} ALU cases are correct")


def test_address_bus(t):
    """[5] 16-bit address bus: LD HL,nn ; JP (HL)."""
    print("\n[5] Address bus A0..A15: walking one and walking zero")
    t.reset()
    res = t.run(build(prog_ldhl_jphl(0xAA55)), periods=60)
    got = res.fetches[2] if len(res.fetches) > 2 else None
    print("    LD HL,AA55h ; JP (HL) -> fetch:", "none" if got is None else f"{got:04X}")
    check(got == 0xAA55, f"expected AA55, got {'none' if got is None else format(got, '04X')}")

    bad = 0
    for bit in range(16):
        t.reset()
        res = t.run(build(prog_ldhl_jphl(1 << bit)), periods=60)
        got = res.fetches[2] if len(res.fetches) > 2 else None
        ok = got == (1 << bit)
        bad += 0 if ok else 1
        print(f"    {'OK ' if ok else 'FAIL'} A{bit:<2d} = 1      -> "
              f"{'none' if got is None else format(got, '04X')}")
        if not ok:
            print(f"         {res.why()}")
            print("         fetches:", " ".join(f"{a:04X}" for a in res.fetches[:8]))

    for bit in range(16):
        want = 0xFFFF ^ (1 << bit)
        t.reset()
        res = t.run(build(prog_ldhl_jphl(want)), periods=60)
        got = res.fetches[2] if len(res.fetches) > 2 else None
        ok = got == want
        bad += 0 if ok else 1
        print(f"    {'OK ' if ok else 'FAIL'} A{bit:<2d} = 0      -> "
              f"{'none' if got is None else format(got, '04X')} (expected {want:04X})")

    check(bad == 0, f"address bus checks failed: {bad}")
    print("    OK — all 32 address bus states are correct")


def test_data_bus(t):
    """[6] Data bus D0..D7: LD A,(nn) ; JP (HL)."""
    print("\n[6] Data bus D0..D7 via LD A,(0100h) ; JP (HL)")

    bad = 0
    for bit in range(8):
        want = 1 << bit
        t.reset()
        res = t.run(build(prog_lda_jphl(0x0100), extra={0x0100: want}), periods=80)
        got = res.result_addr()
        actual = None if got is None else got - 0x0200
        ok = actual == want
        bad += 0 if ok else 1
        print(f"    {'OK ' if ok else 'FAIL'} D{bit} = 1 -> "
              f"{'none' if actual is None else format(actual, '02X')}")

    for bit in range(8):
        want = 0xFF ^ (1 << bit)
        t.reset()
        res = t.run(build(prog_lda_jphl(0x0100), extra={0x0100: want}), periods=80)
        got = res.result_addr()
        actual = None if got is None else got - 0x0200
        ok = actual == want
        bad += 0 if ok else 1
        print(f"    {'OK ' if ok else 'FAIL'} D{bit} = 0 -> "
              f"{'none' if actual is None else format(actual, '02X')} (expected {want:02X})")

    check(bad == 0, f"data bus checks failed: {bad}")
    print("    OK — all 16 data bus states are correct")


def test_alu_16bit(t):
    """[7] 16-bit arithmetic and register pair transfers."""
    print("\n[7] 16-bit ALU: LD rr,nn, ADD HL,rr, INC/DEC rr, LD H/L,r")
    tail = prog_jphl_tail()

    checks = [
        # LD HL,1234h ; JP-tail -> 1234h
        ("LD HL,nn   1234h",
         bytes([0x21, 0x34, 0x12]) + tail, 0x1234),
        # LD HL,0042h ; LD D,H ; LD E,L ; (DE=HL) ; LD HL,DE -> 0042h
        ("LD H/L via D/E",
         bytes([0x21, 0x42, 0x00,   # LD HL,0042h
                0x26, 0x00,         # LD H,00h
                0x54,               # LD D,H
                0x5D,               # LD E,L
                0x26, 0x00,         # LD H,00h
                0x62,               # LD H,D
                0x6B]) + tail, 0x0042),
        # ADD HL,DE 1234h + 1111h = 2345h
        ("ADD HL,DE 1234h+1111h",
         bytes([0x21, 0x34, 0x12,
                0x11, 0x11, 0x11,
                0x19]) + tail, 0x2345),
        # INC HL: 00FFh + 1 = 0100h
        ("INC HL     00FFh",
         bytes([0x21, 0xFF, 0x00,
                0x23]) + tail, 0x0100),
        # DEC HL: 0100h - 1 = 00FFh
        ("DEC HL     0100h",
         bytes([0x21, 0x00, 0x01,
                0x2B]) + tail, 0x00FF),
        # INC BC: 00FFh + 1 = 0100h
        ("INC BC     00FFh",
         bytes([0x01, 0xFF, 0x00,   # LD BC,00FFh
                0x03,               # INC BC
                0x26, 0x00,         # LD H,00h
                0x60,               # LD H,B
                0x69]) + tail, 0x0100),
        # Carry across the boundary: FFFFh + 0001h = 0000h
        ("ADD HL,DE FFFFh+0001h (carry)",
         bytes([0x21, 0xFF, 0xFF,
                0x11, 0x01, 0x00,
                0x19]) + tail, 0x0000),
    ]

    bad = 0
    for label, code, want in checks:
        t.reset()
        res = t.run(build(code), periods=110)
        got = res.result_addr()
        actual = None if got is None else got - 0x0200
        ok = actual == want
        bad += 0 if ok else 1
        print(f"    {'OK ' if ok else 'FAIL'} {label:34s} -> "
              f"{'none' if actual is None else format(actual, '04X')} (expected {want:04X})")
        if not ok:
            print("       fetches:", " ".join(f"{a:04X}" for a in res.fetches[:10]))
    check(bad == 0, f"16-bit checks failed: {bad}")
    print("    OK — 16-bit arithmetic is correct")


def test_monitor(t, rounds=5):
    """[0] Just display the bus state — a check of communication with the tester."""
    print("\n[0] Bus monitor (RESET is held active)")
    for _ in range(rounds):
        bus = t._rise_and_sample()
        print("    ", bus)
        t.send_command(f"{P['CLK']}l")
        t._release_data()
    print("    hint: address 0000 and a high level on the data bus with the "
          "IC inserted in the reset state is normal")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
TESTS = {
    "nop": test_nop_walk,
    "decode": test_instruction_lengths,
    "flow": test_control_flow,
    "alu": test_alu_8bit,
    "addr": test_address_bus,
    "data": test_data_bus,
    "alu16": test_alu_16bit,
}

ORDER = ["nop", "decode", "flow", "alu", "addr", "data", "alu16"]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Functional Z80 tester (DIP-40) on Mega-IC-Tester"
    )
    parser.add_argument("--port", default=DEFAULT_PORT,
                        help=f"Arduino COM port (default {DEFAULT_PORT})")
    parser.add_argument("--monitor", action="store_true",
                        help="only print the bus state and exit")
    parser.add_argument("--test", action="append", choices=ORDER,
                        help="run only the specified test (may be repeated)")
    args = parser.parse_args(argv)

    t = TestZ80(port=args.port)
    failed = []
    try:
        if args.monitor:
            test_monitor(t)
            return 0

        selected = args.test or ORDER
        for name in selected:
            fn = TESTS[name]
            try:
                fn(t)
            except AssertionError as exc:
                failed.append(name)
                print(f"    FAIL [{name}]: {exc}")
            except IOError as exc:
                # Communication lost — there is no point in continuing
                print(f"    COMMUNICATION ERROR [{name}]: {exc}")
                failed.append(name)
                break
    finally:
        try:
            t.close()
        except Exception:
            pass

    print("\n" + "=" * 62)
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

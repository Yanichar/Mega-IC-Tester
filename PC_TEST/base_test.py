from os import name

import serial

from arduino_to_pins import pin40
from simpl_macros import INPUT_MODE
import serial.tools.list_ports

COM_PORT = "COM11"
COM_BAUD = 2000000


def find_arduino_port():
    arduino_vid_pid = [
        (0x1A86, 0x7523),  # Arduino Mega
    ]

    ports = serial.tools.list_ports.comports()
    for port in ports:
        for vid, pid in arduino_vid_pid:
            if port.vid == vid and port.pid == pid:
                return port.device
    return None

def find_by_description():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "Arduino" in port.description or "CH340" in port.description:
            return port.device
    return None

def find_by_handshake(ports):
    for port in ports:
        try:
            print(f"Probe {port}")
            ser = serial.Serial(
                port=port,
                baudrate=COM_BAUD,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=5)

            response = ser.read_until(b"\n")
            ser.close()
            if b"Display initialized" in response:
                return port.device
        except:
            continue
    return None

def check(actual, expected):
    if actual != expected:
        print("FAILED!!!", "actual:", actual, "expected:", expected)
        exit(1)


def extract_bits_from_byte(addr):
    return (
        (addr >> 0) & 1,
        (addr >> 1) & 1,
        (addr >> 2) & 1,
        (addr >> 3) & 1,
        (addr >> 4) & 1,
        (addr >> 5) & 1,
        (addr >> 6) & 1,
        (addr >> 7) & 1,
        (addr >> 8) & 1,
        (addr >> 9) & 1,
        (addr >> 10) & 1,
        (addr >> 11) & 1,
        (addr >> 12) & 1,
        (addr >> 13) & 1,
        (addr >> 14) & 1,
        (addr >> 15) & 1,
    )


class TestSimplController:
    def __init__(self):

        port_candidates = set()
        port_candidates.add(find_arduino_port())
        port_candidates.add(find_by_description())

        print(port_candidates)
        print(find_by_handshake(port_candidates))

        self._ser = serial.Serial(
            port=COM_PORT,
            baudrate=COM_BAUD,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )

        self.try_activate_controller()

    def try_activate_controller(self):
        print("Try to activate")
        for i in range(1000):
            self._ser.write(b".")
            self._ser.flush()
            income = self._ser.read_until(b"\n")
            income = income.strip(b"\r").strip(b"\r\n")
            if income == b"SIMPL Ready":
                break

        print("Activated")

    def send_command(self, cmd: str):
        if len(cmd) > 255:
            print("Overflow", len(cmd))
            return None
        if not cmd.endswith("\n"):
            cmd += "\n"
        self._ser.write(cmd.encode("ascii"))
        self._ser.flush()

        income = self._ser.read_until(b"\n")
        income = income.strip(b"\r").strip(b"\r\n")
        if income != b"":
            return income

        return None

    def __del__(self):
        print("Test socket set to safe state")
        cmd = ""
        for pin in pin40:
            cmd += f"{pin}d{INPUT_MODE}"

        self.send_command(cmd)

        if hasattr(self, "_ser") and self._ser is not None:
            try:
                if self._ser.is_open:
                    self._ser.close()
                    print("Serial port closed")
            except Exception as e:
                print(f"Error closing port: {e}")
            finally:
                self._ser = None

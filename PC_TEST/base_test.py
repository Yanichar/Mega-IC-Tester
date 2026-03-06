import serial

from arduino_to_pins import pin40
from simpl_macros import INPUT_MODE

COM_PORT = "COM9"
COM_BAUD = 2000000


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

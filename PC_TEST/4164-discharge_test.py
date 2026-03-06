import time
from pattern_generator import get_bit_from_pattern
from _4164 import Test4164


def find_max_true(func, low=1, high=120000, max_iterations=1000):
    if high is None:
        if not func(low):
            return None

        high = low + 1
        iterations = 0

        while func(high) and iterations < max_iterations:
            low = high
            high *= 2
            iterations += 1

        if iterations >= max_iterations:
            while func(high):
                high *= 2
                if high > 2**63:
                    return high - 1

    if not func(low):
        return None

    if func(high):
        while func(high):
            high *= 2
            if high > 2**63:
                return high - 1

    while low <= high:
        mid = (low + high) // 2

        if func(mid):
            low = mid + 1
        else:
            high = mid - 1

    return high


if __name__ == "__main__":
    uc = Test4164()

    def _x(delay):
        print(f"Test {delay}")
        if delay < 55:
            return True
        else:
            return False

    def test_discharge(delay):
        pattern = [0xAA for _ in range(32)]

        print("Write...")
        for i in range(256):
            uc.write(i, get_bit_from_pattern(pattern, i))

        print(f"Sleep for {delay}")
        time.sleep(delay / 1000)

        print("Read...")

        ok = True

        for i in range(256):
            read = uc.read(i)

            if get_bit_from_pattern(pattern, i):
                expected = b"1"
            else:
                expected = b"0"

            if read != expected:
                ok = False

        if not ok:
            print("FAIL")
            return False
        else:
            print("PASS")
            return True

    find_max_true(test_discharge, high=20000)
    # print("Final", find_max_true(_x)),

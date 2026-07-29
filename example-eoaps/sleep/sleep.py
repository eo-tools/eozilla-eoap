#  This file was copied over from eozilla's local test service at
#  eozilla/wraptile/src/wraptile/servucse/local/testing.py
#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import sys
import time


def sleep_a_while(
    duration: float = 10.0,
    fail: bool = False,
) -> float:

    t0 = time.time()
    for i in range(101):
        if fail and i == 50:
            raise RuntimeError("Woke up too early")
        time.sleep(duration / 100)
    return time.time() - t0


try:
    duration = float(sys.argv[1])
    fail = sys.argv[2].lower() == "true"
except IndexError:
    ret = sleep_a_while()
else:
    ret = sleep_a_while(duration, fail)
finally:
    print(ret)

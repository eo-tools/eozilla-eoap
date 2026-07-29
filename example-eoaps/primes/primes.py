#  This file was copied over from eozilla's local test service at
#  eozilla/wraptile/src/wraptile/servucse/local/testing.py
#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import sys

import pydantic


def primes_between(
    min_val: int = pydantic.Field(0, ge=0),
    max_val: int = pydantic.Field(100, le=100),
) -> list[int]:

    if max_val < 2 or max_val <= min_val:
        raise ValueError("max_val must be greater 1 and greater min_val")

    limit = int(max_val**0.5) + 1
    is_prime_small = [True] * (limit + 1)
    is_prime_small[0:2] = [False, False]
    for i in range(2, int(limit**0.5) + 1):
        if is_prime_small[i]:
            for j in range(i * i, limit + 1, i):
                is_prime_small[j] = False
    small_primes = [i for i, prime in enumerate(is_prime_small) if prime]

    sieve_range = max_val - min_val + 1
    is_prime = [True] * sieve_range

    for p in small_primes:
        # Find the first multiple of p in the range [min_val, max_val]
        start = max(p * p, ((min_val + p - 1) // p) * p)
        for j in range(start, max_val + 1, p):
            is_prime[j - min_val] = False

    for n in range(min_val, min(min_val + 2, max_val + 1)):
        if n < 2:
            is_prime[n - min_val] = False

    return [min_val + i for i, prime in enumerate(is_prime) if prime]


try:
    min_val = int(sys.argv[1])
    max_val = int(sys.argv[2])
except IndexError:
    ret = primes_between(0, 100)
else:
    ret = primes_between(min_val, max_val)
finally:
    print(ret)

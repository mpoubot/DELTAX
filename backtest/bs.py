"""Black-Scholes pricing for the 4-day-hold sweep.

Why this exists: E15's exit proxy - "neither short strike touched by day 7" -
has no time model, so it cannot distinguish a 7-DTE condor from a 21-DTE one.
Choosing an expiry for a fixed 4-day hold is precisely a question about the
shape of the decay curve, so the position has to be repriced, not proxied.
"""
from math import exp, log, sqrt, erf

RATE = 0.04


def N(x):
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _d(S, K, T, sig):
    v = sig * sqrt(T)
    d1 = (log(S / K) + (RATE + 0.5 * sig * sig) * T) / v
    return d1, d1 - v


def call(S, K, T, sig):
    if T <= 0:
        return max(S - K, 0.0)
    d1, d2 = _d(S, K, T, sig)
    return S * N(d1) - K * exp(-RATE * T) * N(d2)


def put(S, K, T, sig):
    if T <= 0:
        return max(K - S, 0.0)
    d1, d2 = _d(S, K, T, sig)
    return K * exp(-RATE * T) * N(-d2) - S * N(-d1)


def condor_value(S, k_put, k_call, width, T, sig):
    """Value of the SHORT condor - what it costs to buy back. Entry credit is
    this at T0; P&L is credit minus this at exit."""
    ps = put(S, k_put, T, sig) - put(S, k_put - width, T, sig)
    cs = call(S, k_call, T, sig) - call(S, k_call + width, T, sig)
    return ps + cs


def implied_vol(target, S, k_put, k_call, width, T, lo=0.01, hi=5.0):
    """Vol that makes the condor worth `target` - calibrates the model to the
    credit our gate actually requires, so the reprice inherits the real
    premium rather than a theoretical one."""
    if condor_value(S, k_put, k_call, width, T, hi) < target:
        return None
    if condor_value(S, k_put, k_call, width, T, lo) > target:
        return None
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if condor_value(S, k_put, k_call, width, T, mid) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)

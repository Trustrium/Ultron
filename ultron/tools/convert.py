"""Currency conversion (free FX rates via frankfurter.app) + unit conversion (built-in)."""
from __future__ import annotations
import json
import urllib.parse
import urllib.request


# ===== Currency via frankfurter.app =====

from ..cache import ttl_cache


@ttl_cache(seconds=600)
def _fx_rate(from_ccy: str, to_ccy: str) -> tuple[float, str]:
    f = (from_ccy or "").upper().strip()
    t = (to_ccy or "").upper().strip()
    if not f or not t:
        return 0.0, "Provide both from and to currency codes (e.g. USD, EUR, INR)."

    last_err = None

    # Primary: open.er-api.com (free, no key, widely reachable)
    try:
        url = f"https://open.er-api.com/v6/latest/{urllib.parse.quote(f)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Ultron/7.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("result") == "success":
            rate = (data.get("rates") or {}).get(t)
            if rate is not None:
                return float(rate), ""
    except Exception as e:
        last_err = e

    # Fallback: frankfurter.dev (some networks/ISPs block this one)
    try:
        url = f"https://api.frankfurter.dev/v1/latest?base={urllib.parse.quote(f)}&symbols={urllib.parse.quote(t)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Ultron/7.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        rate = (data.get("rates") or {}).get(t)
        if rate is not None:
            return float(rate), ""
    except Exception as e:
        last_err = e

    if last_err is not None:
        return 0.0, f"FX fetch failed (both sources): {last_err}"
    return 0.0, f"No rate returned for {f} -> {t}."


def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return f"Invalid amount: {amount}"
    rate, err = _fx_rate(from_currency, to_currency)
    if err:
        return err
    return (f"{amt:g} {from_currency.upper()} = {amt * rate:.4f} {to_currency.upper()} "
            f"(rate {rate})")


# ===== Unit conversion =====

# All factors normalise to a base unit per dimension.
_LENGTH_TO_M = {
    "mm": 0.001, "millimeter": 0.001, "millimetre": 0.001,
    "cm": 0.01, "centimeter": 0.01, "centimetre": 0.01,
    "m": 1.0, "meter": 1.0, "metre": 1.0,
    "km": 1000.0, "kilometer": 1000.0, "kilometre": 1000.0,
    "in": 0.0254, "inch": 0.0254, "ft": 0.3048, "foot": 0.3048,
    "yd": 0.9144, "yard": 0.9144,
    "mi": 1609.344, "mile": 1609.344,
}
_MASS_TO_KG = {
    "mg": 1e-6, "milligram": 1e-6, "g": 1e-3, "gram": 1e-3, "gramme": 1e-3,
    "kg": 1.0, "kilogram": 1.0, "tonne": 1000.0, "ton": 1000.0,
    "oz": 0.0283495, "ounce": 0.0283495, "lb": 0.453592, "lbs": 0.453592, "pound": 0.453592,
}
_TIME_TO_S = {
    "ms": 1e-3, "millisecond": 1e-3, "s": 1.0, "sec": 1.0, "second": 1.0,
    "min": 60.0, "minute": 60.0, "hour": 3600.0, "hr": 3600.0, "day": 86400.0,
}
_VOLUME_TO_L = {
    "ml": 0.001, "milliliter": 0.001, "millilitre": 0.001,
    "l": 1.0, "liter": 1.0, "litre": 1.0,
    "cup": 0.2365882, "pint": 0.473176, "quart": 0.946353,
    "gallon": 3.785411, "gal": 3.785411,
}


def _normalize_unit(u: str) -> str:
    """Lowercase, strip, and drop a trailing plural 's' (kept 'ms', 'lbs', 'gas')."""
    u = (u or "").lower().strip()
    if u.endswith("s") and u not in {"ms", "lbs", "s"}:
        u = u[:-1]
    return u


def _try_temperature(amount: float, src: str, dst: str) -> str | None:
    """Temperature is non-linear so handle separately. Returns None if not temperature."""
    src_l = src.lower().lstrip("°")
    dst_l = dst.lower().lstrip("°")
    if src_l not in {"c", "f", "k"} or dst_l not in {"c", "f", "k"}:
        return None
    # Normalise to Celsius
    if src_l == "c":
        c = amount
    elif src_l == "f":
        c = (amount - 32) * 5 / 9
    else:
        c = amount - 273.15
    # Convert from Celsius to dst
    if dst_l == "c":
        out = c
    elif dst_l == "f":
        out = c * 9 / 5 + 32
    else:
        out = c + 273.15
    return f"{amount:g} °{src_l.upper()} = {out:.4g} °{dst_l.upper()}"


def convert_unit(amount: float, from_unit: str, to_unit: str) -> str:
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return f"Invalid amount: {amount}"
    fu = _normalize_unit(from_unit)
    tu = _normalize_unit(to_unit)

    temp = _try_temperature(amt, fu, tu)
    if temp is not None:
        return temp

    for table in (_LENGTH_TO_M, _MASS_TO_KG, _TIME_TO_S, _VOLUME_TO_L):
        if fu in table and tu in table:
            base = amt * table[fu]
            out = base / table[tu]
            return f"{amt:g} {fu} = {out:.6g} {tu}"

    return (f"Units '{from_unit}' / '{to_unit}' not recognized. "
            "Supported: length (mm,cm,m,km,in,ft,yd,mi), mass (mg,g,kg,oz,lb), "
            "time (ms,s,min,hour,day), volume (ml,l,cup,pint,quart,gallon), "
            "temperature (c,f,k).")

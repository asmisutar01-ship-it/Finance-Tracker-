"""
app/utils/currency.py
---------------------
Central multi-currency utility for FinanceTracker.

All financial values are STORED in INR in the database.
Conversion only happens:
  - Input  → convert_to_inr()   before saving
  - Display → convert_from_inr() when rendering (optional)

Tax calculations ALWAYS use raw INR values — never call convert_from_inr()
inside tax logic.
"""

import logging
import os
import requests

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static exchange rates  (INR is the base)
# 1 USD = 83 INR,  1 EUR = 90 INR,  1 GBP = 105 INR
# ---------------------------------------------------------------------------
RATES: dict[str, float] = {
    "INR": 1.0,
    "USD": 83.0,
    "EUR": 90.0,
    "GBP": 105.0,
}

SYMBOLS: dict[str, str] = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

SUPPORTED: list[str] = list(RATES.keys())


# ---------------------------------------------------------------------------
# Core conversion helpers
# ---------------------------------------------------------------------------

def get_live_rate(currency: str) -> float | None:
    """Fetch live exchange rate for currency -> INR with 5-second timeout."""
    if currency == "INR":
        return 1.0
        
    api_key = os.environ.get("CURRENCY_API_KEY")
    if not api_key:
        return None
        
    try:
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{currency}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get("result") == "success":
            rates = data.get("conversion_rates", {})
            if "INR" in rates:
                return float(rates["INR"])
    except Exception as exc:
        log.error("ExchangeRate-API failed for %s: %s", currency, exc)
    
    return None


def convert_to_inr(amount: float, currency: str) -> float:
    """
    Convert *amount* (in *currency*) to INR.

    Example:
        convert_to_inr(100, "USD")  → 8300.0
        convert_to_inr(500, "INR")  → 500.0
    """
    try:
        currency = (currency or "INR").upper().strip()
        
        # 1) Try Live Rate
        live_rate = get_live_rate(currency)
        if live_rate is not None:
            return float(amount) * live_rate
            
        # 2) Fallback to static
        rate = RATES.get(currency)
        if rate is None:
            log.warning("Unknown currency '%s'; defaulting to INR.", currency)
            return float(amount)
        return float(amount) * rate
    except Exception as exc:
        log.error("convert_to_inr failed (amount=%s, currency=%s): %s", amount, currency, exc)
        return float(amount)   # fallback: treat as INR


def convert_from_inr(amount_inr: float, target_currency: str) -> float:
    """
    Convert *amount_inr* (stored INR value) to *target_currency*.

    Example:
        convert_from_inr(8300, "USD")  → 100.0
        convert_from_inr(8300, "INR")  → 8300.0
    """
    try:
        target_currency = (target_currency or "INR").upper().strip()
        
        if target_currency == "INR":
            return float(amount_inr)
            
        # 1) Try Live Rate
        live_rate = get_live_rate(target_currency)
        if live_rate is not None and live_rate > 0:
            return float(amount_inr) / live_rate

        # 2) Fallback to static
        rate = RATES.get(target_currency)
        if rate is None:
            log.warning("Unknown target currency '%s'; defaulting to INR.", target_currency)
            return float(amount_inr)
        if rate == 0:
            return float(amount_inr)
        return float(amount_inr) / rate
    except Exception as exc:
        log.error("convert_from_inr failed (amount=%s, target=%s): %s", amount_inr, target_currency, exc)
        return float(amount_inr)


def get_symbol(currency: str) -> str:
    """Return the currency symbol, falling back to '₹'."""
    return SYMBOLS.get((currency or "INR").upper().strip(), "₹")


def format_amount(amount_inr: float, original_amount: float | None, original_currency: str | None) -> str:
    """
    Return a display string for a record.
    - If the record was entered in a foreign currency, show original value + symbol.
    - Otherwise show INR amount.
    """
    try:
        if original_currency and original_currency.upper() != "INR" and original_amount is not None:
            sym = get_symbol(original_currency)
            return f"{sym}{original_amount:,.2f}"
        return f"₹{amount_inr:,.2f}"
    except Exception:
        return f"₹{amount_inr:,.2f}"

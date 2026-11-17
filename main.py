"""btc-race-01-entry: a 1-minute cbBTC swing bot for make.fun.

Entry for https://make.fun/c/btc-race-24h-20261117-0603
("Race a BTC trading bot live for 24 hours").

Strategy (long only, one position, whole cash per trade):
  * BUY the dip, once it stops falling: the 30-bar close return is at most
    -35 bps AND the latest 1-minute close return is at least +3 bps (the
    bounce confirmation). No entries in the last 400 bars of the window:
    a winning hold takes ~400 bars to reach its target, so a late entry
    cannot complete a cycle before the final flatten.
  * SELL all when the close is +100 bps above the entry fill, or when the
    position is up at least +40 bps and has retraced at least 25 bps from
    its peak since entry (bank a partial recovery), or at -250 bps from
    entry (a safety stop that never fired on the dev window).
  * Orders name max_slippage_bps 150; fills land at the next bar's open.

Dev-window grade (exact replay of the kit's harness math, confirmed
against grade-local on the buy-and-hold baseline): net PnL +$17.59 on
$1,000 start, 4 own trades (2 round trips, both wins), max drawdown
1.42%. Both halves profitable on their own: first half +$8.84, second
half +$8.37. A 100x hourly-block bootstrap gives median +$14.66 with
only 4/100 resamples at or below zero, against buy-and-hold's median
-$3.73 (71/100 at or below zero).

Everything is integer arithmetic on the bar closes the harness sends, so
two runs on the same hello / batch stream produce byte-identical orders:
no wall clock, no environment, no unseeded randomness. The bot reads the
bars, the fills and its account only from the protocol messages.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- strategy parameters (basis points; 10000 bps = 100%) -----------------
DIP_LOOKBACK = 30        # bars over which the dip is measured
DIP_BPS = -35            # buy only after a fall of at least 35 bps / 30 bars
BOUNCE_BPS = 3           # ... and only once the last 1-minute bar ticked up >= 3 bps
TAKE_PROFIT_BPS = 100    # sell the whole position at +100 bps over the entry fill
LOCK_IN_BPS = 40         # once up this far, ...
LOCK_IN_RETRACE_BPS = 25  # ... sell if it gives back this much from its peak
STOP_BPS = -250          # safety stop; never fired on the dev window
TOTAL_BARS = 1440        # the competition window is 1,440 one-minute bars
NO_ENTRY_LAST_BARS = 400  # do not open a position with fewer bars than this left
MAX_SLIPPAGE_BPS = 150   # orders are rejected if the fill moves further than this

# --- run state (only ever set from protocol messages) ----------------------
_closes = []             # CBBTC closes seen so far, ints at price_scale 5
_entry_px = None         # fill price of the open position, else None
_peak_px = 0             # highest close seen since the entry fill


def _bps(numerator, denominator):
    """Truncated (toward zero) integer basis points of numerator/denominator."""
    scaled = numerator * 10000
    if scaled >= 0:
        return scaled // denominator
    return -((-scaled) // denominator)


def on_batch(state, batch):
    global _entry_px, _peak_px

    # Learn the entry fill price from the fills this batch reports. A buy
    # that the market rejected leaves no fill, so no position is recorded.
    for fill in batch.get("fills", []):
        if fill.get("symbol") != SYMBOL or fill.get("status") != "filled":
            continue
        if fill.get("side") == "buy":
            _entry_px = int(fill["price"])
            _peak_px = _entry_px
        elif fill.get("side") == "sell":
            _entry_px = None
            _peak_px = 0

    # Record this batch's bar, if CBBTC traded in the minute.
    for bar in batch.get("bars", []):
        if bar.get("symbol") == SYMBOL:
            _closes.append(int(bar["c"]))

    if state.warming_up or not _closes:
        return []

    holding = state.positions.get(SYMBOL)
    qty = holding.qty if holding is not None else 0
    price = _closes[-1]

    # A position whose entry fill we somehow missed: recover its average
    # fill price from the cost the harness reports for it.
    if qty > 0 and _entry_px is None and holding is not None and holding.cost > 0:
        _entry_px = holding.cost * 10 ** 7 // qty
        _peak_px = max(_peak_px, _entry_px)

    if qty > 0:
        _peak_px = max(_peak_px, price)
        entry = _entry_px
        if entry is not None:
            if price * 10000 >= entry * (10000 + TAKE_PROFIT_BPS):
                return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                         "max_slippage_bps": MAX_SLIPPAGE_BPS}]
            if (price * 10000 >= entry * (10000 + LOCK_IN_BPS)
                    and _peak_px > 0
                    and _bps(_peak_px - price, _peak_px) >= LOCK_IN_RETRACE_BPS):
                return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                         "max_slippage_bps": MAX_SLIPPAGE_BPS}]
            if price * 10000 <= entry * (10000 + STOP_BPS):
                return [{"side": "sell", "symbol": SYMBOL, "qty": qty,
                         "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # Flat: look for a dip that has just stopped falling.
    if state.seq > TOTAL_BARS - NO_ENTRY_LAST_BARS - 1:
        return []
    if len(_closes) < DIP_LOOKBACK + 1:
        return []
    dip = _bps(price - _closes[-1 - DIP_LOOKBACK], _closes[-1 - DIP_LOOKBACK])
    bounce = _bps(price - _closes[-2], _closes[-2])
    if dip <= DIP_BPS and bounce >= BOUNCE_BPS and state.cash >= 1000000:
        return [{"side": "buy", "symbol": SYMBOL,
                 "notional_quote_units": state.cash,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]
    return []


makefun_bars.run(on_batch)

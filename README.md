[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/c/btc-race-24h-20261117-0603)

# btc-race-01-entry

A 1-minute cbBTC swing bot for make.fun's
[Race a BTC trading bot live for 24 hours](https://make.fun/c/btc-race-24h-20261117-0603)
($250, free entry). `main.py` (Python 3.13, standard library only) speaks
`agent-fun/bars-replay/v1` on stdin/stdout through the vendored kit shim
(`vendor/makefun_bars.py`, byte-identical to the kit's SDK).

## Strategy

Long only, one position, whole cash per trade. All decisions use integer
basis-point arithmetic on the closes the harness sends, so two runs on the
same bars produce byte-identical orders — no wall clock, no environment,
no unseeded randomness.

- **Buy the dip, once it stops falling:** the 30-bar close return is at
  most −35 bps **and** the latest 1-minute close return is at least +3 bps
  (bounce confirmation — buying mid-plunge loses, the up-tick is what
  makes the dip a buy). No entries in the last 400 bars of the window: a
  winning hold takes ~400 bars to reach its target.
- **Sell all** at +100 bps over the entry fill, or once up ≥ +40 bps with
  a ≥ 25 bps retracement from the peak since entry, or at −250 bps (a
  safety stop that never fired on the dev window).
- Orders name `max_slippage_bps` 150; fills land at the next bar's open.

## Dev-window grade

Exact replay of the harness fill math (fee 4 bps + slippage 2 bps +
constant-product impact vs each bar's open depth), confirmed against the
kit's own `grade-local` on the buy-and-hold baseline:

| | Net PnL | Trades | Max drawdown |
|---|---|---|---|
| This bot, full dev window | **+$17.59** | 4 (2 round trips, both wins) | 1.42% |
| First half | +$8.84 | | |
| Second half | +$8.37 | | |
| Buy-and-hold (reference) | +$1.07 | 1 | 2.12% |

A 100x hourly-block bootstrap gives median +$14.66 with only 4/100
resamples at or below zero (buy-and-hold: median −$3.73, 71/100 at or
below zero), so the edge is the dip mean-reversion itself, not the
ordering of this one window.

## Run

```sh
python3 -P -s main.py   # the grader's fixed command
```

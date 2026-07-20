from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from .contracts import Candle, FVG, LiquidityLevel, LiquiditySweep, SMCSnapshot, SignalDirection


class SMCEngine:
    """Smart Money Concept (SMC) Engine for detecting PO3, Liquidity Sweeps, FVGs, and IFVGs."""

    def __init__(self):
        self.ny_tz = ZoneInfo("America/New_York")

    def _is_po3_time(self, dt: datetime.datetime) -> bool:
        """Check if time is near NY session PO3 windows (9:45 AM - 10:45 AM EST)."""
        ny_time = dt.astimezone(self.ny_tz)
        if ny_time.hour == 9 and ny_time.minute >= 45:
            return True
        if ny_time.hour == 10 and ny_time.minute <= 45:
            return True
        return False

    def _get_liquidity_levels(
        self,
        candles_1m: list[Candle],
        candles_1h: list[Candle],
        candles_4h: list[Candle]
    ) -> list[LiquidityLevel]:
        levels: list[LiquidityLevel] = []
        if not candles_1m:
            return levels

        # Previous Day High / Low
        # We can approximate this by grouping 1h candles by date
        daily_highs = {}
        daily_lows = {}
        for c in candles_1h:
            ny_date = c.candle_time.astimezone(self.ny_tz).date()
            if ny_date not in daily_highs:
                daily_highs[ny_date] = c.high
                daily_lows[ny_date] = c.low
            else:
                daily_highs[ny_date] = max(daily_highs[ny_date], c.high)
                daily_lows[ny_date] = min(daily_lows[ny_date], c.low)

        sorted_dates = sorted(list(daily_highs.keys()))
        if len(sorted_dates) > 1:
            prev_date = sorted_dates[-2]
            levels.append(LiquidityLevel(level_type="PDH", price=daily_highs[prev_date], created_time=datetime.datetime.now(datetime.UTC)))
            levels.append(LiquidityLevel(level_type="PDL", price=daily_lows[prev_date], created_time=datetime.datetime.now(datetime.UTC)))

        # Asian Session High / Low (00:00 to 07:00 UTC based on indicator_engine)
        today_date = candles_1m[-1].candle_time.astimezone(datetime.UTC).date()
        asian_high = 0.0
        asian_low = float('inf')
        has_asian = False
        for c in candles_1m:
            utc_time = c.candle_time.astimezone(datetime.UTC)
            if utc_time.date() == today_date and 0 <= utc_time.hour < 7:
                has_asian = True
                asian_high = max(asian_high, c.high)
                asian_low = min(asian_low, c.low)
        
        if has_asian:
            levels.append(LiquidityLevel(level_type="ASIAN_HIGH", price=asian_high, created_time=datetime.datetime.now(datetime.UTC)))
            levels.append(LiquidityLevel(level_type="ASIAN_LOW", price=asian_low, created_time=datetime.datetime.now(datetime.UTC)))

        return levels

    def _detect_sweeps(self, candles: list[Candle], levels: list[LiquidityLevel]) -> list[LiquiditySweep]:
        sweeps = []
        if not candles or not levels:
            return sweeps

        # Look at the last 15 candles to see if any swept a level
        recent_candles = candles[-15:]
        for level in levels:
            for c in recent_candles:
                swept = False
                rejected = False
                if "HIGH" in level.level_type or level.level_type == "PDH":
                    # BSL Sweep
                    if c.high > level.price and c.close < level.price:
                        swept = True
                        rejected = True
                elif "LOW" in level.level_type or level.level_type == "PDL":
                    # SSL Sweep
                    if c.low < level.price and c.close > level.price:
                        swept = True
                        rejected = True
                
                if swept:
                    sweeps.append(LiquiditySweep(
                        level=level,
                        sweep_time=c.candle_time,
                        rejected=rejected
                    ))
                    break # Only record one sweep per level recently
        return sweeps

    def _find_fvgs(self, candles: list[Candle], timeframe: str) -> list[FVG]:
        fvgs = []
        if len(candles) < 3:
            return fvgs

        # Look back over recent candles to find FVGs and check if mitigated
        lookback = min(len(candles), 100)
        for i in range(len(candles) - lookback, len(candles) - 2):
            c1 = candles[i]
            c2 = candles[i+1]
            c3 = candles[i+2]

            is_bullish = c3.low > c1.high
            is_bearish = c3.high < c1.low

            if is_bullish:
                fvg = FVG(
                    timeframe=timeframe,
                    is_bullish=True,
                    top=c3.low,
                    bottom=c1.high,
                    mitigated=False,
                    created_time=c2.candle_time
                )
            elif is_bearish:
                fvg = FVG(
                    timeframe=timeframe,
                    is_bullish=False,
                    top=c1.low,
                    bottom=c3.high,
                    mitigated=False,
                    created_time=c2.candle_time
                )
            else:
                continue

            # Check mitigation by subsequent candles
            for c_future in candles[i+3:]:
                if fvg.is_bullish:
                    # Bullish FVG mitigated if price goes below bottom
                    if c_future.low <= fvg.bottom:
                        fvg.mitigated = True
                        fvg.mitigated_time = c_future.candle_time
                        break
                else:
                    # Bearish FVG mitigated if price goes above top
                    if c_future.high >= fvg.top:
                        fvg.mitigated = True
                        fvg.mitigated_time = c_future.candle_time
                        break
            
            fvgs.append(fvg)

        return fvgs

    def _find_ifvgs(self, fvgs: list[FVG], recent_candles: list[Candle]) -> list[FVG]:
        # An IFVG is an FVG that has been fully mitigated (traded through) 
        # and has now flipped its role. (e.g. Bullish FVG mitigated becomes Bearish IFVG resistance).
        ifvgs = []
        for fvg in fvgs:
            if not fvg.mitigated:
                continue
            
            # If it's a 1m FVG that was traded through, it's an IFVG.
            # Has price come back to retest it?
            ifvg = fvg.model_copy()
            # Invert its role
            ifvg.is_bullish = not fvg.is_bullish
            ifvgs.append(ifvg)
            
        return ifvgs

    def build_snapshot(
        self,
        candles_by_tf: dict[str, list[Candle]],
        current_time: datetime.datetime,
        cycle_tf: str = "5m",
    ) -> SMCSnapshot:
        c1m = candles_by_tf.get("1m", [])
        c5m = candles_by_tf.get("5m", [])
        c15m = candles_by_tf.get("15m", [])
        c30m = candles_by_tf.get("30m", [])
        c1h = candles_by_tf.get("1h", [])
        c4h = candles_by_tf.get("4h", [])

        c_ltf = c5m if cycle_tf == "15m" and c5m else c1m
        if not c_ltf:
            return SMCSnapshot()

        is_po3 = self._is_po3_time(current_time)
        levels = self._get_liquidity_levels(c_ltf, c1h, c4h)
        sweeps = self._detect_sweeps(c_ltf, levels)

        # HTF Gaps
        if cycle_tf == "15m":
            fvgs_htf1 = self._find_fvgs(c1h, "1h")
            fvgs_htf2 = self._find_fvgs(c4h, "4h")
        else:
            fvgs_htf1 = self._find_fvgs(c15m, "15m")
            fvgs_htf2 = self._find_fvgs(c30m, "30m")
        active_htf_fvgs = [f for f in fvgs_htf1 + fvgs_htf2 if not f.mitigated]

        # LTF Gaps and IFVGs
        ltf_name = "5m" if cycle_tf == "15m" else "1m"
        fvgs_ltf = self._find_fvgs(c_ltf, ltf_name)
        active_ifvgs = self._find_ifvgs(fvgs_ltf, c_ltf)

        # Check for SMC Setup
        # Liquidity Sweep + HTF Gap Delivery + LTF IFVG + DOL
        setup_valid = False
        setup_direction: Optional[SignalDirection] = None
        dol: Optional[LiquidityLevel] = None

        current_price = c_ltf[-1].close

        # Very basic setup logic:
        # If we have a recent BSL sweep (PDH/Asian High) -> Look for Shorts
        # We need price to be in a Bearish HTF FVG or Bearish IFVG.
        
        recent_bsl_sweep = any(s for s in sweeps if "HIGH" in s.level.level_type or s.level.level_type == "PDH")
        recent_ssl_sweep = any(s for s in sweeps if "LOW" in s.level.level_type or s.level.level_type == "PDL")

        bearish_ifvgs_near = [i for i in active_ifvgs if not i.is_bullish and i.bottom <= current_price <= i.top]
        bullish_ifvgs_near = [i for i in active_ifvgs if i.is_bullish and i.bottom <= current_price <= i.top]

        if recent_bsl_sweep and bearish_ifvgs_near:
            setup_valid = True
            setup_direction = SignalDirection.SELL
            # DOL is the next major low
            lows = [l for l in levels if "LOW" in l.level_type or l.level_type == "PDL"]
            if lows:
                dol = lows[0] # Simplification
        elif recent_ssl_sweep and bullish_ifvgs_near:
            setup_valid = True
            setup_direction = SignalDirection.BUY
            # DOL is the next major high
            highs = [l for l in levels if "HIGH" in l.level_type or l.level_type == "PDH"]
            if highs:
                dol = highs[0]

        return SMCSnapshot(
            active_htf_fvgs=active_htf_fvgs,
            recent_sweeps=sweeps,
            active_ifvgs=active_ifvgs,
            dol=dol,
            is_po3_time=is_po3,
            smc_setup_valid=setup_valid,
            setup_direction=setup_direction
        )

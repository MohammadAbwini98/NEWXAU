# Phase 07 - Shadow-Mode Validation and Backtesting

## Goal

Validate whether AI news analysis improves XAUUSD trading decisions before allowing it to affect live trades.

## Shadow mode definition

In shadow mode:

```text
- News is collected.
- AI analysis is generated.
- Strategy calculates what it would have done with news.
- Real trading behavior is not changed.
- Validation results are stored.
```

## Validation horizons

Evaluate each news analysis against future XAUUSD movement at:

```text
5 minutes
15 minutes
30 minutes
60 minutes
240 minutes
```

For each horizon, store:

```text
price_at_analysis
price_at_horizon
return_pct
predicted_direction
actual_direction
was_correct
```

## Actual direction logic

Example:

```text
return_pct > +threshold => UP
return_pct < -threshold => DOWN
otherwise => NEUTRAL
```

Suggested thresholds:

```text
5m:   0.03% to 0.05%
15m:  0.05% to 0.08%
30m:  0.08% to 0.12%
60m:  0.10% to 0.20%
240m: 0.20% to 0.40%
```

Tune based on XAUUSD volatility.

## Metrics to calculate

```text
Directional accuracy by event type
Directional accuracy by confidence bucket
Average return after BUY-bias news
Average return after SELL-bias news
False positive rate
False negative rate
Impact of blocking high-risk windows
Strategy P&L with news shadow vs without news
Drawdown with news shadow vs without news
```

## Event-type reports

Generate separate reports for:

```text
CPI
FOMC
NFP
Fed speeches
War escalation
General gold news
```

## Confidence bucket evaluation

Buckets:

```text
0.50-0.59
0.60-0.69
0.70-0.79
0.80-0.89
0.90-1.00
```

The system should only allow trading impact from confidence buckets that prove useful.

## Shadow comparison logic

For each strategy signal, calculate two versions:

```text
baseline_decision = strategy without news
news_decision = strategy with news state
```

Store:

```text
baseline_action
news_adjusted_action
baseline_position_size
news_adjusted_position_size
baseline_expected_score
news_adjusted_score
actual_outcome
```

## Backtesting limitation

Historical AI news analysis may be difficult unless historical news is stored. For first release, use forward shadow validation.

Later, if you build a historical news dataset, run full walk-forward testing.

## Minimum validation period before live influence

Recommended:

```text
At least 4 weeks of shadow mode
At least 10+ high-impact macro events if possible
At least 100+ analyzed news items
At least 20+ actual strategy signals with active news state
```

If data is limited, enable only very conservative behavior first, such as event-window blocking.

## Promotion criteria

Enable `NEWS_STRATEGY_WEIGHT_ENABLED=true` only if:

```text
High-relevance news has positive directional accuracy.
News-adjusted shadow signals reduce drawdown or improve risk-adjusted return.
False positives are acceptable.
AI JSON output is stable.
No collector instability affects strategy.
```

Enable `NEWS_TRADE_BLOCK_ENABLED=true` only if:

```text
High-impact event windows show worse performance or excessive volatility.
Blocking those windows would have reduced drawdown or bad fills.
```

## Reports

Create scheduled reports:

```text
Daily news impact report
Weekly shadow-mode report
Event-specific report after CPI/FOMC/NFP
Monthly promotion-readiness report
```

## Acceptance criteria

- Each AI analysis is evaluated against future price movement.
- Dashboard shows hit rate by event type.
- Strategy comparison with/without news is stored.
- System can prove whether news is helping before live rollout.

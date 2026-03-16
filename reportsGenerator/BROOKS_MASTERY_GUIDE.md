# Al Brooks Price Action Mastery Guide

> **Source:** Al Brooks — *Trading Price Action Trends*, *Trading Price Action Trading Ranges*, *Trading Price Action Reversals* (Wiley Trading Series)
> **Purpose:** Institutional-grade reference for report generators. Pattern lessons, trap taxonomy, probability framework, and educational content.
> **Patterns:** 24 (12 LONG, 12 SHORT) — aligned with `AlBrooksAnalyzer` in `scanner_analyzer.py`

---

## 1. PATTERN CATALOG

### 1A. LONG PATTERNS (12)

---

#### `high_1` — High 1: First Pullback in Bull Trend

**Brooks Source:** *Ranges* Ch.17 — "A High 1 is the first bar whose high is above the prior bar's high after a pullback of one or more bars."

**What It Is:** The very first pullback in a new or strong bull trend. Price dips briefly then resumes higher. This is the earliest re-entry after a trend starts.

**Win Rate:** 55-65% (lower than High 2 because the pullback may not be complete)

**Why It Works:** In a strong bull trend, the first pause is caused by profit-taking, not by bears gaining control. Buyers who missed the initial move are waiting for any dip. When price ticks above the prior bar's high, those buyers flood in. The pullback was too shallow for bears to build conviction.

**Confirmation Bar:** Next bar must trade above the High 1 signal bar's high. A strong bull bar closing near its high is ideal.

**Measured Move:** From the start of the trend to the High 1 signal bar = Leg 1. Project Leg 1 length upward from the High 1 entry = Target.

**Invalidation:** If price drops below the pullback low before triggering, the High 1 is dead. If the trend has already had multiple legs, it's likely a High 3 or 4 instead.

**Trap Association:** `late_move_trap` if entered after 3+ legs of trend.

**Lesson Template:** *"This is a High 1 setup — the first pullback in a bull trend. Al Brooks teaches that the first pullback is often the best entry because momentum is strongest. Bulls who missed the initial move are eager to buy any dip, and the pullback is typically too shallow for bears to build a position. The key risk is that the pullback isn't complete — a High 2 (second pullback) is generally higher probability."*

---

#### `high_2` — High 2: Second Entry Long After Pullback

**Brooks Source:** *Ranges* Ch.17 — "A High 2 is the second signal bar above the prior bar's high... it is effectively a two-legged pullback."

**What It Is:** Two-legged pullback in a bull trend. The market pulls back, makes a small bounce, pulls back again (second leg), then resumes. This is Brooks' highest-probability trend continuation entry.

**Win Rate:** 60-70%

**Why It Works:** The two-legged pullback traps bears twice. First pullback: bears short, bulls scale in. Second pullback: remaining bears add shorts. When price breaks above the second pullback high, ALL those bears are trapped. Their covering adds explosive buying pressure. Brooks: *"High 2 is a failed bear breakout that becomes a bull signal."*

**Confirmation Bar:** Strong bull bar closing on its high, on the bar after the signal bar. Volume increase confirms institutional participation.

**Measured Move:** Leg1 (from trend start to first pullback low) = Leg2 (projected from High 2 entry). Also: height of the two-legged pullback projected upward.

**Invalidation:** If the second pullback breaks below the first pullback's low, the trend may be transitioning to a trading range. Also invalid if Always-In direction has shifted to NEUTRAL or SHORT.

**Trap Association:** `bear_trap` — bears who shorted both pullbacks get squeezed.

**Lesson Template:** *"This is a High 2 — the highest-probability bull continuation pattern. Two pullback legs have trapped short sellers. When price now breaks above the High 2 signal bar, those trapped bears must cover, creating a surge of buying pressure. Brooks says this is the 'bread and butter' of trend trading. The two-legged structure confirms the pullback is complete — the trend is ready to resume."*

---

#### `high_3` — High 3: Third Push Up (Often Climax)

**Brooks Source:** *Trends* Ch.15 — "After three pushes, the trend is more likely to reverse... traders should look for signs of exhaustion."

**What It Is:** Third pullback entry in a bull trend. While still valid, three pushes often signal the trend is getting old. This is the beginning of climax territory.

**Win Rate:** 45-55% (reduced due to exhaustion risk)

**Why It Works:** Trend still has some momentum, but it's weakening. Each push has less force (shrinking bars, lower volume). Late bulls are entering. Smart money may be taking profits into the late-entry buying.

**Confirmation Bar:** Must be very strong (large bull bar, high volume) to overcome the exhaustion risk. Weak confirmation = probable failure.

**Measured Move:** Less reliable. If Leg 3 < Leg 2 < Leg 1, the trend is decelerating. Target the height of the smallest leg projected from entry.

**Invalidation:** Divergence on RSI/MACD, decreasing volume, bars with long upper tails (selling pressure).

**Trap Association:** `late_move_trap` — entering after 3 pushes is a classic retail trap.

**Lesson Template:** *"This is a High 3 — three pushes up in a bull trend. Al Brooks warns that three-push patterns often signal exhaustion. While the trend may continue, each leg is typically weaker. This is where 'wedge' patterns form — three pushes with weakening momentum often precede reversals. Position size should be reduced, stops tightened, and traders should watch for climax signals (large bars on high volume followed by reversal)."*

---

#### `high_4` — High 4: Fourth Entry (Trend Getting Old)

**Brooks Source:** *Trends* Ch.16 — "By the fourth push, most trends have exhausted their buying pressure."

**What It Is:** Fourth pullback entry. The trend is very old. This is a low-probability continuation and high-probability reversal zone.

**Win Rate:** 35-45% (trend is exhausted)

**Why It Works:** Rarely works for continuation. Most value is as a REVERSAL signal — if the High 4 fails, it often marks the end of the trend.

**Confirmation Bar:** Requires overwhelming strength. Without it, this is a sell signal disguised as a buy signal.

**Measured Move:** Minimal — target the most recent swing high at best.

**Invalidation:** Almost always. Four-push trends rarely produce a fifth leg. The probability favors a trading range or reversal.

**Trap Association:** `late_move_trap` — classic "buying the top" trap.

**Lesson Template:** *"This is a High 4 — the trend has had four pushes and is likely exhausted. Al Brooks teaches that by the fourth push, most buying pressure has been spent. Late retail buyers are entering while institutions are selling to them. This setup has LOW conviction for continuation. Consider it a warning sign — if this push fails, it will likely mark the trend's end. Reduce position size dramatically or wait for a reversal setup instead."*

---

#### `double_bottom` — Double Bottom: W Pattern Reversal

**Brooks Source:** *Reversals* Ch.8 — "A double bottom is simply two attempts to break below a price level that both fail."

**What It Is:** Price tests a low twice and holds both times, forming a "W" shape. The second test creates a bear trap.

**Win Rate:** 60-70% (when at significant support with strong reversal bars)

**Why It Works:** Bears tried twice to push price lower and failed both times. Every bear who shorted the second test is now trapped. When price breaks above the neckline (the high between the two lows), trapped bears covering + new bulls entering = strong rally. Brooks: *"The second test of the low is the market's way of confirming that bears cannot break through."*

**Confirmation Bar:** Strong bull bar closing above the neckline (high between the two lows).

**Measured Move:** Height from the double bottom to the neckline, projected upward from the neckline.

**Invalidation:** If the second low breaks significantly below the first (more than 1-2%), it's not a double bottom — it's a lower low in a continuing bear trend.

**Trap Association:** `bear_trap` — bears who shorted the second test get squeezed.

**Lesson Template:** *"This is a Double Bottom reversal — bears tried twice to push below support and failed. The second test is critical: it proves bears lack the power to continue lower. All shorts from both tests are now trapped. When price breaks above the neckline, covering creates a powerful rally. The measured move target is the height of the W projected from the neckline."*

---

#### `higher_low` — Higher Low: Trend Continuation

**Brooks Source:** *Trends* Ch.2 — "A series of higher lows is the definition of an uptrend."

**What It Is:** Each pullback low is higher than the previous pullback low. This is the most fundamental bullish structure.

**Win Rate:** 55-65%

**Why It Works:** Higher lows mean bears are getting weaker with each attempt. Each selling wave is less powerful than the last. Bulls are stepping in earlier and at higher prices, showing increasing confidence.

**Confirmation Bar:** Any bull bar that holds above the prior swing low.

**Measured Move:** Leg1=Leg2 from the most recent higher low.

**Invalidation:** If the pullback breaks below the prior swing low (becomes a lower low), the higher-low structure is broken.

**Trap Association:** None specific — this is a structural observation, not a trapped-trader pattern.

**Lesson Template:** *"This Higher Low confirms the bullish structure — each pullback is shallower than the last, showing bears are losing power. Buyers are stepping in at increasingly higher prices, demonstrating growing confidence. As long as the higher-low sequence holds, the uptrend is intact. The key level to watch is the prior swing low — a break below it would end the pattern."*

---

#### `breakout_pullback` — Breakout Pullback: Retest of Breakout Level

**Brooks Source:** *Ranges* Ch.5 — "The best breakout pullback entries come when the pullback tests the breakout level and finds support where there used to be resistance."

**What It Is:** After a breakout above resistance, price pulls back to test the breakout level. Former resistance becomes support. Entry on the bounce.

**Win Rate:** 65-75% (one of the highest probability setups)

**Why It Works:** The breakout proved buyers can push through resistance. The pullback lets latecomers enter at the breakout level. When former resistance holds as support, it confirms the breakout's validity. Traders who missed the initial breakout now have a "second chance" entry.

**Confirmation Bar:** Bull reversal bar at the breakout level. Best if it has a long lower tail (showing buyers defending the level).

**Measured Move:** Height of the trading range that price broke out from, projected from the breakout level.

**Invalidation:** If the pullback drops back inside the prior range (below the breakout level), the breakout has failed.

**Trap Association:** `bull_trap` if the breakout itself was weak; `none` if the breakout was strong.

**Lesson Template:** *"This is a Breakout Pullback — price broke above resistance, pulled back to retest the level, and is bouncing. This is one of Brooks' highest-probability setups because it combines two powerful forces: (1) the breakout proved buyers can push through, and (2) the successful retest proves the level has flipped from resistance to support. Old resistance becoming new support is one of the most reliable principles in technical analysis."*

---

#### `wedge_reversal` — Wedge Reversal: Three Pushes Down Reversing

**Brooks Source:** *Reversals* Ch.7 — "A wedge is three pushes in one direction, each with weakening momentum... The third push is the exhaustion point."

**What It Is:** Three descending pushes with each push showing less momentum (smaller bars, less volume, divergences). After the third push fails to make a significant new low, price reverses upward.

**Win Rate:** 60-70%

**Why It Works:** Each push down is weaker, meaning bears are running out of sellers. By the third push, the last bears have entered. There's no one left to sell. When buying emerges, there's a vacuum above because all the selling pressure has been absorbed. Brooks: *"Wedges are climactic moves. Three pushes with weakening momentum = prepare for reversal."*

**Confirmation Bar:** Strong bull reversal bar after the third push. Best if it engulfs the prior bear bar.

**Measured Move:** Height of the entire wedge (from first push high to third push low) projected upward from the reversal point. Also: the start of the wedge (first push high) is a common target.

**Invalidation:** If the third push has STRONGER momentum than the second (accelerating, not decelerating), it's not a wedge — it's a trend acceleration.

**Trap Association:** `bear_trap` — bears who entered on the third push get trapped.

**Lesson Template:** *"This is a Wedge Reversal — three descending pushes with declining momentum. Each push trapped more bears while absorbing remaining selling pressure. By the third push, there are no sellers left. Al Brooks teaches that wedges are one of the most reliable reversal patterns because they represent complete exhaustion. The measured move target is the top of the wedge."*

---

#### `expanding_triangle` — Expanding Triangle Bottom

**Brooks Source:** *Reversals* Ch.17 — "Expanding triangles form when both sides become increasingly aggressive."

**What It Is:** Price makes wider and wider swings at a bottom — lower lows AND higher highs alternating. This shows extreme two-sided trading that eventually resolves upward.

**Win Rate:** 50-60%

**Why It Works:** Both bulls and bears are fighting aggressively. The expanding range shows increasing volatility. Resolution comes when one side exhausts itself. At a bottom, the final lower low traps all bears, and the subsequent rally breaks above prior highs with force.

**Confirmation Bar:** Strong bull bar that breaks above the upper boundary of the expanding pattern.

**Measured Move:** Width of the widest swing in the triangle, projected from the breakout point.

**Invalidation:** If the pattern continues expanding without resolution (more than 5 swings), it becomes random chop rather than a tradeable pattern.

**Trap Association:** `bear_trap` — bears who sold the final lower low are trapped when the reversal comes with force.

**Lesson Template:** *"This is an Expanding Triangle at a bottom — both bulls and bears are increasingly aggressive, creating wider swings. The final push lower traps the last bears. When the reversal comes, it's often explosive because all that trapped energy releases at once. This pattern requires patience — wait for the breakout above the upper boundary before entering."*

---

#### `failed_breakdown` — Failed Breakdown: Bear Trap

**Brooks Source:** *Reversals* Ch.11 — "A failed breakout is one of the most reliable trading signals because trapped traders must exit."

**What It Is:** Price breaks below a support level but immediately reverses back above it. The breakdown "failed." Every bear who shorted the breakdown is now trapped.

**Win Rate:** 65-75%

**Why It Works:** This is pure trapped-trader mechanics. Bears saw the breakdown and shorted aggressively. When price reverses back above support, EVERY one of those shorts is losing money. As they cover (buy to close), their covering adds buying pressure that accelerates the rally. Brooks: *"80% of breakouts fail."* When they fail, trade the opposite direction.

**Confirmation Bar:** Strong bull bar closing back above the broken support level. High volume confirms institutions were involved.

**Measured Move:** Height of the failed breakdown (distance from support to the breakdown low) projected upward from support.

**Invalidation:** If price breaks back below support after the initial bounce, the failure itself failed — avoid.

**Trap Association:** `bear_trap` — textbook bear trap.

**Lesson Template:** *"This is a Failed Breakdown — price broke below support but immediately reversed. Brooks teaches that 80% of breakouts fail, and failed breakouts create the strongest signals because trapped traders must exit. Every bear who shorted the breakdown is now losing money, and their covering fuels the rally. This is one of the highest-conviction setups in price action trading."*

---

#### `ema_bounce` — EMA Bounce: Support at Moving Average

**Brooks Source:** *Trends* Ch.12 — "In a strong trend, the 20-bar EMA acts as a magnet... pullbacks to the EMA are buying opportunities."

**What It Is:** In an uptrend, price pulls back to the 20-period EMA and bounces. The EMA acts as dynamic support.

**Win Rate:** 55-65%

**Why It Works:** In strong trends, the EMA represents fair value. Institutional algorithms often have buy orders at the EMA. When price touches the EMA and bounces, it shows the trend's support structure is intact. Brooks: *"In a strong bull trend, the first pullback to the 20 EMA is the best buying opportunity."*

**Confirmation Bar:** Bull bar closing above the EMA after touching it. Best if the bar's low is at or near the EMA and the close is well above.

**Measured Move:** Distance from the EMA to the prior swing high, projected from the EMA bounce point.

**Invalidation:** If price closes decisively below the EMA (full bar below), the trend may be weakening and transitioning to a trading range.

**Trap Association:** None — this is a trend-following setup, not a trap pattern.

**Lesson Template:** *"This is an EMA Bounce — price pulled back to the 20-period EMA in an uptrend and is bouncing. Brooks teaches that in strong trends, the EMA acts as dynamic support because institutional algorithms place buy orders there. The bounce confirms the trend is healthy and the pullback is complete. The key risk is if price closes below the EMA — that would signal the trend is weakening."*

---

#### `tight_trading_range_breakout` — Tight TR Breakout: Compression Release

**Brooks Source:** *Ranges* Ch.22 — "A tight trading range has at least 3-5 bars with significant overlap... the eventual breakout is often strong."

**What It Is:** Price compresses into a very tight range (low volatility), then breaks out to the upside. The compression stores energy that releases explosively.

**Win Rate:** 55-65% (direction uncertain until breakout occurs)

**Why It Works:** Tight ranges represent equilibrium — buyers and sellers are balanced. When one side finally wins, the losing side must exit, creating a one-sided move. The tighter the range, the more explosive the eventual breakout. Brooks: *"Tight trading ranges are coiled springs."*

**Confirmation Bar:** Strong breakout bar with a large body closing near its high, ideally on increased volume. Weak breakout bars (small body, long upper tail) often fail.

**Measured Move:** Height of the tight range projected from the breakout point.

**Invalidation:** If the breakout bar is weak (small body, doji-like) or if price immediately pulls back into the range, the breakout has failed — expect the opposite direction.

**Trap Association:** `bull_trap` if the breakout fails; `bear_trap` if it succeeds (bears who faded the range top are trapped).

**Lesson Template:** *"This is a Tight Trading Range Breakout — price compressed into a narrow range, building energy, and has now broken out to the upside. Brooks compares tight ranges to coiled springs — the longer the compression, the more powerful the release. Both sides were trapped in the range; now the bears must cover, adding fuel to the move. Watch for follow-through on the next 1-2 bars to confirm the breakout is real."*

---

### 1B. SHORT PATTERNS (12)

---

#### `low_1` — Low 1: First Pullback in Bear Trend

**Brooks Source:** *Ranges* Ch.17 — "Low 1 is the first bar whose low is below the prior bar's low after a bounce."

**Win Rate:** 55-65%

**Why It Works:** Mirror of High 1. In a strong bear trend, the first bounce is just profit-taking by shorts, not a real reversal. When price drops below the prior bar's low, it confirms the bear trend is resuming. Late shorts who missed the initial move enter here.

**Trap Association:** `late_move_trap` if the bear trend is already extended.

**Lesson Template:** *"This is a Low 1 — the first pullback in a bear trend. The bounce was just short-covering, not real buying. The trend is resuming as sellers re-enter. The risk is that the pullback isn't complete — a Low 2 (second pullback) would provide a higher-probability entry."*

---

#### `low_2` — Low 2: Second Entry Short After Pullback

**Brooks Source:** *Ranges* Ch.17 — "A Low 2 is the second time the market drops below a prior bar's low after a rally... it is the mirror image of the High 2."

**Win Rate:** 60-70%

**Why It Works:** Mirror of High 2. Two-legged bounce traps bulls twice. Both sets of trapped longs must sell when price breaks below the Low 2 signal bar. Their selling adds to bear pressure.

**Trap Association:** `bull_trap` — bulls who bought both bounces get squeezed.

**Lesson Template:** *"This is a Low 2 — the highest-probability bear continuation pattern. Two bounce legs have trapped bulls who thought the trend was reversing. When price now breaks below the Low 2 signal bar, those trapped bulls must sell, creating a cascade of selling pressure. This is the 'bread and butter' of bear trend trading."*

---

#### `low_3` — Low 3: Third Push Down (Often Climax)

**Brooks Source:** *Trends* Ch.15 — Three pushes = potential exhaustion.

**Win Rate:** 45-55%

**Trap Association:** `late_move_trap`

**Lesson Template:** *"This is a Low 3 — three pushes down, each with potentially weakening momentum. Al Brooks warns that three-push moves often signal exhaustion. This is where wedge bottoms form. Position size should be reduced and stops tightened. If this push fails to make a significant new low, a reversal may follow."*

---

#### `low_4` — Low 4: Fourth Entry (Trend Getting Old)

**Brooks Source:** *Trends* Ch.16

**Win Rate:** 35-45%

**Trap Association:** `late_move_trap`

**Lesson Template:** *"This is a Low 4 — the bear trend has had four pushes and is likely exhausted. Late short sellers are entering while smart money covers. This setup has LOW conviction for continuation. A failed Low 4 often marks the bottom."*

---

#### `double_top` — Double Top: M Pattern Reversal

**Brooks Source:** *Reversals* Ch.8 — "A double top is two failed attempts to break above a price level."

**Win Rate:** 60-70%

**Why It Works:** Mirror of double bottom. Bulls tried twice to break above resistance and failed. Every bull from both tests is trapped when price drops below the neckline.

**Trap Association:** `bull_trap`

**Lesson Template:** *"This is a Double Top reversal — bulls tried twice to break above resistance and failed. The second failure proves buyers cannot push through. All longs from both tests are trapped, and their selling when price breaks below the neckline creates powerful downside momentum. Target: height of the M projected downward from the neckline."*

---

#### `lower_high` — Lower High: Bear Trend Continuation

**Brooks Source:** *Trends* Ch.2

**Win Rate:** 55-65%

**Lesson Template:** *"This Lower High confirms the bearish structure — each bounce is weaker than the last, showing bulls are losing power. Sellers are entering at increasingly lower prices. The key level is the prior swing high — a break above it would end the pattern."*

---

#### `breakdown_pullback` — Breakdown Pullback: Retest of Breakdown Level

**Brooks Source:** *Ranges* Ch.5

**Win Rate:** 65-75%

**Why It Works:** Mirror of breakout pullback. After a breakdown below support, price rallies back to test the level. Former support becomes resistance. Short the rejection.

**Trap Association:** `bear_trap` if the breakdown was weak; `none` if strong.

**Lesson Template:** *"This is a Breakdown Pullback — price broke below support, bounced to retest the level, and is being rejected. Former support is now resistance. This is one of the highest-probability setups because it confirms the breakdown's validity while offering an ideal entry with a tight stop above the former support level."*

---

#### `wedge_top` — Wedge Top: Three Pushes Up Reversing

**Brooks Source:** *Reversals* Ch.7

**Win Rate:** 60-70%

**Lesson Template:** *"This is a Wedge Top — three ascending pushes with declining momentum. Each push trapped more bulls while absorbing remaining buying pressure. By the third push, there are no buyers left. Brooks teaches this is one of the most reliable reversal patterns. The measured move target is the bottom of the wedge."*

---

#### `expanding_triangle_top` — Expanding Triangle Top

**Brooks Source:** *Reversals* Ch.17

**Win Rate:** 50-60%

**Lesson Template:** *"This is an Expanding Triangle at a top — increasingly aggressive swings in both directions. The final higher high traps the last bulls, and the reversal often comes with force. Wait for the breakdown below the lower boundary."*

---

#### `failed_breakout` — Failed Breakout: Bull Trap

**Brooks Source:** *Reversals* Ch.11 — "80% of breakout attempts fail."

**Win Rate:** 65-75%

**Why It Works:** Bulls saw the breakout and bought aggressively. When price reverses back below resistance, every one of those longs is losing money. Their selling adds to the downside pressure.

**Trap Association:** `bull_trap` — textbook bull trap.

**Lesson Template:** *"This is a Failed Breakout — price broke above resistance but immediately reversed. Brooks' '80% of breakouts fail' rule applies here. Every bull who bought the breakout is now trapped. Their forced selling fuels the decline. Failed breakouts produce the strongest signals because trapped traders must exit."*

---

#### `ema_rejection` — EMA Rejection: Resistance at Moving Average

**Brooks Source:** *Trends* Ch.12

**Win Rate:** 55-65%

**Lesson Template:** *"This is an EMA Rejection — price bounced to the 20-period EMA in a downtrend and is being rejected. The EMA acts as dynamic resistance. Institutional sellers are defending this level. The rejection confirms the bear trend is intact. If price closes above the EMA, the bear thesis weakens."*

---

#### `climactic_exhaustion` — Climactic Exhaustion: Parabolic Reversal

**Brooks Source:** *Trends* Ch.15, *Reversals* Ch.6 — "A buy climax is a series of increasingly large bull bars... it is unsustainable and will be followed by a correction."

**Win Rate:** 55-65% (for the reversal trade)

**Why It Works:** Parabolic moves attract the last buyers. They buy because price is rising fast (FOMO). But there's no one left to buy after them. When buying exhausts itself, the reversal is sharp because: (1) no new buyers, (2) profit-taking floods in, (3) new shorts enter. The bigger the climax, the sharper the reversal.

**Trap Association:** `late_move_trap` + `bull_trap`

**Lesson Template:** *"This is Climactic Exhaustion — price accelerated into a parabolic move with increasingly large bars. Brooks teaches that climaxes are unsustainable — the LAST buyers are entering out of FOMO while smart money sells to them. When the buying exhausts itself, the reversal is sharp. Look for a strong reversal bar on high volume. The bigger the climax, the larger the expected correction."*

---

## 2. TRAP TYPE TAXONOMY

### Overview

Traps are the core engine of price action trading. Al Brooks: *"Recognizing traps is more important than recognizing setups."* A trap is when traders enter in one direction and are immediately forced to exit, with their exits fueling the opposite move.

### 2A. `bull_trap`

**Definition:** A failed breakout above resistance or failed reversal to the upside. Bulls enter expecting continuation but price reverses, trapping them.

**Brooks Source:** *Reversals* Ch.11 — Failed breakouts; *Ranges* Ch.5 — "Most breakouts of trading ranges fail."

**Mechanics:**
1. Price breaks above a resistance level (or a pattern signals "buy")
2. Bulls enter long positions, placing stops below the breakout level
3. Price reverses back below resistance
4. Bulls' stops are hit, their selling adds to bear pressure
5. The reversal accelerates as trapped bulls scramble to exit

**How to Identify:**
- Breakout bar is weak (small body, long upper tail, low volume)
- No follow-through on the bar after the breakout
- Price quickly reverses back inside the prior range
- Volume spikes on the reversal, not on the breakout

**How to Trade:** Short when price closes back below the broken resistance level. Stop above the failed breakout high. Target: opposite end of the prior range.

**Severity Scale:**
- MILD: Price drifts back below slowly, gives time to exit
- MODERATE: Price reverses within 2-3 bars, most bulls trapped
- SEVERE: Immediate reversal on same or next bar, violent selloff

**Report Narrative:** *"Bull trap detected — price broke above [level] but failed to hold. Breakout was weak ([detail: small bar / low volume / long tail]). Trapped bulls are now exiting, adding fuel to the decline. This failed breakout increases the probability of a move to the opposite side of the range."*

---

### 2B. `bear_trap`

**Definition:** A failed breakdown below support or failed reversal to the downside. Bears enter expecting continuation but price reverses, trapping them.

**Brooks Source:** *Reversals* Ch.11 — mirror of bull trap.

**Mechanics:** Mirror of bull trap. Bears short the breakdown, price reverses above support, bears' stops are hit, their covering (buying to close) adds to the rally.

**How to Identify:**
- Breakdown bar is weak (small body, long lower tail)
- No follow-through below
- Quick reversal back above support
- Volume spikes on the reversal

**Severity Scale:** Same as bull trap (MILD/MODERATE/SEVERE).

**Report Narrative:** *"Bear trap detected — price broke below [level] but failed to hold. Breakdown was weak. Trapped bears are now covering (buying to close), fueling the rally. This failed breakdown increases the probability of a move to [upper target]."*

---

### 2C. `late_move_trap`

**Definition:** Entering a trend after 3+ pushes/legs, when exhaustion is imminent. The trader enters just as the trend is about to reverse.

**Brooks Source:** *Trends* Ch.15 — "Climaxes often occur after the third push." *Trends* Ch.16 — "By the fourth push, most trends have exhausted their buying pressure."

**Mechanics:**
1. Trend has been running for 3+ legs
2. Late trader sees the trend and enters (FOMO)
3. Momentum is fading (smaller bars, divergences)
4. Smart money is exiting into the late-entry buying
5. Trend reverses, late entry immediately underwater

**How to Identify:**
- Count 3+ pushes/legs in the current trend
- Each leg has smaller bars than the previous
- RSI/MACD divergence (price higher but indicator lower)
- Bars with long tails against the trend direction
- Volume declining on each push

**How to Trade:** DON'T enter with the trend. Instead, wait for the reversal signal after the 3rd/4th push and trade the reversal.

**Report Narrative:** *"Late-move trap warning — this trend has had [N] pushes. Brooks teaches that after 3+ pushes, exhaustion is likely. Each leg shows [declining momentum / smaller bars / divergence]. Entering with the trend here has low probability. Consider waiting for a reversal setup instead."*

---

### 2D. `failed_reversal_trap`

**Definition:** A reversal pattern forms but fails, and the original trend resumes violently. Traders who bet on the reversal are trapped.

**Brooks Source:** *Reversals* Ch.1 — "Not all reversal patterns lead to reversals... when a reversal fails, the trend resumes with even more force."

**Mechanics:**
1. Reversal signal appears (reversal bar, double top/bottom, wedge)
2. Counter-trend traders enter based on the reversal signal
3. The reversal fails — trend resumes through the reversal point
4. Counter-trend traders' stops are hit
5. The trend accelerates as trapped reversal traders exit

**How to Identify:**
- Reversal pattern forms but the "confirmation bar" fails (weak, doesn't follow through)
- Price quickly returns to the trend direction
- The reversal was against a very strong trend (Always-In firmly established)

**Severity:** Often SEVERE — failed reversals produce the strongest continuation moves because the trapped counter-trend traders add fuel.

**Report Narrative:** *"Failed reversal trap — a [pattern] reversal signal appeared but failed. Counter-trend traders who entered the reversal are now trapped and must exit. Their forced exits are accelerating the original trend. Failed reversals are among the strongest continuation signals."*

---

### 2E. `vacuum_fill_trap`

**Definition:** Price fills a gap or vacuum zone then reverses, trapping traders who expected continuation through the gap.

**Brooks Source:** *Trends* Ch.9 (Gaps), *Ranges* Ch.6 — "Gaps act as magnets... once filled, the original direction often resumes."

**Mechanics:**
1. A gap (or vacuum zone) exists from a prior strong move
2. Price moves to fill the gap
3. Traders expect the gap fill to lead to continuation through the gap
4. Instead, price reverses after filling the gap
5. The original trend/direction resumes

**How to Identify:**
- Price approaching a known gap level
- Gap fill occurs on declining momentum
- Reversal bar forms at the gap fill level
- Volume picks up on the reversal, not the fill

**Report Narrative:** *"Vacuum fill trap — price filled the gap at [level] but is now reversing. Gaps act as magnets, but once filled, the pull disappears and the original trend often resumes. Traders who expected continuation through the gap are trapped."*

---

## 3. BAR READING FRAMEWORK

### Body Ratio Classification

| Body % of Range | Classification | Interpretation |
|-----------------|---------------|----------------|
| >70% | **Strong Trend Bar** | One side completely dominated. High conviction. |
| 50-70% | **Moderate Trend Bar** | Slight dominance. Acceptable for signals. |
| 30-50% | **Weak Bar** | Neither side convincing. Poor signal bar. |
| <30% | **Doji** | Pure indecision. Wait for next bar. |

### Tail Analysis

| Tail Position | Meaning |
|--------------|---------|
| **Long lower tail (bull)** | Buyers stepped in at lows, rejected selling pressure |
| **Long upper tail (bear)** | Sellers stepped in at highs, rejected buying pressure |
| **Long tails both sides** | Indecision, two-sided trading. Avoid trading this bar. |
| **No tails** | One-sided conviction. Very strong signal if body is large. |

### Bar Types (Brooks Classification)

| Type | Criteria | Signal Value |
|------|----------|-------------|
| **Bull Trend Bar** | Close > Open, close in upper 1/3 | Bullish continuation |
| **Bear Trend Bar** | Close < Open, close in lower 1/3 | Bearish continuation |
| **Bull Reversal Bar** | Close in upper 1/3 after prior bear bar(s) | Potential bottom |
| **Bear Reversal Bar** | Close in lower 1/3 after prior bull bar(s) | Potential top |
| **Inside Bar** | High < prior high AND low > prior low | Compression — breakout coming |
| **Outside Bar** | High > prior high AND low < prior low | Extreme two-sided trading |
| **Doji** | Body < 30% of range | Indecision |
| **Shaved Bar** | Close AT high (bull) or low (bear), no opposing tail | Maximum conviction |

### Consecutive Bar Patterns

| Pattern | Bars | Signal |
|---------|------|--------|
| 3+ consecutive bull bars | Strong bull trend | Buy pullbacks, DON'T short |
| 3+ consecutive bear bars | Strong bear trend | Sell rallies, DON'T buy |
| Alternating bull/bear | Trading range | Fade extremes, wait for breakout |
| Shrinking bars | Momentum fading | Tighten stops, watch for reversal |
| Expanding bars | Climax building | Prepare for exhaustion reversal |
| Overlapping bars | Congestion | Don't trade — wait for clarity |

### Context Rules

1. **A signal bar's value depends on WHERE it forms**, not just what it looks like
2. A bull reversal bar AT SUPPORT is 10x more valuable than one in the middle of nowhere
3. A bear reversal bar AFTER THREE PUSHES UP is a high-probability reversal signal
4. An inside bar in a strong trend = continuation. An inside bar in a range = meaningless.
5. Always read bars relative to the prior 3-5 bars, not in isolation

---

## 4. TREND EVOLUTION MODEL

### The Five Phases

Trends don't die suddenly — they evolve through predictable phases. Recognizing the current phase tells you how to trade.

```
STRONG_TREND → CHANNEL → BROAD_CHANNEL → TRADING_RANGE → REVERSAL
     (1)          (2)         (3)              (4)           (5)
```

#### Phase 1: STRONG TREND (Score: 80-100)

**Characteristics:**
- Consecutive trend bars (3+ in a row)
- Small or no pullbacks
- Bars closing near their extremes (no opposing tails)
- Price far from EMA (stretched)
- High volume

**How to Trade:** With the trend ONLY. Buy any dip (even 1-bar pullbacks). Don't short/fade.

**Transition Signal → Channel:** First significant pullback (2+ bars), bars start overlapping.

#### Phase 2: CHANNEL (Score: 60-80)

**Characteristics:**
- Price contained between parallel trend line and channel line
- Regular pullbacks to trend line
- Each leg makes new extreme (higher highs or lower lows)
- Bars show some overlap but trend direction maintained

**How to Trade:** Buy at trend line, take profit at channel line. Each pullback to the trend line is an entry. Brooks: *"Trade with the channel — buy lows, sell highs within the trend."*

**Transition Signal → Broad Channel:** Pullbacks become deeper, channel widens, bars overlap more.

#### Phase 3: BROAD CHANNEL (Score: 40-60)

**Characteristics:**
- Wide, sloppy channel
- Pullbacks retrace 50%+ of each leg
- Increasing overlap between bars
- Trading range behavior starting to appear
- Two-sided trading increases

**How to Trade:** Reduced position size. Take quick profits. Both long and short trades possible at extremes.

**Transition Signal → Trading Range:** Channel flattens, price moves sideways, clear support and resistance form.

#### Phase 4: TRADING RANGE (Score: 20-40)

**Characteristics:**
- Horizontal price movement between support and resistance
- Failed breakouts in both directions (Brooks: "80% of breakouts fail")
- Two-sided bars, lots of overlap
- EMA flattens

**How to Trade:** Buy at support, sell at resistance. Scalp. Don't hold for large moves. Iron condors in options. Brooks: *"In trading ranges, buy low, sell high, and get out quickly."*

**Transition Signal → Reversal:** Strong breakout in opposite direction of prior trend, with follow-through.

#### Phase 5: REVERSAL

**Characteristics:**
- Strong breakout from trading range in opposite direction
- New Always-In direction established
- Follow-through bars confirm new trend
- Volume confirms institutional participation

**How to Trade:** Enter new trend direction. The cycle restarts at Phase 1.

### Scoring Criteria

| Factor | Strong Trend | Channel | Broad Channel | Trading Range |
|--------|-------------|---------|---------------|---------------|
| Bar overlap (%) | <20% | 20-40% | 40-60% | >60% |
| Body-to-range ratio | >65% | 50-65% | 40-50% | <40% |
| Pullback depth | <30% of leg | 30-50% | 50-70% | >70% |
| EMA slope | Steep | Moderate | Slight | Flat |
| Consecutive same-direction bars | 4+ | 2-3 | 1-2 | Alternating |

---

## 5. CLIMAX DETECTION FRAMEWORK

### What Is a Climax?

A climax is an unsustainable burst of momentum that exhausts the trend. It's the "blow-off top" or "capitulation bottom." After a climax, expect at least a pullback and possibly a reversal.

### Climax Types

#### Type 1: Simple Climax
- **Definition:** Single bar with body > 2x average body size, closing at extreme
- **Volume:** Usually above average
- **Severity:** LOW — may cause a 1-3 bar pullback
- **Detection:** `abs(close - open) > 2 * avg_body_20 AND close in extreme 10% of range`

#### Type 2: Consecutive Climax
- **Definition:** 3+ consecutive bars with above-average bodies, all closing near extremes
- **Volume:** Increasing each bar
- **Severity:** MODERATE — expect a multi-bar pullback or transition to channel
- **Detection:** `3+ bars where body > 1.5 * avg_body AND close in extreme 25%`

#### Type 3: Parabolic Climax
- **Definition:** Accelerating move where each bar is LARGER than the previous
- **Volume:** Exponentially increasing
- **Severity:** HIGH — often marks the end of the trend
- **Detection:** `body[i] > body[i-1] for 3+ bars AND volume increasing`
- **Brooks Quote:** *"A buy climax is a series of increasingly large bull bars... it is unsustainable."*

#### Type 4: Channel Overshoot Climax
- **Definition:** Price breaks out above/below the channel line in an accelerating move
- **Volume:** Spike on the overshoot
- **Severity:** HIGH — overshooting the channel is a classic reversal signal
- **Detection:** `price crosses channel_line AND bar is strong trend bar AND prior bars were in channel`
- **Brooks Source:** *Reversals* Ch.5 — "Trend channel line overshoots are one of the strongest reversal signals."

### Climax Resolution

| Climax Severity | Expected Resolution | Timeframe |
|----------------|-------------------|-----------|
| LOW (simple) | 1-3 bar pullback, trend resumes | Immediate |
| MODERATE (consecutive) | Multi-bar pullback to EMA, may form channel | 5-10 bars |
| HIGH (parabolic/overshoot) | Deep pullback or full reversal | 10-20+ bars |

---

## 6. SPIKE-AND-CHANNEL PATTERN

### Definition

One of Brooks' most important patterns. A strong initial move (the "spike") followed by a slower, more orderly continuation (the "channel"). The spike sets the direction; the channel confirms it.

**Brooks Source:** *Trends* Ch.21 — "Spike and channel trends are among the most common and reliable trend patterns."

### Four Phases

```
Phase 1: SPIKE
├── 1-3 bars with body > 2x ATR
├── Closes near extremes
├── Usually gaps or large moves
└── Sets the Always-In direction

Phase 2: CHANNEL FORMATION
├── Price pulls back from spike high/low
├── Smaller bars, more overlap
├── Parallel lines form (trend line + channel line)
└── Lower slope than spike

Phase 3: CHANNEL TRADING
├── Regular pullbacks to trend line
├── Each leg makes new extreme
├── Take profit at channel line
└── Enter on trend line tests

Phase 4: CHANNEL BREAKOUT
├── Price breaks the channel trend line
├── Usually leads to trading range
├── May lead to measured move
└── Spike height projected from breakout = target
```

### Entry Rules

1. **After the spike:** Buy the first pullback (most aggressive, highest reward)
2. **In the channel:** Buy at trend line tests, sell at channel line
3. **On channel break:** If trend line breaks, expect measured move to spike start

### Measured Move Target

**Primary:** Height of the spike, projected from the end of the channel = target for the correction after channel break.

**Secondary:** Height of the channel, projected from the breakout point.

---

## 7. MICRO CHANNEL DETECTION

### Definition

A micro channel is an extremely strong trend where EVERY bar's low is above the prior bar's low (bull) or every bar's high is below the prior bar's high (bear). This means there is NO overlap in the direction against the trend — pure one-sided price action.

**Brooks Source:** *Trends* Ch.10 — "A micro channel is a series of bars where every bar has a higher low than the prior bar."

### Criteria

**Bull Micro Channel:** `low[i] > low[i-1]` for 4+ consecutive bars
**Bear Micro Channel:** `high[i] < high[i-1]` for 4+ consecutive bars

### Trading Rules

1. **Do NOT fade a micro channel** — it's the strongest possible trend signal
2. **Expect a breakout of the micro channel to lead to a pullback** — but the pullback is usually a buying opportunity (bull) or selling opportunity (bear)
3. **The first break of a micro channel** often leads to a test of the start of the channel
4. **Micro channels rarely last more than 10 bars** — they're too strong to sustain

### Probability Impact

- Active micro channel: **+10% to trend continuation probability**
- Just-broken micro channel: **-5% (pullback likely)** but trend usually resumes

---

## 8. MEASURED MOVE TARGETS

### Method 1: Leg1 = Leg2

The most fundamental measured move. The second leg of a trend equals the first leg in length.

```
                          Target
                           ↑
                      Leg 2 (= Leg 1)
                     ↗
    Pullback Low ──────
                     ↘
                Leg 1
               ↗
Start ──────
```

**Calculation:** Target = Pullback_Low + (Pullback_Low - Start)

**Reliability:** HIGH (60-70% of trends reach their Leg1=Leg2 target)

### Method 2: Spike Projection

After a spike-and-channel pattern, project the spike height from the channel breakout.

**Calculation:** Target = Channel_Break + Spike_Height

**Reliability:** MODERATE (50-60%)

### Method 3: Range Projection

The height of a trading range, projected from the breakout point.

**Calculation:** Target = Breakout_Level + Range_Height

**Reliability:** HIGH for strong breakouts (65-75%), LOW for weak breakouts

### Method 4: Gap Projection

Brooks teaches that gaps (between bars or between price levels) act as magnets and measuring tools.

**Types:**
- **Measuring gap:** Appears at the midpoint of a move. Total move = 2x the distance from start to gap.
- **Breakaway gap:** Appears at the start of a move. Target = gap height projected from gap.

**Reliability:** MODERATE (55-65%)

### Using Multiple Methods

When multiple methods give similar targets, confidence increases:
- 3 methods agree within 2%: **HIGH CONFIDENCE** target
- 2 methods agree: **MODERATE CONFIDENCE** target
- All methods diverge: **LOW CONFIDENCE** — use the most conservative target

---

## 9. EXPANDED PROBABILITY FRAMEWORK

### Base Probability

Al Brooks starts every trade at **50%** — the market can go either way. Every factor either adds or subtracts from this base.

### Adjustment Factors

| # | Factor | Impact | Condition | Brooks Source |
|---|--------|--------|-----------|---------------|
| 1 | Always-In aligned | +10-15% | Trade matches Always-In direction | *Trends* Ch.1 |
| 2 | Strong trend bars | +5-10% | Bars closing near extremes, large bodies | *Trends* Ch.2 |
| 3 | High volume on setup | +10% | Volume above 20-bar average | *Ranges* Ch.1 |
| 4 | Multi-timeframe alignment | +10-15% | Daily + weekly both agree on direction | *Trends* Ch.12 |
| 5 | Catalyst present | +5-10% | Earnings, upgrade, insider buy within 30 days | Contextual |
| 6 | Failed opposite setup | +10-15% | Bear setup failed → bullish; bull setup failed → bearish | *Reversals* Ch.11 |
| 7 | Second entry (High 2/Low 2) | +5-10% | Two-legged pullback = higher probability than first entry | *Ranges* Ch.17 |
| 8 | Breakout pullback | +5% | Successfully retested breakout level | *Ranges* Ch.5 |
| 9 | Micro channel active | +10% | Pure one-sided price action | *Trends* Ch.10 |
| 10 | Spike-and-channel in progress | +5% | Established trend structure | *Trends* Ch.21 |
| 11 | Dalio Ratio aligned | +5% | Buyers paying premium (LONG) or discount (SHORT) | Dalio integration |
| 12 | Dollar Flow aligned | +3% | Net accumulation (LONG) or distribution (SHORT) | Dalio integration |
| 13 | Sustainability high | +3% | Trend sustainability score ≥70 | Dalio integration |
| 14 | Counter-trend trade | -20-30% | Fighting Always-In direction | *Trends* Ch.1 |
| 15 | Low volume | -10-15% | Below-average volume = no institutional interest | *Ranges* Ch.1 |
| 16 | Choppy/overlapping bars | -10% | Indecision, range-bound price action | *Ranges* Ch.21 |
| 17 | Late in move (3+ pushes) | -10-15% | Exhaustion risk | *Trends* Ch.15 |
| 18 | Weak signal bar | -10% | Small body, long tails both sides, doji | *Trends* Ch.5 |
| 19 | RSI/MACD divergence | -10-15% | Momentum diverging from price | Contextual |
| 20 | Broad channel / range | -5-10% | Trend weakening, two-sided trading | *Trends* Ch.10 |
| 21 | Climax detected | -10-15% | Parabolic or consecutive climax bars | *Trends* Ch.15 |
| 22 | Dalio Ratio opposed | -5% | Buyers paying discount in a LONG setup | Dalio integration |
| 23 | Dollar Flow opposed | -3% | Distribution in a LONG setup | Dalio integration |
| 24 | Sustainability low | -3% | Trend sustainability score ≤30 | Dalio integration |

### Probability Cap

Per Brooks methodology, probability is **capped at 30-80%**. No setup is certain, and no setup is impossible if the market can still move.

### Narrative Generation Template

```
"Base: 50% (market starts at 50/50)
 + {factor1_name}: +{value}% ({reason})
 + {factor2_name}: +{value}% ({reason})
 - {factor3_name}: -{value}% ({reason})
 = Adjusted: {final}% → {conviction_tier}"
```

**Example:**
```
"Base: 50%
 + Always-In LONG aligned: +12%
 + High 2 pattern (second entry): +8%
 + High volume: +10%
 - Late in move (3 pushes): -10%
 = Adjusted: 70% → HIGH CONVICTION"
```

### Conviction Tiers

| Probability | Tier | Position Size | Action |
|------------|------|--------------|--------|
| ≥70% | HIGH CONVICTION | Full size (2% risk) | Execute immediately |
| 50-69% | MODERATE | 50-75% size | Execute with caveats |
| <50% | LOW | Do not trade | Wait for better setup |

---

## 10. DALIO-BROOKS INTEGRATION

### How Dalio Metrics Confirm/Deny Brooks Setups

The Dalio Economic Machine framework ("Price = Total Spending / Quantity Sold") provides a money-flow lens that either confirms or contradicts the price action.

### Confirmation Table

| Brooks Signal | Dalio Confirmation | Dalio Contradiction |
|--------------|-------------------|---------------------|
| Always-In LONG | Dalio Ratio >1.0 (premium), positive dollar flow, sustainability ≥60 | Dalio Ratio <1.0, negative dollar flow |
| Always-In SHORT | Dalio Ratio <1.0 (discount), negative dollar flow | Dalio Ratio >1.0, positive dollar flow |
| Breakout (LONG) | Dalio Ratio rising + institutional activity detected | Dalio Ratio falling, no institutional activity |
| Climax (LONG) | Dalio Ratio extremely high (>1.05) = unsustainable buying | N/A — extreme ratios confirm climax |
| Trading Range | Dalio Ratio near 1.0, low sustainability | N/A — neutrality confirms range |

### Integration Rules

1. **Dalio CONFIRMS Brooks:** Add +5% to +11% probability (ratio + flow + sustainability)
2. **Dalio CONTRADICTS Brooks:** Subtract -5% to -11% probability
3. **Dalio NEUTRAL:** No adjustment — price action alone drives the decision
4. **Institutional Activity Detected:** If Dalio institutional detection aligns with Brooks direction, the highest-conviction trades

### Report Integration

When writing reports, the Dalio section should follow the Brooks analysis:

```
**Money Flow Confirmation:** Dalio Ratio at {value} ({interpretation}) {confirms/contradicts}
the {Always-In direction}. Dollar flow is {positive/negative} ({net_flow}).
Sustainability score: {score}/100.

{If confirms}: "The money flow data supports the price action signal — real buyers
are accumulating at these levels."

{If contradicts}: "CAUTION: Money flow data contradicts the price action. While the
pattern suggests {direction}, actual spending data shows {opposite}. Reduce position
size or wait for confirmation."
```

---

## APPENDIX A: BROOKS RULES SUMMARY

### The 10 Commandments of Price Action Trading

1. **The market is Always-In long or Always-In short** — determine which and trade with it
2. **80% of breakouts fail** — never chase a breakout without confirmation
3. **Two-legged pullbacks are the highest-probability entries** (High 2 / Low 2)
4. **Three pushes = exhaustion** — after 3 legs, expect reversal or range
5. **Failed breakouts create the strongest signals** — trapped traders must exit
6. **Recognizing traps is more important than recognizing setups**
7. **The first pullback in a strong trend is the best entry**
8. **In trading ranges: buy low, sell high, scalp** — don't swing trade ranges
9. **Bar context matters more than bar shape** — a doji at support means something different than a doji in the middle of nowhere
10. **If you don't have ≥60% probability AND 1:1 R/R (or 50% with 2:1 R/R), don't trade**

### The Trader's Equation (Brooks, *Ranges* Ch.25)

```
Expected Value = (Win Rate × Average Win) - (Loss Rate × Average Loss)

For a trade to be valid:
- 60% win rate requires at least 1:1 Risk/Reward
- 50% win rate requires at least 2:1 Risk/Reward
- 40% win rate requires at least 3:1 Risk/Reward

If EV ≤ 0, DO NOT TRADE regardless of how good the setup looks.
```

---

## APPENDIX B: COUNTER-TREND TRADING RULES

Counter-trend trades (against Always-In direction) are LOW probability. Brooks provides strict rules:

1. **Only after a climax** — never counter-trend into a healthy move
2. **Need a strong reversal bar** — grade A+ signal (body >60% of range, closing near extreme, at key level)
3. **Scalp only** — take 50% of the prior leg, not the whole move
4. **Use 1/2 position size** — never full size counter-trend
5. **Have a clear stop** — below the climax low (long reversal) or above climax high (short reversal)
6. **Exit on first sign of trend resumption** — if trend resumes, you're wrong. Get out.

### 9 No-Go Situations for Counter-Trend Trades

1. Always-In direction is strong and clear
2. No climax or exhaustion signal
3. Signal bar is weak (doji, small body, long opposing tail)
4. No support/resistance at the reversal level
5. Trend has had fewer than 3 pushes
6. Volume is increasing WITH the trend (not exhausting)
7. Multiple timeframes agree on the trend direction
8. Recent failed reversals in the same area
9. Broad market is trending in the same direction

---

## APPENDIX C: QUICK REFERENCE — PATTERN-TO-STRATEGY MAP

| Pattern | Direction | Win Rate | Best Strategy | Position Size |
|---------|-----------|----------|---------------|---------------|
| high_1 | LONG | 55-65% | Debit spread | 50-75% |
| high_2 | LONG | 60-70% | Long calls / debit spread | 75-100% |
| high_3 | LONG | 45-55% | Credit spread (sell premium) | 25-50% |
| high_4 | LONG | 35-45% | AVOID or reversal trade | 0-25% |
| double_bottom | LONG | 60-70% | Long calls / debit spread | 75-100% |
| higher_low | LONG | 55-65% | Debit spread | 50-75% |
| breakout_pullback | LONG | 65-75% | Long calls / debit spread | 75-100% |
| wedge_reversal | LONG | 60-70% | Debit spread | 75-100% |
| expanding_triangle | LONG | 50-60% | Straddle / small debit | 50% |
| failed_breakdown | LONG | 65-75% | Long calls | 75-100% |
| ema_bounce | LONG | 55-65% | Debit spread | 50-75% |
| tight_tr_breakout | LONG | 55-65% | Debit spread / straddle | 50-75% |
| low_1 | SHORT | 55-65% | Debit put spread | 50-75% |
| low_2 | SHORT | 60-70% | Long puts / debit put spread | 75-100% |
| low_3 | SHORT | 45-55% | Credit spread (sell premium) | 25-50% |
| low_4 | SHORT | 35-45% | AVOID or reversal trade | 0-25% |
| double_top | SHORT | 60-70% | Long puts / debit put spread | 75-100% |
| lower_high | SHORT | 55-65% | Debit put spread | 50-75% |
| breakdown_pullback | SHORT | 65-75% | Long puts | 75-100% |
| wedge_top | SHORT | 60-70% | Debit put spread | 75-100% |
| expanding_triangle_top | SHORT | 50-60% | Straddle / small debit | 50% |
| failed_breakout | SHORT | 65-75% | Long puts | 75-100% |
| ema_rejection | SHORT | 55-65% | Debit put spread | 50-75% |
| climactic_exhaustion | SHORT | 55-65% | Long puts / bear spread | 75-100% |

---

*Last Updated: March 2026 | Synthesized from Al Brooks' 3-book series (Trends, Trading Ranges, Reversals)*
*Aligned with AlBrooksAnalyzer patterns in scanner_analyzer.py*

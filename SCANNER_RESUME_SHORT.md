# SHORT SCANNER - RESUME DOCUMENT

**Created:** 2026-01-11 21:10 EST
**Status:** Paused at Batch 4/8 - Urgent bug fix required

---

## CURRENT PROGRESS

### Batches Completed: 4/8

| Batch | Scanned | 4/4 Passed | 3/4 Passed | Time |
|-------|---------|------------|------------|------|
| 1 | 20 | 1 | 4 | 117s |
| 2 | 20 | 5 | 3 | 222s |
| 3 | 20 | 1 | 6 | 178s |
| 4 | 20 | 2 | 6 | 271s |
| **Total** | **80** | **9** | **19** | **~13min** |

---

## 4/4 GATE PASSERS FOUND (9 Total)

| Rank | Symbol | Signal | Conf | Price | Stop | T1 | T2 | Key Catalyst |
|------|--------|--------|------|-------|------|----|----|--------------|
| 1 | **DELL** | STRONG_SELL | 80% | $120.57 | $125.39 | $113.33 | $108.51 | 6 Bearish UOA, Dalio 0.93 |
| 2 | **FICO** | STRONG_SELL | 80% | $1,649 | $1,715 | $1,551 | $1,485 | 3 Bearish UOA, Insider Selling |
| 3 | **CHDN** | SELL | 75% | $107.05 | $111.33 | $100.63 | $96.34 | Fresh SHORT, Dalio 0.95 |
| 4 | **BXSL** | SELL | 75% | $26.24 | $27.28 | $24.66 | $23.61 | Dalio 0.97, F-Score 2 |
| 5 | **CNQ** | SELL | 75% | $32.08 | $33.36 | $30.16 | $28.87 | Bearish News, Distress Z 1.50 |
| 6 | **OCFC** | SELL | 75% | $17.87 | $18.58 | $16.80 | $16.08 | 6/6 Freshness, Dalio 0.92 |
| 7 | **CAG** | SELL | 70% | $16.98 | $17.65 | $15.96 | $15.28 | Bearish UOA, Dalio 0.97 |
| 8 | **QTWO** | SELL | 70% | $70.30 | $73.11 | $66.08 | $63.27 | Dalio 0.96, F-Score 8 |
| 9 | **INTA** | SELL | 65% | $43.53 | $45.27 | $40.92 | $39.18 | Pre-Earnings 22d |

---

## 3/4 GATE PASSERS (Watchlist - 19 Total)

| Symbol | Failed Gate | Key Notes |
|--------|-------------|-----------|
| META | Quality | **10 Bearish UOA**, Pre-Earnings 16d |
| DT | Quality | Pre-Earnings 20d, Bearish UOA |
| MKTX | Quality | Strong Dalio 0.95, 9 Bearish News |
| ADMA | Quality | Strong Dalio 0.94, Bearish UOA |
| NBIX | Quality | Strong Dalio 0.96 |
| TVTX | Catalyst | Dalio 0.95, Distress Z 1.16 |
| ARWR | Brooks | 3 Bearish UOA, Pre-Earnings 28d |
| IRON | Catalyst | Strong Dalio 0.95, F-Score 2 |
| ZM | Quality | Insider Selling |
| MGNI | Catalyst | Fresh SHORT, F-Score 8 |
| LBTYK | Catalyst | Dalio BEARISH, Distress Z 0.66 |
| PFGC | Brooks | Brooks conflicting |
| CDW | Brooks | Brooks conflicting |
| MTN | Brooks | Brooks conflicting |
| PLUS | Freshness | Freshness issue |
| TBBB | Brooks | Brooks conflicting |
| ALKT | Catalyst | Weak catalyst |
| RIVN | Brooks | Brooks conflicting |
| ORKA | Freshness | Freshness issue |

---

## REMAINING CANDIDATES TO SCAN (80 candidates)

### Batch 5 (indices 80-99)
```
["ORI", "COHR", "PSK", "CJ", "STRF", "DSGX", "FNMAS", "ARQT", "UTHR", "COLL", "NUVB", "HROW", "ESTA", "EYPT", "CNOB", "STLD", "LNC", "CCO", "MDB", "IOVA"]
```

### Batch 6 (indices 100-119)
```
["NUE", "DVN", "GIII", "DCOM", "RLAY", "DOO", "ARLO", "HAFN", "WRB", "PD", "PXED", "PODD", "SNOW", "BULL", "ARDT", "IPGP", "BEPC", "ALNY", "CLVT", "CVLT"]
```

### Batch 7 (indices 120-139)
```
["PSTG", "ALH", "PARR", "TAC", "KTB", "BB", "TA", "AVAH", "ETN", "EXPI", "CRWD", "WGS", "FIZZ", "UBER", "NSIT", "SPB", "TEM", "DORM", "PHR", "WLY"]
```

### Batch 8 (indices 140-159)
```
["CXT", "AAP", "AGIO", "PANW", "TSCO", "BSY", "LIF", "NPI"]
```

---

## COMMAND TO RESUME SCANNING

Run these commands in order after fixing the bug:

### Batch 5:
```
scan_short_candidates(candidates=["ORI", "COHR", "PSK", "CJ", "STRF", "DSGX", "FNMAS", "ARQT", "UTHR", "COLL", "NUVB", "HROW", "ESTA", "EYPT", "CNOB", "STLD", "LNC", "CCO", "MDB", "IOVA"], batch_size=20, top_n=10)
```

### Batch 6:
```
scan_short_candidates(candidates=["NUE", "DVN", "GIII", "DCOM", "RLAY", "DOO", "ARLO", "HAFN", "WRB", "PD", "PXED", "PODD", "SNOW", "BULL", "ARDT", "IPGP", "BEPC", "ALNY", "CLVT", "CVLT"], batch_size=20, top_n=10)
```

### Batch 7:
```
scan_short_candidates(candidates=["PSTG", "ALH", "PARR", "TAC", "KTB", "BB", "TA", "AVAH", "ETN", "EXPI", "CRWD", "WGS", "FIZZ", "UBER", "NSIT", "SPB", "TEM", "DORM", "PHR", "WLY"], batch_size=20, top_n=10)
```

### Batch 8:
```
scan_short_candidates(candidates=["CXT", "AAP", "AGIO", "PANW", "TSCO", "BSY", "LIF", "NPI"], batch_size=20, top_n=10)
```

---

## QUICK RESUME PROMPT

Copy this to continue the scan:

```
Resume SHORT scanner from Batch 5. Read SCANNER_RESUME_SHORT.md for context.
Remaining batches: 5, 6, 7, 8 (80 candidates total).
Current totals: 9 @ 4/4 gates, 19 @ 3/4 gates.
Pause after each batch and wait for my signal.
```

---

## LONG SCAN SUMMARY (Completed Earlier)

For reference, the LONG scan completed with:
- **14 unique 4/4 passers** (GE, BKNG, STOK, DLO, IMO, DECK, WLDN, INCY, LOPE, HROW, WAT, CSL, ACN, ESE)
- **46 @ 3/4 passers**
- Top picks: GE (85%), DECK (Quality A), WAT (Quality A), ACN (Quality A), BKNG (7 UOA)

---

**Last Updated:** 2026-01-11 21:10 EST

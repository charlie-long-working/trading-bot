# DCA Futures Bot Analysis — BTCUSDT Perpetual

Period: 2017-08-17 → 2026-03-14 | Data: BTC/USDT Spot (proxy for futures)

## 1. Bot từ Screenshot (Tham số gốc)

| Parameter | Value |
|-----------|-------|
| Pair | BTCUSDT Perpetual |
| Direction | Long |
| Leverage | 10x |
| Price step | 0.75% |
| Take profit | 1.5% |
| Initial order margin | $28 |
| Safety order margin | $11 |
| Max safety orders | 13 |
| Volume scale | 1.00x |
| Step scale | 1.10x |
| **Total margin needed** | **$171** |
| **Max price deviation** | **18.39%** |
| Stop loss | Not set |

### Safety Order Grid

| SO# | Trigger (drop from entry) | Cumulative drop | Margin |
|-----|--------------------------|-----------------|--------|
| SO1 | 0.7500% | 0.75% | $11 |
| SO2 | 0.8250% | 1.57% | $11 |
| SO3 | 0.9075% | 2.48% | $11 |
| SO4 | 0.9983% | 3.48% | $11 |
| SO5 | 1.0981% | 4.58% | $11 |
| SO6 | 1.2079% | 5.79% | $11 |
| SO7 | 1.3287% | 7.12% | $11 |
| SO8 | 1.4615% | 8.58% | $11 |
| SO9 | 1.6077% | 10.18% | $11 |
| SO10 | 1.7685% | 11.95% | $11 |
| SO11 | 1.9453% | 13.90% | $11 |
| SO12 | 2.1398% | 16.04% | $11 |
| SO13 | 2.3538% | 18.39% | $11 |

## 2. Kết quả Simulation (bot screenshot, vốn $300)

| Timeframe | Final Balance | Return | Cycles | TP | Liquidation | Win Rate | Max DD | Fees | Funding |
|-----------|--------------|--------|--------|----|-------------|----------|--------|------|---------|
| 15m | $9.99 | -96.7% | 60 | 56 | **4** | 93.3% | 97.3% | $16.42 | $5.19 |
| 1h | $4,249.70 | +1316.6% | 3113 | 3000 | **112** | 96.4% | 63.8% | $989.64 | $701.59 |
| 4h | $8,314.79 | +2671.6% | 2526 | 2462 | **63** | 97.5% | 24.3% | $809.59 | $571.84 |

### Thời điểm Liquidation (cháy tài khoản)

**15m:**
  - 2017-08-22 00:45: Price $3,790 (entry $4,444, drop 14.7%), SO filled: 11, Margin lost: $149, Balance after: $162
  - 2017-09-04 07:15: Price $4,080 (entry $4,928, drop 17.2%), SO filled: 13, Margin lost: $171, Balance after: $193
  - 2017-09-05 01:30: Price $3,750 (entry $4,400, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $58
  - 2017-09-08 14:15: Price $4,029 (entry $4,738, drop 15.0%), SO filled: 12, Margin lost: $160, Balance after: $10

**1h:**
  - 2017-08-22 00:00: Price $3,790 (entry $4,444, drop 14.7%), SO filled: 11, Margin lost: $149, Balance after: $153
  - 2017-09-04 15:00: Price $4,015 (entry $4,691, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $231
  - 2017-09-14 10:00: Price $3,620 (entry $4,361, drop 17.0%), SO filled: 13, Margin lost: $171, Balance after: $302
  - 2017-09-15 11:00: Price $2,817 (entry $3,370, drop 16.4%), SO filled: 12, Margin lost: $160, Balance after: $185
  - 2017-09-22 15:00: Price $3,506 (entry $4,090, drop 14.3%), SO filled: 11, Margin lost: $149, Balance after: $172
  - 2017-11-11 13:00: Price $6,125 (entry $7,213, drop 15.1%), SO filled: 12, Margin lost: $160, Balance after: $636
  - 2017-11-12 06:00: Price $5,325 (entry $6,399, drop 16.8%), SO filled: 12, Margin lost: $160, Balance after: $486
  - 2017-12-09 17:00: Price $12,535 (entry $15,340, drop 18.3%), SO filled: 13, Margin lost: $171, Balance after: $1270
  - 2017-12-13 03:00: Price $14,667 (entry $17,205, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $1250
  - 2017-12-21 15:00: Price $14,022 (entry $17,039, drop 17.7%), SO filled: 13, Margin lost: $171, Balance after: $1416
  - 2017-12-28 02:00: Price $13,418 (entry $16,351, drop 17.9%), SO filled: 13, Margin lost: $171, Balance after: $1645
  - 2018-01-08 09:00: Price $14,619 (entry $17,070, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $1897
  - 2018-01-10 08:00: Price $13,131 (entry $15,349, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $1818
  - 2018-01-16 08:00: Price $11,041 (entry $14,085, drop 21.6%), SO filled: 13, Margin lost: $171, Balance after: $1847
  - 2018-01-16 21:00: Price $9,880 (entry $11,964, drop 17.4%), SO filled: 13, Margin lost: $171, Balance after: $1699
  - 2018-01-30 15:00: Price $10,206 (entry $11,969, drop 14.7%), SO filled: 11, Margin lost: $149, Balance after: $2181
  - 2018-02-01 20:00: Price $8,751 (entry $10,285, drop 14.9%), SO filled: 11, Margin lost: $149, Balance after: $2076
  - 2018-02-04 20:00: Price $7,930 (entry $9,270, drop 14.5%), SO filled: 11, Margin lost: $149, Balance after: $2062
  - 2018-02-11 08:00: Price $7,727 (entry $9,035, drop 14.5%), SO filled: 11, Margin lost: $149, Balance after: $2203
  - 2018-03-07 16:00: Price $9,810 (entry $11,669, drop 15.9%), SO filled: 12, Margin lost: $160, Balance after: $2489
  - 2018-03-09 04:00: Price $8,550 (entry $9,993, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $2373
  - 2018-03-14 21:00: Price $7,900 (entry $9,253, drop 14.6%), SO filled: 11, Margin lost: $149, Balance after: $2396
  - 2018-03-18 14:00: Price $7,322 (entry $8,536, drop 14.2%), SO filled: 11, Margin lost: $149, Balance after: $2334
  - 2018-03-29 04:00: Price $7,595 (entry $8,950, drop 15.1%), SO filled: 12, Margin lost: $160, Balance after: $2288
  - 2018-04-01 14:00: Price $6,430 (entry $7,565, drop 15.0%), SO filled: 12, Margin lost: $160, Balance after: $2126
  - 2018-05-11 12:00: Price $8,462 (entry $9,904, drop 14.6%), SO filled: 11, Margin lost: $149, Balance after: $2274
  - 2018-05-24 09:00: Price $7,267 (entry $8,530, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $2191
  - 2018-06-10 18:00: Price $6,623 (entry $7,728, drop 14.3%), SO filled: 11, Margin lost: $149, Balance after: $2115
  - 2018-06-24 06:00: Price $5,778 (entry $6,751, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $2016
  - 2018-08-04 12:00: Price $7,218 (entry $8,419, drop 14.3%), SO filled: 11, Margin lost: $149, Balance after: $2050
  - 2018-08-08 16:00: Price $6,188 (entry $7,260, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $1899
  - 2018-11-14 16:00: Price $5,830 (entry $6,982, drop 16.5%), SO filled: 12, Margin lost: $160, Balance after: $1996
  - 2018-11-19 16:00: Price $5,068 (entry $5,980, drop 15.2%), SO filled: 12, Margin lost: $160, Balance after: $1834
  - 2018-11-20 08:00: Price $4,405 (entry $5,135, drop 14.2%), SO filled: 11, Margin lost: $149, Balance after: $1684
  - 2018-11-23 01:00: Price $4,240 (entry $4,952, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $1546
  - 2018-11-24 22:00: Price $3,825 (entry $4,493, drop 14.9%), SO filled: 11, Margin lost: $149, Balance after: $1424
  - 2018-12-06 14:00: Price $3,631 (entry $4,276, drop 15.1%), SO filled: 12, Margin lost: $160, Balance after: $1405
  - 2019-05-17 03:00: Price $7,000 (entry $8,286, drop 15.5%), SO filled: 12, Margin lost: $160, Balance after: $2259
  - 2019-06-06 18:00: Price $7,445 (entry $8,717, drop 14.6%), SO filled: 11, Margin lost: $149, Balance after: $2317
  - 2019-07-01 14:00: Price $10,256 (entry $12,099, drop 15.2%), SO filled: 12, Margin lost: $160, Balance after: $2662
  - 2019-07-14 10:00: Price $10,590 (entry $12,368, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $2698
  - 2019-07-16 23:00: Price $9,350 (entry $10,910, drop 14.3%), SO filled: 11, Margin lost: $149, Balance after: $2586
  - 2019-07-28 22:00: Price $9,165 (entry $10,777, drop 14.9%), SO filled: 12, Margin lost: $160, Balance after: $2549
  - 2019-08-14 17:00: Price $10,100 (entry $11,970, drop 15.6%), SO filled: 12, Margin lost: $160, Balance after: $2530
  - 2019-08-29 07:00: Price $9,320 (entry $10,891, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $2424
  - 2019-09-24 18:00: Price $8,600 (entry $10,532, drop 18.3%), SO filled: 13, Margin lost: $171, Balance after: $2333
  - 2019-11-17 08:00: Price $8,351 (entry $9,736, drop 14.2%), SO filled: 11, Margin lost: $149, Balance after: $2322
  - 2019-11-22 10:00: Price $6,940 (entry $8,536, drop 18.7%), SO filled: 13, Margin lost: $171, Balance after: $2149
  - 2020-02-28 12:00: Price $8,445 (entry $9,868, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $2500
  - 2020-03-09 05:00: Price $7,675 (entry $9,086, drop 15.5%), SO filled: 12, Margin lost: $160, Balance after: $2365
  - 2020-03-12 10:00: Price $5,550 (entry $8,065, drop 31.2%), SO filled: 13, Margin lost: $171, Balance after: $2207
  - 2020-03-16 10:00: Price $4,444 (entry $5,273, drop 15.7%), SO filled: 12, Margin lost: $160, Balance after: $2287
  - 2020-09-03 15:00: Price $10,460 (entry $12,363, drop 15.4%), SO filled: 12, Margin lost: $160, Balance after: $3326
  - 2020-11-26 08:00: Price $16,334 (entry $19,282, drop 15.3%), SO filled: 12, Margin lost: $160, Balance after: $3650
  - 2021-01-04 10:00: Price $28,130 (entry $33,558, drop 16.2%), SO filled: 12, Margin lost: $160, Balance after: $4018
  - 2021-01-10 20:00: Price $35,111 (entry $40,945, drop 14.2%), SO filled: 11, Margin lost: $149, Balance after: $4071
  - 2021-01-17 10:00: Price $33,850 (entry $39,578, drop 14.5%), SO filled: 11, Margin lost: $149, Balance after: $4171
  - 2021-01-21 12:00: Price $31,300 (entry $37,162, drop 15.8%), SO filled: 12, Margin lost: $160, Balance after: $4065
  - 2021-01-27 14:00: Price $29,242 (entry $34,544, drop 15.3%), SO filled: 12, Margin lost: $160, Balance after: $3990
  - 2021-02-22 14:00: Price $47,622 (entry $58,073, drop 18.0%), SO filled: 13, Margin lost: $171, Balance after: $4279
  - 2021-02-23 09:00: Price $45,000 (entry $54,085, drop 16.8%), SO filled: 12, Margin lost: $160, Balance after: $4131
  - 2021-02-28 06:00: Price $43,739 (entry $51,348, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $4084
  - 2021-03-25 12:00: Price $50,439 (entry $59,365, drop 15.0%), SO filled: 12, Margin lost: $160, Balance after: $4161
  - 2021-04-18 03:00: Price $50,931 (entry $64,577, drop 21.1%), SO filled: 13, Margin lost: $171, Balance after: $4127
  - 2021-04-23 05:00: Price $48,443 (entry $56,572, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $4027
  - 2021-05-12 23:00: Price $48,600 (entry $57,228, drop 15.1%), SO filled: 12, Margin lost: $160, Balance after: $4061
  - 2021-05-17 03:00: Price $42,777 (entry $50,809, drop 15.8%), SO filled: 12, Margin lost: $160, Balance after: $3960
  - 2021-05-19 04:00: Price $38,605 (entry $45,173, drop 14.5%), SO filled: 11, Margin lost: $149, Balance after: $3862
  - 2021-05-23 16:00: Price $31,111 (entry $37,908, drop 17.9%), SO filled: 13, Margin lost: $171, Balance after: $3952
  - 2021-05-29 13:00: Price $34,126 (entry $39,864, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $3913
  - 2021-06-08 02:00: Price $32,351 (entry $38,682, drop 16.4%), SO filled: 12, Margin lost: $160, Balance after: $3844
  - 2021-06-20 10:00: Price $33,724 (entry $40,127, drop 16.0%), SO filled: 12, Margin lost: $160, Balance after: $3832
  - 2021-06-22 12:00: Price $29,294 (entry $35,543, drop 17.6%), SO filled: 13, Margin lost: $171, Balance after: $3675
  - 2021-07-19 14:00: Price $30,407 (entry $35,601, drop 14.6%), SO filled: 11, Margin lost: $149, Balance after: $3651
  - 2021-09-07 15:00: Price $42,843 (entry $52,664, drop 18.6%), SO filled: 13, Margin lost: $171, Balance after: $3915
  - 2021-09-21 00:00: Price $40,200 (entry $48,591, drop 17.3%), SO filled: 13, Margin lost: $171, Balance after: $3811
  - 2021-11-16 10:00: Price $58,574 (entry $68,349, drop 14.3%), SO filled: 11, Margin lost: $149, Balance after: $4033
  - 2021-12-04 04:00: Price $49,188 (entry $58,614, drop 16.1%), SO filled: 12, Margin lost: $160, Balance after: $3972
  - 2022-01-05 20:00: Price $43,723 (entry $51,451, drop 15.0%), SO filled: 12, Margin lost: $160, Balance after: $3949
  - 2022-01-21 21:00: Price $36,158 (entry $43,275, drop 16.4%), SO filled: 12, Margin lost: $160, Balance after: $3836
  - 2022-02-21 11:00: Price $37,348 (entry $44,196, drop 15.5%), SO filled: 12, Margin lost: $160, Balance after: $3911
  - 2022-03-07 02:00: Price $37,584 (entry $44,243, drop 15.1%), SO filled: 12, Margin lost: $160, Balance after: $3855
  - 2022-04-11 19:00: Price $39,770 (entry $46,581, drop 14.6%), SO filled: 11, Margin lost: $149, Balance after: $3877
  - 2022-05-05 18:00: Price $36,001 (entry $42,440, drop 15.2%), SO filled: 12, Margin lost: $160, Balance after: $3756
  - 2022-05-09 17:00: Price $31,000 (entry $36,316, drop 14.6%), SO filled: 11, Margin lost: $149, Balance after: $3605
  - 2022-06-12 23:00: Price $26,560 (entry $31,125, drop 14.7%), SO filled: 11, Margin lost: $149, Balance after: $3773
  - 2022-06-14 00:00: Price $21,757 (entry $25,358, drop 14.2%), SO filled: 11, Margin lost: $149, Balance after: $3645
  - 2022-06-18 06:00: Price $19,120 (entry $22,454, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $3558
  - 2022-07-26 15:00: Price $20,706 (entry $24,173, drop 14.3%), SO filled: 11, Margin lost: $149, Balance after: $3766
  - 2022-08-19 11:00: Price $21,262 (entry $24,867, drop 14.5%), SO filled: 11, Margin lost: $149, Balance after: $3735
  - 2022-09-19 06:00: Price $18,233 (entry $21,398, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $3685
  - 2022-11-08 19:00: Price $17,167 (entry $21,365, drop 19.6%), SO filled: 13, Margin lost: $171, Balance after: $3745
  - 2022-11-09 21:00: Price $15,671 (entry $18,460, drop 15.1%), SO filled: 12, Margin lost: $160, Balance after: $3588
  - 2023-03-09 18:00: Price $20,967 (entry $24,800, drop 15.5%), SO filled: 12, Margin lost: $160, Balance after: $3740
  - 2023-06-14 20:00: Price $24,821 (entry $29,460, drop 15.8%), SO filled: 12, Margin lost: $160, Balance after: $3866
  - 2023-08-17 21:00: Price $25,166 (entry $31,606, drop 20.4%), SO filled: 13, Margin lost: $171, Balance after: $3794
  - 2024-01-22 18:00: Price $40,119 (entry $46,784, drop 14.2%), SO filled: 11, Margin lost: $149, Balance after: $4112
  - 2024-03-19 09:00: Price $62,983 (entry $73,434, drop 14.2%), SO filled: 11, Margin lost: $149, Balance after: $4317
  - 2024-04-13 20:00: Price $60,661 (entry $71,968, drop 15.7%), SO filled: 12, Margin lost: $160, Balance after: $4252
  - 2024-05-01 08:00: Price $56,553 (entry $66,331, drop 14.7%), SO filled: 11, Margin lost: $149, Balance after: $4168
  - 2024-06-24 09:00: Price $60,567 (entry $71,313, drop 15.1%), SO filled: 12, Margin lost: $160, Balance after: $4132
  - 2024-07-05 04:00: Price $53,486 (entry $63,436, drop 15.7%), SO filled: 12, Margin lost: $160, Balance after: $4004
  - 2024-08-04 14:00: Price $59,317 (entry $69,348, drop 14.5%), SO filled: 11, Margin lost: $149, Balance after: $4025
  - 2024-08-05 06:00: Price $49,000 (entry $59,158, drop 17.2%), SO filled: 13, Margin lost: $171, Balance after: $3862
  - 2024-09-06 14:00: Price $54,424 (entry $64,111, drop 15.1%), SO filled: 12, Margin lost: $160, Balance after: $3861
  - 2025-02-25 15:00: Price $86,051 (entry $101,083, drop 14.9%), SO filled: 11, Margin lost: $149, Balance after: $4397
  - 2025-10-10 21:00: Price $102,000 (entry $125,128, drop 18.5%), SO filled: 13, Margin lost: $171, Balance after: $4688
  - 2025-11-13 18:00: Price $98,147 (entry $115,015, drop 14.7%), SO filled: 11, Margin lost: $149, Balance after: $4580
  - 2025-11-21 07:00: Price $82,000 (entry $98,974, drop 17.1%), SO filled: 13, Margin lost: $171, Balance after: $4411
  - 2026-01-30 01:00: Price $81,118 (entry $96,765, drop 16.2%), SO filled: 12, Margin lost: $160, Balance after: $4381
  - 2026-02-04 17:00: Price $72,169 (entry $84,243, drop 14.3%), SO filled: 11, Margin lost: $149, Balance after: $4239
  - 2026-02-05 20:00: Price $62,345 (entry $73,426, drop 15.1%), SO filled: 12, Margin lost: $160, Balance after: $4078

**4h:**
  - 2017-09-14 08:00: Price $3,418 (entry $4,361, drop 21.6%), SO filled: 13, Margin lost: $171, Balance after: $538
  - 2018-01-08 08:00: Price $14,551 (entry $17,070, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $2375
  - 2018-01-30 12:00: Price $10,206 (entry $12,013, drop 15.0%), SO filled: 12, Margin lost: $160, Balance after: $2733
  - 2018-03-07 16:00: Price $9,389 (entry $11,568, drop 18.8%), SO filled: 13, Margin lost: $171, Balance after: $3164
  - 2018-03-14 20:00: Price $7,900 (entry $9,250, drop 14.6%), SO filled: 11, Margin lost: $149, Balance after: $3161
  - 2018-03-18 12:00: Price $7,322 (entry $8,536, drop 14.2%), SO filled: 11, Margin lost: $149, Balance after: $3044
  - 2018-03-29 12:00: Price $7,334 (entry $8,612, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $2991
  - 2018-05-11 12:00: Price $8,462 (entry $9,930, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $3181
  - 2018-05-24 08:00: Price $7,267 (entry $8,527, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $3093
  - 2018-06-10 16:00: Price $6,623 (entry $7,722, drop 14.2%), SO filled: 11, Margin lost: $149, Balance after: $3037
  - 2018-06-24 04:00: Price $5,778 (entry $6,762, drop 14.6%), SO filled: 11, Margin lost: $149, Balance after: $2936
  - 2018-08-04 12:00: Price $6,951 (entry $8,374, drop 17.0%), SO filled: 13, Margin lost: $171, Balance after: $2948
  - 2018-08-10 20:00: Price $6,026 (entry $7,088, drop 15.0%), SO filled: 12, Margin lost: $160, Balance after: $2806
  - 2018-11-14 16:00: Price $5,700 (entry $6,982, drop 18.4%), SO filled: 13, Margin lost: $171, Balance after: $2841
  - 2018-11-19 20:00: Price $4,855 (entry $5,753, drop 15.6%), SO filled: 12, Margin lost: $160, Balance after: $2707
  - 2018-11-24 20:00: Price $3,825 (entry $4,630, drop 17.4%), SO filled: 13, Margin lost: $171, Balance after: $2592
  - 2018-12-07 00:00: Price $3,341 (entry $3,960, drop 15.6%), SO filled: 12, Margin lost: $160, Balance after: $2605
  - 2019-07-14 08:00: Price $10,505 (entry $12,368, drop 15.1%), SO filled: 12, Margin lost: $160, Balance after: $4010
  - 2019-07-28 20:00: Price $9,165 (entry $10,740, drop 14.7%), SO filled: 11, Margin lost: $149, Balance after: $3984
  - 2019-08-16 04:00: Price $9,750 (entry $11,446, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $3948
  - 2019-08-29 04:00: Price $9,320 (entry $10,916, drop 14.6%), SO filled: 11, Margin lost: $149, Balance after: $3822
  - 2019-09-24 16:00: Price $7,800 (entry $10,214, drop 23.6%), SO filled: 13, Margin lost: $171, Balance after: $3759
  - 2019-11-18 16:00: Price $8,060 (entry $9,404, drop 14.3%), SO filled: 11, Margin lost: $149, Balance after: $3843
  - 2019-11-22 08:00: Price $6,940 (entry $8,187, drop 15.2%), SO filled: 12, Margin lost: $160, Balance after: $3681
  - 2020-03-08 12:00: Price $8,321 (entry $9,753, drop 14.7%), SO filled: 11, Margin lost: $149, Balance after: $3989
  - 2020-03-12 08:00: Price $5,550 (entry $8,280, drop 33.0%), SO filled: 13, Margin lost: $171, Balance after: $3817
  - 2020-09-03 20:00: Price $9,961 (entry $11,957, drop 16.7%), SO filled: 12, Margin lost: $160, Balance after: $4690
  - 2021-03-25 12:00: Price $50,428 (entry $59,273, drop 14.9%), SO filled: 12, Margin lost: $160, Balance after: $6560
  - 2021-04-18 00:00: Price $50,931 (entry $64,511, drop 21.1%), SO filled: 13, Margin lost: $171, Balance after: $6510
  - 2021-04-23 04:00: Price $47,700 (entry $56,425, drop 15.5%), SO filled: 12, Margin lost: $160, Balance after: $6394
  - 2021-05-12 20:00: Price $48,600 (entry $57,101, drop 14.9%), SO filled: 11, Margin lost: $149, Balance after: $6430
  - 2021-05-17 16:00: Price $42,001 (entry $49,015, drop 14.3%), SO filled: 11, Margin lost: $149, Balance after: $6326
  - 2021-06-20 08:00: Price $33,724 (entry $40,144, drop 16.0%), SO filled: 12, Margin lost: $160, Balance after: $6672
  - 2021-06-22 12:00: Price $28,805 (entry $35,600, drop 19.1%), SO filled: 13, Margin lost: $171, Balance after: $6504
  - 2021-07-19 12:00: Price $30,407 (entry $35,512, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $6458
  - 2021-09-21 00:00: Price $40,200 (entry $48,367, drop 16.9%), SO filled: 12, Margin lost: $160, Balance after: $6733
  - 2021-11-19 00:00: Price $55,600 (entry $65,713, drop 15.4%), SO filled: 12, Margin lost: $160, Balance after: $6952
  - 2021-12-04 04:00: Price $42,000 (entry $57,428, drop 26.9%), SO filled: 13, Margin lost: $171, Balance after: $6846
  - 2022-01-05 20:00: Price $42,500 (entry $51,205, drop 17.0%), SO filled: 13, Margin lost: $171, Balance after: $6834
  - 2022-02-21 08:00: Price $37,348 (entry $44,199, drop 15.5%), SO filled: 12, Margin lost: $160, Balance after: $7011
  - 2022-04-11 20:00: Price $39,200 (entry $46,032, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $7141
  - 2022-05-05 16:00: Price $35,572 (entry $42,440, drop 16.2%), SO filled: 12, Margin lost: $160, Balance after: $7012
  - 2022-05-09 16:00: Price $30,334 (entry $36,553, drop 17.0%), SO filled: 13, Margin lost: $171, Balance after: $6840
  - 2022-06-13 00:00: Price $24,900 (entry $30,302, drop 17.8%), SO filled: 13, Margin lost: $171, Balance after: $6963
  - 2022-06-18 16:00: Price $18,031 (entry $21,101, drop 14.6%), SO filled: 11, Margin lost: $149, Balance after: $6903
  - 2022-08-26 20:00: Price $20,108 (entry $23,747, drop 15.3%), SO filled: 12, Margin lost: $160, Balance after: $7179
  - 2022-11-09 20:00: Price $15,588 (entry $18,547, drop 16.0%), SO filled: 12, Margin lost: $160, Balance after: $7357
  - 2023-03-09 16:00: Price $20,766 (entry $24,943, drop 16.7%), SO filled: 12, Margin lost: $160, Balance after: $7538
  - 2023-06-06 12:00: Price $25,351 (entry $29,562, drop 14.2%), SO filled: 11, Margin lost: $149, Balance after: $7632
  - 2023-08-17 20:00: Price $25,166 (entry $31,606, drop 20.4%), SO filled: 13, Margin lost: $171, Balance after: $7540
  - 2024-01-22 16:00: Price $39,432 (entry $46,784, drop 15.7%), SO filled: 12, Margin lost: $160, Balance after: $7820
  - 2024-04-13 20:00: Price $60,661 (entry $72,404, drop 16.2%), SO filled: 12, Margin lost: $160, Balance after: $8105
  - 2024-05-01 08:00: Price $56,553 (entry $66,435, drop 14.9%), SO filled: 11, Margin lost: $149, Balance after: $8045
  - 2024-07-04 08:00: Price $56,952 (entry $66,504, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $8017
  - 2024-08-04 16:00: Price $57,123 (entry $67,303, drop 15.1%), SO filled: 12, Margin lost: $160, Balance after: $8016
  - 2024-09-06 12:00: Price $53,808 (entry $64,115, drop 16.1%), SO filled: 12, Margin lost: $160, Balance after: $8024
  - 2025-02-25 08:00: Price $86,888 (entry $101,329, drop 14.2%), SO filled: 11, Margin lost: $149, Balance after: $8455
  - 2025-10-10 20:00: Price $102,000 (entry $124,659, drop 18.2%), SO filled: 13, Margin lost: $171, Balance after: $8778
  - 2025-11-13 16:00: Price $98,147 (entry $114,959, drop 14.6%), SO filled: 11, Margin lost: $149, Balance after: $8664
  - 2025-11-21 00:00: Price $85,360 (entry $99,692, drop 14.4%), SO filled: 11, Margin lost: $149, Balance after: $8512
  - 2026-01-29 16:00: Price $83,383 (entry $97,267, drop 14.3%), SO filled: 11, Margin lost: $149, Balance after: $8473
  - 2026-02-04 16:00: Price $72,169 (entry $84,650, drop 14.7%), SO filled: 11, Margin lost: $149, Balance after: $8321
  - 2026-02-05 20:00: Price $62,345 (entry $73,166, drop 14.8%), SO filled: 11, Margin lost: $149, Balance after: $8172

### Phân tích rủi ro

- Bot cần tổng margin: **$171** (với vốn $300, dùng 57%)
- Max price deviation: **18.39%** — nếu giá giảm hơn mức này sau khi fill hết SO → **liquidation**
- Tại 10x leverage, sau khi fill hết SO, giá chỉ cần giảm thêm ~1-2% là cháy
- **Không có stop loss** → rủi ro mất toàn bộ margin trong 1 cycle

## 3. Chiến lược tối ưu cho $300

### Best Overall ($300)

| Parameter | Value |
|-----------|-------|
| Leverage | 5x |
| Price step | 1.25% |
| Take profit | 1.0% |
| Initial margin | $8 |
| SO margin | $8 |
| Max SOs | 13 |
| Step scale | 1.10x |
| Total margin | $112 |
| **Return** | **+588.2%** |
| Cycles | 4859 (TP: 4843, Liq: 15) |
| Max DD | 27.7% |

### Kết quả trên các timeframe ($300)

| Config | TF | Return | Cycles | TP | Liq | Win Rate | Max DD |
|--------|-----|--------|--------|----|-----|----------|--------|
| best | 15m | +400.0% | 4958 | 4936 | 21 | 99.6% | 37.7% |
| best | 1h | +588.2% | 4859 | 4843 | 15 | 99.7% | 27.7% |
| best | 4h | +632.8% | 3969 | 3959 | 9 | 99.7% | 20.9% |

## 4. Chiến lược tối ưu cho $500

### Best Overall ($500)

| Parameter | Value |
|-----------|-------|
| Leverage | 5x |
| Price step | 1.25% |
| Take profit | 1.0% |
| Initial margin | $10 |
| SO margin | $11 |
| Max SOs | 13 |
| Step scale | 1.10x |
| Total margin | $153 |
| **Return** | **+475.5%** |
| Cycles | 5082 (TP: 5066, Liq: 15) |
| Max DD | 23.9% |

### Kết quả trên các timeframe ($500)

| Config | TF | Return | Cycles | TP | Liq | Win Rate | Max DD |
|--------|-----|--------|--------|----|-----|----------|--------|
| best | 15m | +330.6% | 5213 | 5191 | 21 | 99.6% | 34.4% |
| best | 1h | +475.5% | 5082 | 5066 | 15 | 99.7% | 23.9% |
| best | 4h | +537.3% | 4079 | 4070 | 8 | 99.8% | 16.0% |

## 5. So sánh với các chiến lược khác

| Strategy | Vốn | Return | Max DD | Liquidation Risk | Thời gian | Phức tạp |
|----------|-----|--------|--------|------------------|-----------|----------|
| **DCA Bot (screenshot)** | $300 | Xem bảng trên | Xem trên | **CAO** (no SL) | 24/7 auto | Thấp |
| DCA Bot 1h (screenshot) | $300 | +1316.6% | 63.8% | 112 liq events | Auto | Thấp |
| MACD+RSI Futures 1d | $500 | +11.2% | <20% | Rất thấp (SL) | Active | Trung bình |
| Regime+Fusion BTC 1h | $500 | +1147.5% | 4% | Thấp | Active | Cao |
| Buy & Hold BTC | $500 | +1454.3% | ~80% | Không | Passive | Rất thấp |
| DCA Spot ($10/day) | $33,400 | +336% (~$145K) | ~60% | Không | Auto | Rất thấp |

### Nhận xét so sánh

1. **DCA Bot Futures (screenshot)** là bot grid/DCA leverage — lợi nhuận đều đặn khi thị trường sideway hoặc tăng nhẹ,
   nhưng **cực kỳ nguy hiểm khi có flash crash hoặc bear market kéo dài**.
2. **Không có stop loss + 10x leverage** = risk of ruin rất cao. Một sự kiện black swan (COVID crash -50%, FTX -30%)
   sẽ xóa sổ toàn bộ vốn.
3. So với Regime+Fusion (return +1147% với DD chỉ 4%), DCA bot có risk/reward kém hơn nhiều.
4. So với DCA Spot đơn giản, DCA bot futures phức tạp hơn nhưng rủi ro cao hơn rất nhiều.

## 6. Khuyến nghị

### Cho $300:

**Chiến lược tối ưu (balance risk/return):**
- Leverage: 5x
- Price step: 1.25%
- Take profit: 1.0%
- Initial margin: $8
- Safety order margin: $8
- Max safety orders: 13
- Step scale: 1.10x
- Total margin: $112 / $300 = 37%
- **Kết quả:** Return +588.2%, Liq: 15, Max DD 27.7%

### Cho $500:

**Chiến lược tối ưu (balance risk/return):**
- Leverage: 5x
- Price step: 1.25%
- Take profit: 1.0%
- Initial margin: $10
- Safety order margin: $11
- Max safety orders: 13
- Step scale: 1.10x
- Total margin: $153 / $500 = 31%
- **Kết quả:** Return +475.5%, Liq: 15, Max DD 23.9%

### Khi nào cần bơm thêm vốn (Add Margin)?

Bot DCA futures có nguy cơ liquidation khi:
1. **BTC giảm >15% liên tục** mà không hồi (ví dụ: bear market 2022)
2. **Flash crash** (COVID Mar 2020: -50% trong 2 ngày)
3. **Tất cả Safety Orders đã fill** và giá tiếp tục giảm

**Dấu hiệu cần bơm vốn:**
- SO ≥ 10/13 đã fill → chuẩn bị thêm margin
- Margin ratio > 80% → nguy hiểm
- BTC đang trong downtrend trên Daily/Weekly → tạm dừng bot hoặc thêm vốn

**Lời khuyên:** Luôn giữ ít nhất 30-50% vốn NGOÀI bot làm quỹ dự phòng add margin.

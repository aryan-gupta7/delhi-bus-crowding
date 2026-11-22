# Validation report

## V1: temporal hold-out on whole weekdays

| set | days | first | last |
|---|---|---|---|
| train | 11 | 2026-10-01 | 2026-10-16 |
| test | 8 | 2026-10-21 | 2026-10-30 |

### Daily boarding-ticket counts: mean NB log score per cell-day (higher is better)

| stratum (training tickets/week per cell) | cells x days | model (Poisson-gamma + phi) | B5 per-cell MLE, NB | B0 per-cell MLE, Poisson | Bc citywide-share prior, NB |
|---|---|---|---|---|---|
| <10 | 286470 | -0.4315 | -0.4432 | -0.4555 | -0.5444 |
| 10-74 | 61978 | -2.4435 | -2.4550 | -2.5942 | -3.1054 |
| >=75 | 12353 | -3.5235 | -3.5339 | -3.8494 | -4.3935 |
| all | 360801 | -0.8830 | -0.8946 | -0.9391 | -1.1161 |
| all, training mean > 0 | 188779 | -1.6117 | -1.6261 | -1.7103 | -2.0439 |

### 80% predictive intervals (cells with training mean >= 5 tickets/day)

| predictor | cells x days | 80% interval coverage | interval score |
|---|---|---|---|
| model | 40210 | 0.8231 | 19.3015 |
| B5 | 40210 | 0.8162 | 19.4103 |

### OD pairs: mean log score per held-out ticket (higher is better)

| tier (training matched tickets in route-band) | held-out tickets | model (shrinkage chosen on inner split) | model (strengths as fitted) | route all-day profile | raw band profile | uniform over i<j |
|---|---|---|---|---|---|---|
| <10 | 6999 | -7.3435 | -5.5114 | -7.2888 | -8.9704 | -6.3600 |
| 10-74 | 60072 | -6.5874 | -5.2757 | -6.2395 | -7.2305 | -6.6434 |
| >=75 | 545179 | -6.0498 | -5.2582 | -5.5828 | -5.8789 | -6.9806 |
| all | 612250 | -6.1174 | -5.2628 | -5.6668 | -6.0469 | -6.9404 |

### Flow rank agreement against the like-for-like held-out target

| stratum | predictor | cells | Spearman vs target | top-decile overlap |
|---|---|---|---|---|
| all cells | model Q-hat (shrinkage chosen on inner split) | 1,302,846 | 0.8199 | 0.8201 |
| all cells | model Q-hat (strengths as fitted) | 1,302,846 | 0.8065 | 0.7890 |
| all cells | B0 | 1,302,846 | 0.7443 | 0.6390 |
| all cells | B1 | 1,302,846 | 0.6265 | 0.4076 |
| all cells | B2 | 1,302,846 | 0.8327 | 0.8183 |
| all cells | B3 | 1,302,846 | 0.7593 | 0.6813 |
| all cells | B4 | 1,302,846 | 0.6263 | 0.4081 |
| all cells | replicate ceiling (a predictor as noisy as the target) | 1,302,846 | 0.8790 |  |
| all cells | noise-free ceiling (sqrt of replicate ceiling) | 1,302,846 | 0.9376 |  |
| route-hour tier <10 | model Q-hat (shrinkage chosen on inner split) | 867,623 | 0.5897 | 0.5537 |
| route-hour tier <10 | model Q-hat (strengths as fitted) | 867,623 | 0.5720 | 0.5105 |
| route-hour tier <10 | B0 | 867,623 | 0.5016 | 0.3631 |
| route-hour tier <10 | B1 | 867,623 | 0.4034 | 0.2147 |
| route-hour tier <10 | B2 | 867,623 | 0.6023 | 0.5463 |
| route-hour tier <10 | B3 | 867,623 | 0.5265 | 0.4225 |
| route-hour tier <10 | B4 | 867,623 | 0.4038 | 0.2145 |
| route-hour tier <10 | replicate ceiling (a predictor as noisy as the target) | 867,623 | 0.6705 |  |
| route-hour tier <10 | noise-free ceiling (sqrt of replicate ceiling) | 867,623 | 0.8188 |  |
| route-hour tier 10-74 | model Q-hat (shrinkage chosen on inner split) | 356,321 | 0.8315 | 0.6844 |
| route-hour tier 10-74 | model Q-hat (strengths as fitted) | 356,321 | 0.7722 | 0.6221 |
| route-hour tier 10-74 | B0 | 356,321 | 0.4293 | 0.3493 |
| route-hour tier 10-74 | B1 | 356,321 | 0.0970 | 0.1537 |
| route-hour tier 10-74 | B2 | 356,321 | 0.8263 | 0.6851 |
| route-hour tier 10-74 | B3 | 356,321 | 0.5263 | 0.4559 |
| route-hour tier 10-74 | B4 | 356,321 | 0.0964 | 0.1552 |
| route-hour tier 10-74 | replicate ceiling (a predictor as noisy as the target) | 356,321 | 0.8640 |  |
| route-hour tier 10-74 | noise-free ceiling (sqrt of replicate ceiling) | 356,321 | 0.9295 |  |
| route-hour tier >=75 | model Q-hat (shrinkage chosen on inner split) | 78,902 | 0.9427 | 0.8023 |
| route-hour tier >=75 | model Q-hat (strengths as fitted) | 78,902 | 0.9157 | 0.7801 |
| route-hour tier >=75 | B0 | 78,902 | 0.3865 | 0.4189 |
| route-hour tier >=75 | B1 | 78,902 | 0.1750 | 0.2281 |
| route-hour tier >=75 | B2 | 78,902 | 0.9438 | 0.8180 |
| route-hour tier >=75 | B3 | 78,902 | 0.5821 | 0.5309 |
| route-hour tier >=75 | B4 | 78,902 | 0.1757 | 0.2323 |
| route-hour tier >=75 | replicate ceiling (a predictor as noisy as the target) | 78,902 | 0.9569 |  |
| route-hour tier >=75 | noise-free ceiling (sqrt of replicate ceiling) | 78,902 | 0.9782 |  |
| band am | model Q-hat (shrinkage chosen on inner split) | 248,443 | 0.8738 | 0.8476 |
| band am | model Q-hat (strengths as fitted) | 248,443 | 0.8583 | 0.8227 |
| band am | B0 | 248,443 | 0.7630 | 0.6344 |
| band am | B1 | 248,443 | 0.6030 | 0.3685 |
| band am | B2 | 248,443 | 0.8851 | 0.8580 |
| band am | B3 | 248,443 | 0.7885 | 0.6847 |
| band am | B4 | 248,443 | 0.6023 | 0.3665 |
| band am | replicate ceiling (a predictor as noisy as the target) | 248,443 | 0.9255 |  |
| band am | noise-free ceiling (sqrt of replicate ceiling) | 248,443 | 0.9620 |  |
| band mid | model Q-hat (shrinkage chosen on inner split) | 402,066 | 0.8008 | 0.7952 |
| band mid | model Q-hat (strengths as fitted) | 402,066 | 0.7876 | 0.7697 |
| band mid | B0 | 402,066 | 0.7155 | 0.6205 |
| band mid | B1 | 402,066 | 0.5713 | 0.3848 |
| band mid | B2 | 402,066 | 0.7990 | 0.7866 |
| band mid | B3 | 402,066 | 0.7302 | 0.6755 |
| band mid | B4 | 402,066 | 0.5712 | 0.3816 |
| band mid | replicate ceiling (a predictor as noisy as the target) | 402,066 | 0.8469 |  |
| band mid | noise-free ceiling (sqrt of replicate ceiling) | 402,066 | 0.9203 |  |
| band pm | model Q-hat (shrinkage chosen on inner split) | 271,431 | 0.8545 | 0.8197 |
| band pm | model Q-hat (strengths as fitted) | 271,431 | 0.8383 | 0.7851 |
| band pm | B0 | 271,431 | 0.7544 | 0.6039 |
| band pm | B1 | 271,431 | 0.6036 | 0.3534 |
| band pm | B2 | 271,431 | 0.8466 | 0.8153 |
| band pm | B3 | 271,431 | 0.7698 | 0.6578 |
| band pm | B4 | 271,431 | 0.6030 | 0.3500 |
| band pm | replicate ceiling (a predictor as noisy as the target) | 271,431 | 0.8836 |  |
| band pm | noise-free ceiling (sqrt of replicate ceiling) | 271,431 | 0.9400 |  |
| band eve | model Q-hat (shrinkage chosen on inner split) | 197,425 | 0.7926 | 0.7995 |
| band eve | model Q-hat (strengths as fitted) | 197,425 | 0.7758 | 0.7582 |
| band eve | B0 | 197,425 | 0.7030 | 0.5959 |
| band eve | B1 | 197,425 | 0.5821 | 0.3442 |
| band eve | B2 | 197,425 | 0.8006 | 0.7928 |
| band eve | B3 | 197,425 | 0.7171 | 0.6411 |
| band eve | B4 | 197,425 | 0.5821 | 0.3468 |
| band eve | replicate ceiling (a predictor as noisy as the target) | 197,425 | 0.8481 |  |
| band eve | noise-free ceiling (sqrt of replicate ceiling) | 197,425 | 0.9209 |  |
| band night | model Q-hat (shrinkage chosen on inner split) | 183,481 | 0.4782 | 0.6661 |
| band night | model Q-hat (strengths as fitted) | 183,481 | 0.4662 | 0.6063 |
| band night | B0 | 183,481 | 0.5066 | 0.5430 |
| band night | B1 | 183,481 | 0.4665 | 0.4335 |
| band night | B2 | 183,481 | 0.6560 | 0.6814 |
| band night | B3 | 183,481 | 0.5261 | 0.5931 |
| band night | B4 | 183,481 | 0.4664 | 0.4348 |
| band night | replicate ceiling (a predictor as noisy as the target) | 183,481 | 0.7703 |  |
| band night | noise-free ceiling (sqrt of replicate ceiling) | 183,481 | 0.8777 |  |

### Where along a route the load peaks (within-route-hour shape)

| stratum | predictor | within-route-hour shape Spearman |
|---|---|---|
| route-hours with target >= 20 pax/day | model Q-hat (shrinkage chosen on inner split) | 0.8420 |
| route-hours with target >= 20 pax/day | model Q-hat (strengths as fitted) | 0.7963 |
| route-hours with target >= 20 pax/day | B2 | 0.8358 |

### Level agreement with the held-out target (weighted kappa; each predictor uses its own training cuts)

| stratum | predictor | cells | weighted kappa |
|---|---|---|---|
| all stretch-hours | model Q-hat (shrinkage chosen on inner split) | 269,789 | 0.8286 |
| band am | model Q-hat (shrinkage chosen on inner split) | 66,064 | 0.8357 |
| band mid | model Q-hat (shrinkage chosen on inner split) | 89,056 | 0.8064 |
| band pm | model Q-hat (shrinkage chosen on inner split) | 68,164 | 0.8312 |
| band eve | model Q-hat (shrinkage chosen on inner split) | 37,603 | 0.8228 |
| band night | model Q-hat (shrinkage chosen on inner split) | 8,902 | 0.7304 |
| all stretch-hours | model Q-hat (strengths as fitted) | 269,789 | 0.8068 |
| band am | model Q-hat (strengths as fitted) | 66,064 | 0.8261 |
| band mid | model Q-hat (strengths as fitted) | 89,056 | 0.7742 |
| band pm | model Q-hat (strengths as fitted) | 68,164 | 0.8120 |
| band eve | model Q-hat (strengths as fitted) | 37,603 | 0.7936 |
| band night | model Q-hat (strengths as fitted) | 8,902 | 0.6583 |
| all stretch-hours | B2 | 269,789 | 0.8298 |
| band am | B2 | 66,064 | 0.8425 |
| band mid | B2 | 89,056 | 0.8099 |
| band pm | B2 | 68,164 | 0.8240 |
| band eve | B2 | 37,603 | 0.8134 |
| band night | B2 | 8,902 | 0.7776 |

### Profile-shrinkage multiplier (inner split of the training days)

| strength multiplier | inner-split shape Spearman | chosen |
|---|---|---|
| 1.0000 | 0.7421 | False |
| 0.3000 | 0.7539 | False |
| 0.1000 | 0.7510 | False |
| 0.0300 | 0.7672 | False |
| 0.0100 | 0.7729 | False |
| 0.0030 | 0.7882 | False |
| 0.0010 | 0.7945 | False |
| 0.0003 | 0.7947 | True |
| 0.0000 | 0.7907 | False |

target cells of route-bands with no matched test ticket (set to 0): 31.3% of segment-hours

## V7: known-pattern assertions

| assertion | observed | threshold | held | note |
|---|---|---|---|---|
| two weekday peaks: AM and PM peak hour each >= 1.5x the midday mean hour | {'am': 4.87, 'pm': 2.9} | >= 1.5 | True | weak: the ticket hour profile is carried into the estimate by construction |
| weekend peak-to-midday ratio is below the weekday ratio | 3.31 vs 4.87 | weekend < weekday | True |  |
| AM: inbound routes carry a larger AM share of their flow than outbound routes | 0.446 vs 0.250 | inbound > outbound | True | radial routes only; inbound = last stop nearer the Connaught Place centroid |
| PM: outbound routes carry a larger PM share of their flow than inbound routes | 0.348 vs 0.186 | outbound > inbound | True |  |
| Sundays carry fewer tickets than weekdays (median daily passengers; real Sundays only, so the day-type rule cannot decide it) | 51831 vs 102021 | Sunday < 0.9 x weekday | True |  |
| code check: AM/PM peak ratio of passenger-segments | 1.4200 | about 1.5 (profiled) | True | the data assert this about themselves; kept only to catch a code bug |
| named hubs' busiest stretch ranks above suburban end-points (09h pressure percentile) | hubs 1.00 (n=8) vs controls 0.94 (n=4) | hub median >= 0.9 and > controls | True | hub and control lists are assumptions (config validation.hub_names / control_names) |

## V8-lite: planner on random queries (each query is a ride on one scheduled route, so a direct journey always exists: 'answered' is a light check)

| queries | n | answered | crashes | comfortable card shown | latency p50 (s) | latency p95 (s) |
|---|---|---|---|---|---|---|
| all queries | 200 | 0.9850 | 0 | 0.0000 | 0.1424 | 0.7117 |
| peak am (07-10) | 61 | 1.0000 | 0 | 0.0000 | 0.1492 | 0.9415 |
| midday (11-16) | 60 | 1.0000 | 0 | 0.0000 | 0.1563 | 0.7131 |
| peak pm (17-20) | 79 | 0.9620 | 0 | 0.0000 | 0.1152 | 0.5212 |

## V9: sensitivity of recommendations to the invented assumptions

| setting | robust share (exposure-weighted) | shown: peak am (07-10) | shown: midday (11-16) | shown: peak pm (17-20) | calmer candidate has a central advantage | recommendations changed vs base | exposure share whose level changes vs base |
|---|---|---|---|---|---|---|---|
| base: sigma 0.4, theta in {-0.4,-0.2,0} | 0.5003 | 0.0149 | 0.0000 | 0.0046 | 0.1900 | 0.0000 | 0.0000 |
| route effect sigma 0.0 | 0.7705 | 0.0547 | 0.0167 | 0.0411 | 0.1900 | 0.0317 | 0.0000 |
| route effect sigma 0.9 | 0.4725 | 0.0000 | 0.0000 | 0.0000 | 0.1900 | 0.0067 | 0.0000 |
| theta = 0 only (constant capture) | 0.5438 | 0.0100 | 0.0000 | 0.0046 | 0.1900 | 0.0017 | 0.0000 |
| theta = -0.2 only | 0.5320 | 0.0199 | 0.0056 | 0.0046 | 0.1900 | 0.0033 | 0.0000 |
| small-N: Pi shrink n0=2 | 0.4925 | 0.0249 | 0.0056 | 0.0046 | 0.1917 | 0.0050 | 0.0837 |
| small-N: 1/4-1/2-1/4 smoothing of N | 0.4906 | 0.0149 | 0.0000 | 0.0046 | 0.1917 | 0.0033 | 0.1124 |
| multipliers 1.0/1.25/1.6 | 0.5003 | 0.0050 | 0.0000 | 0.0000 | 0.0683 | 0.0050 | 0.0000 |
| multipliers 1.0/1.3/3.0 | 0.5003 | 0.0050 | 0.0000 | 0.0046 | 0.2117 | 0.0033 | 0.0000 |

### Robustness value Gamma* (smallest coverage difference that erases the advantage)

| candidates | n | median Gamma* | share >= 1.61x (sigma 0.4) | share >= 2.91x (sigma 0.9) |
|---|---|---|---|---|
| suppressed | 110 | 1.0000 | 0.1545 | 0.0455 |
| shown | 4 | 2.6484 | 1.0000 | 0.2500 |

## V10: do recommendations made on training days hold on held-out days? (week-to-week stability under the same unidentified scale; not a test of correctness)

| group | queries | calmer still lower on held-out days | advantage still >= margin |
|---|---|---|---|
| shown (robust in range) | 10 | 10/10 (100%; 95% CI 69%-100%) | 10/10 (100%) |
| suppressed (central advantage, not robust) | 44 | 38/44 (86%; 95% CI 73%-95%) | 31/44 (70%) |

Queries not judged: fewer than two options: 16, no central advantage: 1183, stretch without estimate or held-out flow: 247

## V11: week-to-week stability (model fitted separately on each full weekday week)

| weeks | cells | Spearman of Q-hat | level weighted kappa |
|---|---|---|---|
| 2026-10-05 vs 2026-10-12 | 1220115 | 0.9014 | 0.8174 |
| 2026-10-12 vs 2026-10-26 | 1218349 | 0.9128 | 0.8486 |

2 pair(s) of consecutive full weeks: October has full five-day weekday weeks on 5-9, 12-16 and 26-30 Oct (19-23 Oct loses a day to a stream fault and a holiday), so the pairs are 5/12 Oct and 12/26 Oct (the latter skips a week).

## V3: rerun on new files (time slices, frozen thresholds)

| check | result | passed |
|---|---|---|
| first half: GTFS-only artefacts (patterns, segments, stretches) bit-identical to the reference | True | True |
| first half: weekday level agreement with the reference (frozen cuts), weighted kappa on 210,508 cells | 0.9370 | True |
| second half: GTFS-only artefacts (patterns, segments, stretches) bit-identical to the reference | True | True |
| second half: weekday level agreement with the reference (frozen cuts), weighted kappa on 191,804 cells | 0.9300 | True |
| full rerun in a fresh directory reproduces the reference reproducibility hash | True | True |

**What no metric here can show:** crowding truth (the passengers per seat a rider meets). The tickets are a ~2.6% digital-ticket sample without trip identifiers or alighting counts; the held-out tests validate the estimator of the *sampled* process (volumes, spatial profiles, levels), not absolute loads, cross-route or cross-hour scale, true alighting or seat availability. V3 slices are subsets of the reference data, so V3 tests rerun determinism, not generalisation. V9 is a sensitivity analysis, not unseen-case evidence.

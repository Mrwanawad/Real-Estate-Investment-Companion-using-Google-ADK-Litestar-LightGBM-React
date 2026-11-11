# Financing reference values

Every expected value below was computed independently of `reic.modules.financing` (plain
Python `fractions.Fraction` / float scripts and by hand), then asserted in the tests.
Conventions: `*_pct` inputs are fractions (0.10 = 10%); money is rounded half-up to 0.01 EGP;
month 0 is signing; NPV/IRR use numpy-financial's convention (index 0 undiscounted).

## Mortgage

| Case | Working | Expected | Test |
|---|---|---|---|
| 1,000,000 EGP, 12% nominal annual, 10 years, monthly | r = 0.12/12 = 0.01, n = 120, PMT = L*r / (1 - (1+r)^-n) = 14,347.0948... | PMT 14,347.09; month 1 interest 10,000.00, principal 4,347.09, balance 995,652.91; total interest about 721,651 (120 x 14,347.09 - 1,000,000 = 721,650.80, last payment adjusts by cents) | `test_mortgage_reference_one_million_twelve_percent_ten_years` |
| 100,000 EGP, 12%, 1 year | PMT = 8,884.8788... rounds to 8,884.88; rows rebuilt by hand with half-up rounding: m1 interest 1,000.00 / principal 7,884.88 / balance 92,115.12; m2 interest 921.15 / balance 84,151.39; m12 payment 8,884.85 (clears balance), interest 87.97 | total interest 6,618.53; total paid 106,618.53 (= 11 x 8,884.88 + 8,884.85) | `test_mortgage_small_loan_full_amortisation_reference` |
| 100 EGP, 0%, 1 year | 100/12 = 8.3333 -> 8.33 x 11 = 91.63; last = 8.37 | rows 8.33 x 11 and 8.37 | `test_zero_rate_mortgage` |
| IRR of the loan flows | Rate per month must equal 0.12/12 | 0.010000 monthly, 0.126825 annualised (1.01^12 - 1) | `test_irr_of_loan_cash_flows_is_monthly_rate` |

Note on rounding: rounding the payment to the piastre shifts the balance by up to 0.005 per
month, compounded at the loan rate; the final payment absorbs it, so the last payment can differ
from the regular one by more than a cent on large, high-rate loans (e.g. a few EGP on 4.2M at
22.5% over 20 years). Totals still tie exactly.

## Installment plans

| Case | Working | Expected |
|---|---|---|
| 3,000,000 unit, 10% down, 7 years quarterly, no interest | down 300,000.00; balance 2,700,000; 28 installments; 2,700,000 / 28 = 96,428.5714... -> 96,428.57; 27 x 96,428.57 = 2,603,571.39; last = 2,700,000 - 2,603,571.39 = 96,428.61 | 28 installments, 27 of 96,428.57 and the final (month 84) 96,428.61; total exactly 3,000,000.00 |
| 2,000,000, 10% down, 20% at delivery (month 36), 5% maintenance, 5 years annual, 5% cash discount | down 200,000; delivery 400,000; maintenance 100,000; balance 1,400,000 / 5 = 280,000 at months 12..60 | total nominal 2,100,000.00 (price + maintenance); cash price 1,900,000.00; month 36 outflow 780,000.00 |
| 1,000,000, 10% down, 3 years annual, 10% annual escalation | balance 900,000; weights 1, 1.1, 1.21 (sum 3.31); 900,000/3.31 = 271,903.323...; x1.1 = 299,093.655...; x1.21 = 329,003.021... | 271,903.32, 299,093.66, 329,003.02 (last = 900,000 - 271,903.32 - 299,093.66) |

## NPV, IRR, PV

| Case | Working | Expected |
|---|---|---|
| Flows [-100, 39, 59, 55, 20] at 10% per period, t=0 first | exact fraction sum(c_t / 1.1^t) = 573,890 / 14,641 = 39.19745... | NPV 39.20. The brief quoted 38.88; that figure does not follow from these flows under the t=0-first convention, and numpy-financial agrees with 39.1974591899 |
| IRR of the same flows | bisection on sum(c_t/(1+x)^t) = 0 | 0.280948 (about 0.2809), numpy-financial 0.28094842115996 |
| 1,000,000 due in month 12, 20% effective annual | 1,000,000 / 1.2 (monthly rate 1.2^(1/12) - 1 = 0.0153094705) | PV 833,333.33 |
| 100,000 now + 900,000 at month 12, 20% | 100,000 + 900,000/1.2 | PV 850,000.00 |

## Comparison (price 1,000,000, 20% discount rate, 5% cash discount, plan 10% down + balance at month 12)

Cash price 950,000.00 (PV 950,000.00); plan PV 850,000.00; effective cost vs cash -100,000.00;
plan max monthly outflow 900,000.00, average 900,000 / 12 = 75,000.00; plan is cheapest.

## Cross-checks against numpy-financial (not hand values)

- 12 PMT/IPMT cases (`PMT_CASES`): payment within 0.005 of `npf.pmt`; total interest within a bound derived from the compounded cent rounding.
- 12 seeded random flow series each for NPV (within 0.0051 of `npf.npv`) and IRR (within 5e-7 of `npf.irr`).

## Property tests (seeded loops)

Installment sums equal price + maintenance exactly; mortgage balance ends at 0.00 and totals tie; PV of any plan at 0% discount equals nominal total; PV at positive rates never exceeds nominal; IRR of a loan equals rate/12 within 1e-6.

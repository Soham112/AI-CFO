---
name: cfo-tax-allocation
description: Cross-border (US/India) tax-aware allocation - which account and vehicle to use, EPF/PPF/FD vs US T-bills/401k/IRA, PFIC rules for Indian mutual funds, NRI rules, FBAR. Use for "should I keep my SIP / EPF / FD" or "where should I hold this".
---

# Tax-aware allocation

Read `config/profile.yaml` first. If citizenship, visa/green card status, plan to return to
India, or tax bracket are TODO, ask the user once - they change the answer.

## Order of operations for a US tax resident
1. Emergency fund (6 months) in HYSA / T-bills.
2. 401(k) up to the employer match.
3. HSA (if eligible), Roth IRA (backdoor if over the income limit).
4. Rest of 401(k).
5. Taxable brokerage: broad index ETFs (tax-efficient), India via US-listed ETFs.
6. India-side money only for INR goals (parents, return to India, property).

## Placement
- Tax-inefficient (gold ETFs = collectibles 28%, bonds, REITs, high-turnover) → IRA/401k.
- Tax-efficient broad equity ETFs → taxable.
- **Never** Indian MFs/ETFs in a US-taxable life without a CPA (PFIC, Form 8621).

## Guaranteed products
Run `python -m dicfo fixed-income` and explain the "real in spend currency" column: an 8%
INR return minus ~3%/yr rupee depreciation and US tax can be worse than US T-bills.

## Indian residents (if the profile changes)
Equity LTCG 12.5% over Rs1.25L, STCG 20%; EPF/VPF/PPF are EEE; debt MFs bought after Apr 2023
taxed at slab; use ELSS only under the old regime.

Always end with "confirm with a cross-border CPA/CA" for anything involving PFIC, FBAR, or
residency changes.

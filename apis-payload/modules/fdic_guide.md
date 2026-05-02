# FDIC BankFind Suite

Script: `projects/apis/fdic/fdic.py`
Base URL: `https://api.fdic.gov/banks`
Docs: `https://api.fdic.gov/banks/docs/`
Auth: None required
Rate limit: No formal limit (max 10,000 records per request; offset-based pagination)
Dependencies: `requests`


## Triggers

Use for: individual bank financials (balance sheet, income, credit quality, deposits, capital), banking system aggregates (1934-present), bank failures and resolution details, CRE concentration screening, uninsured deposit risk, NIM and funding cost analysis, peer comparison across any Call Report field, branch locations with lat/lng, M&A and structure change history, deposit market share (SOD), state-level and community bank analysis, HTM/AFS unrealized securities losses (the SVB-style interest rate risk indicator), interest-rate repricing gap analysis, holding company linkage (CERT to HC and all subsidiary roster), Minority Depository Institutions (MDIs), de novo / newly chartered banks, Community Bank Leverage Ratio (CBLR) qualified banks, Federal Reserve district breakdown, specialty bank categorization (agricultural, credit card monoline, trust, mortgage originators), PPP loan exposure, foreign office exposure, asset-size distribution, efficiency ratio distribution, charge-off waterfall by loan type, non-performing asset ratio screen, structure change aggregation by CHANGECODE, M&A wave analysis by year, comprehensive multi-section bank profile ("snapshot").

Not for: bank holding company consolidated data (FFIEC FR Y-9C), weekly banking aggregates (FRED H.8), bank stock prices (market data), 10-K/10-Q text (SEC EDGAR), non-US banks (BIS), Treasury auctions (TreasuryDirect), overnight funding rates (NY Fed), commercial paper / CD rates (FRED).


## Data Catalog

### Endpoints

| Endpoint | ~Records | Description |
|----------|----------|-------------|
| `/institutions` | ~14,000 | Bank demographics: name, location, charter, assets, deposits, ROA/ROE |
| `/financials` | millions | Quarterly Call Report data (RISVIEW): 2,377 fields per CERT+REPDTE |
| `/failures` | ~4,100 | Every bank failure 1934-present with resolution type and DIF cost |
| `/summary` | ~5,000 | Industry aggregates by year from 1934 (filterable by state, type) |
| `/locations` | ~80,000 | Branch locations with lat/lng, service type, main office flag |
| `/sod` | millions | Summary of Deposits: branch-level annual deposit data from ~1994 |
| `/history` | ~200,000 | Structure events: mergers, acquisitions, name changes, charter conversions |
| `/demographics` | sparse | Community demographics tied to CERT + REPDTE |

### Monetary Units

All dollar amounts are in **thousands** ($000s):

| API Value | Actual Dollars |
|-----------|---------------|
| ASSET: 3752662000 | $3.75 TRILLION |
| DEP: 438331000 | $438 BILLION |
| NETINC: 8737000 | $8.7 BILLION |
| COST: 23460 | $23.5 MILLION |

### Filter Syntax

Elasticsearch query string syntax. All field names and values must be UPPERCASE.

```
NAME:"First Bank"                         Exact phrase match
STALP:NY AND ACTIVE:1                    Boolean AND
NAME:"First Bank" OR NAME:"Unibank"      Boolean OR
STNAME:("West Virginia","Delaware")       Multi-value (any of)
!(STNAME:"Virginia")                      Exclusion (NOT)
DEP:[50000 TO *]                          Numeric range inclusive ($000s)
DATEUPDT:["2010-01-01" TO "2010-12-31"]   Date range inclusive
FAILYR:{2015 TO 2016}                     Range exclusive
```

### Key Identifiers

| Field | Description |
|-------|-------------|
| CERT | FDIC certificate number (primary key across all endpoints) |
| REPDTE | Report date YYYYMMDD (quarter ends: 0331, 0630, 0930, 1231) |
| UNINUM | FDIC unique number for branches |
| NAME | Legal institution name |
| ACTIVE | 1 = open and insured, 0 = closed |

### The Full RISVIEW Universe

The `/financials` endpoint draws from the full RISVIEW schema: **2,377 fields** covering every line item from the quarterly Call Report (FFIEC 031/041/051). Fields follow a strict prefix + suffix naming convention. Pass any field name in `--fields`; the 60+ curated presets select commonly needed subsets.

**Field suffixes**

| Suffix | Meaning | Example |
|--------|---------|---------|
| (none) | Base dollar value in thousands | ASSET = total assets |
| R | Ratio (typically % of assets) | ASSETR, DEPR, LNRER |
| Q | Quarterly (vs default YTD cumulative) | NETINCQ, NIMQ |
| A | Annualized | NIMA, EINTEXPA, ILNA |
| J | Adjusted | LNATRESJ = allowance + allocated transfer risk |
| DOM / FOR | Domestic / Foreign offices | DEPDOM, DEPFOR, ILNDOM, ILNFOR |

**Prefix families (2,377 fields total)**

| Prefix | Count | Concept |
|--------|-------|---------|
| LN* | 272 | Loans by type (RE, C&I, consumer, ag, credit card, leases) |
| NT* | 95 | Net charge-offs by loan type |
| DR* | 54 | Gross charge-offs by loan type |
| CR* | 54 | Loan recoveries by loan type |
| P3* | 54 | 30-89 day past due by loan type |
| P9* | 53 | 90+ day past due by loan type |
| NA* | 55 | Non-accrual by loan type |
| NC* | 45 | Non-current total (= 90+ past due + non-accrual) |
| DEP* | 30 | Deposits by type and insurance tier |
| NTR*/TRN* | 40 | Transaction vs non-transaction deposits |
| CD* | 8 | Time deposit maturity buckets |
| SC* | 69 | Securities by type (UST, agency, MBS, muni, ABS, foreign) |
| EQ* | 26 | Equity capital components |
| RBC*/IDT1* | 12 | Regulatory capital ratios (Tier 1, Total, Leverage, CET1) |
| I* (income) | 50+ | Interest income by asset type, fee income, gains/losses |
| E* (expense) | 30+ | Interest expense, operating expense |
| UC* | 16 | Unused commitments (credit lines) |
| LOC* | 7 | Standby letters of credit |
| ENCE*/ASCE* | 12 | Credit enhancements / recourse exposure |
| ABCU*/ABCX* | 4 | Asset-backed unused commit / credit exposure |
| SZ* | 68 | Securitization exposures (past due, charge-offs, recoveries, commits) |
| RS*/NARS* | 20 | Restructured (TDR) loans (current and non-accrual) |
| OTB*/OTHB* | 20 | FHLB advances and other borrowings by maturity |
| FX* / RT* / OTH*FFC/NVS/POC/WOC | 30+ | Derivative contracts (FX, interest rate, equity, commodity) |
| TRADE*/TR* | 14 | Trading accounts, trading liabilities, revaluation |
| TFRA/TC*/TE*/TF*/TI*/T[MOP]* | ~150 | Fiduciary / trust accounts and fee income |
| CH* | 14 | Cash, currency, balances due (Fed, other banks) |
| OR* | 11 | Other real estate owned (foreclosed) |
| OALI* | 5 | Bank-owned life insurance (general/separate/hybrid accounts) |
| SZ25/SZ100/SZ1B/SZ10B/SZ250B | 20+ | Asset size bucket flags |
| CB/BK*/INS*/CLCODE | 20+ | Charter, insurance, regulatory metadata |

Full field schema: `https://api.fdic.gov/banks/docs/risview_properties.yaml`

### Key Identifiers and Metadata

| Field | Description |
|-------|-------------|
| CERT | FDIC certificate number (primary key across all endpoints) |
| REPDTE | Report date YYYYMMDD (quarter ends: 0331, 0630, 0930, 1231) |
| NAME | Legal institution name |
| ACTIVE | 1 = open and insured, 0 = closed |
| BKCLASS | Charter class (N=national, SM=state member, NM=state nonmember, SB=savings bank, SA=savings assn) |
| CB | Community bank flag (1/0) |
| INSDIF | Deposit Insurance Fund member flag |
| SZ100T1B / SZ1BP / SZ10BP / SZ250BP | Asset size bucket flags ($100M-$1B, >$1B, >$10B, >$250B) |
| STALP | State abbreviation; STNAME = full state name |
| FED | Federal Reserve district (1-12) |
| REGAGNT | Primary federal regulator (FDIC, FRB, OCC, OTS) |
| SPECGRP | Asset concentration hierarchy (0-9); SPECGRPDESC = description |

### Balance Sheet: Assets

| Field | Description |
|-------|-------------|
| ASSET | Total assets (includes cash, loans, securities, premises, off-B/S excluded) |
| ERNAST | Total earning assets |
| ASSTLT | Long-term assets (5+ year repricing) |
| CHBAL | Cash & due from depository institutions |
| CHBALI / CHBALNI | Interest-bearing / noninterest-bearing cash |
| CHFRB | Balance due from Federal Reserve Bank |
| CHCOIN | Currency & coin |
| CHCIC / CHITEM | Cash items / cash items collected in domestic offices |
| CHUS / CHNUS | Balances due from US / non-US banks |
| SC | Total securities (see Securities section for breakdown) |
| LNLSGR | Gross loans & leases (+ unearned income) |
| LNLSNET | Net loans & leases (gross - allowance - unearned) |
| UNINC | Unearned income |
| LNATRES | Allowance for loan & lease losses (ALLL) |
| TRADE | Trading account assets |
| BKPREM | Premises & fixed assets |
| ORE | Other real estate owned (foreclosed properties) |
| INTAN | Total intangible assets |
| INTANGW | Goodwill |
| INTANGCC | Purchased credit card relationships & nonmortgage servicing assets |
| INTANMSR | Mortgage servicing assets |
| INTANOTH | Other identifiable intangibles |
| OA | Other assets |
| AOA | All other assets |
| OALIFINS | Bank-owned life insurance assets (total) |
| OALIFGEN / OALIFSEP / OALIFHYB | Life insurance general / separate / hybrid accounts |
| INVSUB | Investments in unconsolidated subsidiaries |
| INVSUORE | Investments in real estate (subsidiaries) |

### Balance Sheet: Liabilities

| Field | Description |
|-------|-------------|
| LIAB | Total liabilities |
| LIABEQ | Total liabilities + equity (must equal ASSET) |
| DEP | Total deposits (domestic + foreign) |
| DEPDOM | Deposits in domestic offices |
| DEPFOR | Deposits in foreign offices |
| DEPI | Interest-bearing deposits (total) |
| DEPIDOM / DEPIFOR | Interest-bearing deposits (domestic / foreign) |
| DEPNI | Noninterest-bearing deposits (total) |
| DEPNIDOM / DEPNIFOR | Noninterest-bearing deposits (domestic / foreign) |
| FREPP | Fed funds purchased + repos (short liability) |
| FREPO | Fed funds sold + reverse repos (asset side - flipped) |
| FFPUR | Federal funds purchased |
| REPOPUR | Repurchase agreements (sold under agreement to repurchase) |
| REPOPURF | Repo agreements - foreign |
| REPOSLDF | Reverse repo agreements - foreign |
| OBOR | Other borrowed funds |
| OTHBOR | Other borrowed money |
| OTHBRF | Other borrowed funds (alternate aggregate) |
| OTHBFHLB | FHLB borrowings (total) |
| SUBND | Subordinated notes & debentures |
| SUBLLPF | Subordinated debt + limited-life preferred stock |
| TRADEL | Trading liabilities |
| ALLOTHL | All other liabilities |
| OLMIN | Other liabilities + minority interest in subsidiaries |
| TTL | Treasury tax & loan note option |
| TTLOTBOR | TT&L + other borrowings |
| LLPFDSTK | Limited-life preferred stock |
| ACEPT | Bank's liability on acceptances |

### Balance Sheet: Equity Capital

| Field | Description |
|-------|-------------|
| EQTOT / EQ | Total equity capital |
| EQCS | Common stock |
| EQPP | Perpetual preferred stock |
| EQSUR | Surplus |
| EQUP | Undivided profits (retained earnings) |
| EQUPGR | Undivided profits (gross) |
| EQUPTOT | Undivided profits + net & other capital components |
| EQCCOMPI | Other comprehensive income (AOCI) |
| EQCTRSTX | Treasury stock transactions |
| EQCSTKRX | Sale of capital stock |
| EQCDIV | Cash dividends (common + preferred) |
| EQCDIVC / EQCDIVP | Cash dividends on common / preferred |
| EQCDIVNTINC | Cash dividends / net income ratio |
| EQCMRG | Changes due to mergers |
| EQCREST | Accounting changes & corrections |
| EQCPREV | Bank equity capital, most recently reported |
| EQCONSUB | Minority interest in consolidated subsidiaries |
| EQCBHCTR | Transactions with bank holding company |
| EQCFCTA | Cumulative foreign currency translation adjustments |
| EQNWCERT | Net worth certificates (for thrifts) |
| EQOTHCC | Other equity capital components |
| EQV | Bank equity capital / assets ratio |

### Loan Composition (272 LN* fields)

**Top-level loan categories**

| Field | Description |
|-------|-------------|
| LNRE | Real estate loans (total) |
| LNCI | Commercial & industrial loans (total) |
| LNCON | Consumer loans (total) |
| LNAG | Agricultural loans (not RE-backed) |
| LNMUNI | Municipal / obligations of states & political subdivisions |
| LNFG | Foreign government loans |
| LNDEP | Loans to depository institutions |
| LS | Lease financing receivables |
| LNOTHER | Loans to nondepository financial institutions + other |
| LNSOTHER | Other loans (all other categories) |

**Real estate loans (LNRE subcomponents)**

| Field | Description |
|-------|-------------|
| LNRECONS | Construction & land development (total) |
| LNRECNFM | 1-4 family construction loans |
| LNRECNOT | Other construction & land development |
| LNREMULT | Multifamily (5+ units) residential RE |
| LNRENRES | Nonfarm nonresidential RE (CRE offices, retail, industrial) |
| LNRENROW | Owner-occupied nonfarm nonresidential |
| LNRENROT | Other nonfarm nonresidential (investor-owned) |
| LNRERES | 1-4 family residential (total) |
| LNRERSFM | 1-4 family, first liens |
| LNRERSF2 | 1-4 family, junior liens |
| LNRELOC | 1-4 family, revolving home equity lines |
| LNREAG | Agricultural RE loans (farmland) |
| LNREFOR | RE loans in foreign offices |
| LNREDOM | RE loans in domestic offices |
| LNREJ | RE loans adjusted |
| LNCOMRE | Commercial real estate (composite) |

**C&I sub-categories (by size)**

| Field | Description |
|-------|-------------|
| LNCI1 | C&I loans under $100K |
| LNCI2 | C&I loans $100K-$250K |
| LNCI3 | C&I loans $250K-$1M |
| LNCI4 | C&I loans under $1M (small business) |
| LNCIFOR | C&I loans in foreign offices |
| LNCINUS | C&I loans to non-US borrowers |

**Consumer loans**

| Field | Description |
|-------|-------------|
| LNCRCD | Credit card loans |
| LNAUTO | Automobile loans |
| LNCRCDRP | Credit card + related plans |
| LNCONRP | Consumer loans - related plans |
| LNCONORP | Other consumer & related plans |
| LNCONOTH | Consumer loans - other (non-credit-card, non-auto) |
| LNCONFOR | Consumer loans in foreign offices |

**Ag loans (by size)**

| Field | Description |
|-------|-------------|
| LNAG1 / LNAG2 / LNAG3 / LNAG4 | Ag loans by size tier (U100K / 100-250K / 250-500K / U500K) |

**Loan maturity / repricing buckets**

| Field | Description |
|-------|-------------|
| LNRS3LES | 1-4 family RE repricing ≤ 3 months |
| LNRS3T12 | 1-4 family RE repricing 3-12 months |
| LNRS1T3 | 1-4 family RE repricing 1-3 years |
| LNRS3T5 | 1-4 family RE repricing 3-5 years |
| LNRS5T15 | 1-4 family RE repricing 5-15 years |
| LNRSOV15 | 1-4 family RE repricing over 15 years |
| LNOT3LES ... LNOTOV15 | All other loans repricing by same buckets |

**Loan status / disposition**

| Field | Description |
|-------|-------------|
| LNATRES | Allowance for loan & lease losses (ALLL) |
| LNATRESJ | Allowance + allocated transfer risk |
| LNLSRES | Allowance for loan & lease losses (alternate) |
| LNRESRE | Allowance for RE loans only |
| LNLSSALE | Loans & leases held for resale |
| LNPLEDGE | Pledged loans and leases |
| LNSERV | Principal balance of loans serviced for others |

**Small business / government programs**

| Field | Description |
|-------|-------------|
| LNSB | Small business loans sold |
| PPPLNBAL | Outstanding balance of PPP loans (post-2020) |
| PPPLNNUM | Number of PPP loans outstanding |
| PPPLNPLG | PPP loans pledged to PPPLF |

### Deposits (93 DEP* fields + 40 TRN*/NTR* transaction/nontransaction)

**Top-level deposit structure**

| Field | Description |
|-------|-------------|
| DEP | Total deposits (all offices) |
| DEPDOM | Deposits in domestic offices |
| DEPFOR | Deposits in foreign offices |
| DEPI | Interest-bearing deposits |
| DEPNI | Noninterest-bearing deposits |
| DEPIDOM / DEPIFOR | Interest-bearing by geography |
| DEPNIDOM / DEPNIFOR | Noninterest-bearing by geography |
| COREDEP | Core deposits (stable retail funding) |
| VOLIAB | Volatile liabilities (wholesale/flighty funding) |
| IRAKEOGH | IRAs and Keogh plans (retirement deposits) |

**Transaction vs Non-transaction accounts**

| Field | Description |
|-------|-------------|
| TRN | Transaction accounts (total) |
| DDT | Demand deposits (DDAs) |
| TRNIPC | Transaction - individuals, partnerships, corporations |
| TRNIPCOC | Transaction - IPC official checks |
| TRNUSGOV | Transaction - US government |
| TRNMUNI | Transaction - municipalities |
| TRNCBO | Transaction - commercial banks & others |
| TRNFC / TRNFG | Transaction - foreign country / foreign government |
| TRNNIA | Non-interest-bearing transaction accounts >$250K (amount) |
| NTR | Non-transaction accounts (total) |
| NTRSMMDA | Money market deposit accounts (MMDA) |
| NTRSOTH | Savings - other |
| NTRTIME | Time deposits (total) |
| NTRTMLG | Time deposits > $100K (legacy threshold) |
| NTRTMLGJ | Time deposits > $250K (current threshold) |
| NTRTMMED | Time deposits ≤ $250K |
| NTRCDSM | Time deposits ≤ $100K |
| NTRCDSMJ | Time deposits ≤ insurance limit |
| NTRIPC / NTRUSGOV / NTRMUNI | Non-transaction by depositor type |
| NTRCOMOT / NTRFC / NTRFG | Non-transaction by counterparty |

**Time deposit maturity buckets**

| Field | Description |
|-------|-------------|
| CD3LES | Time deposits >$250K with repricing ≤ 3 months |
| CD3LESS | Time deposits ≤$250K with repricing ≤ 3 months |
| CD3T12 / CD3T12S | Repricing 3-12 months (>$250K / ≤$250K) |
| CD1T3 / CD1T3S | Repricing 1-3 years |
| CDOV3 / CDOV3S | Repricing over 3 years |

**Deposit insurance**

| Field | Description |
|-------|-------------|
| DEPINS | Estimated insured deposits |
| DEPUNA | Est. uninsured deposits in domestic offices + insured branches |
| DEPUNINS | Estimated uninsured deposits (all) |
| ESTINS | Estimated insured percentage |
| DEPLGAMT | Amount in deposit accounts > $250K |
| DEPLGB | Number of deposit accounts > $250K |
| DEPSMAMT | Amount in deposit accounts ≤ $250K |
| DEPSMB | Number of deposit accounts ≤ $250K |
| DEPLGRA / DEPLGRN | Retirement deposit accts > $250K (amount / number) |
| DEPSMRA / DEPSMRN | Retirement deposit accts ≤ $250K (amount / number) |
| DEPBEFEX | Deposit liabilities before exclusions |
| DEPALLEX | Total allowable exclusions (foreign + others) |
| DEPCSBQ | Deposit liabilities after exclusions |

**Brokered deposits**

| Field | Description |
|-------|-------------|
| BRO | Brokered deposits (total) |
| BROINS | Brokered deposits - insured |
| BROINSLG | Brokered deposits - insured, large |
| DEPLSNB | Deposits through listing service (not brokered) |

### Securities (118 SC* fields)

**Top-level and by issuer**

| Field | Description |
|-------|-------------|
| SC | Total securities |
| SCUST | US Treasury securities (pure Treasuries) |
| SCUSO | US government obligations (Treasuries + Agency debt) |
| SCUS | US Treasury & Agency (composite) |
| SCAGE | US Agency (non-mortgage agency debt) |
| SCAOT | US Agency all other |
| SCASPNSUM | Non-mortgage issues by US govt or sponsored agencies |
| SCMUNI | Municipal securities (states, political subdivisions) |
| SCMUNIAA / SCMUNIAF | Muni AFS at amortized cost / fair value |
| SCMUNIHA / SCMUNIHF | Muni HTM at amortized cost / fair value |
| SCDOMO | Other domestic debt securities |
| SCFORD | Foreign debt securities |
| SCFDEQ | Foreign debt & equity |
| SCEQ | Equity securities |
| SCEQFV | Equity securities at readily determinable fair value |
| SCEQNFT | Equity securities not held for trading |
| SCABS | Asset-backed securities (consumer, student loan, equip, etc.) |
| SCSFP | Structured financial products - total |
| SCSNHAA / SCSNHAF | Structured notes at amortized cost / fair value |

**MBS breakdown (mortgage-backed securities)**

| Field | Description |
|-------|-------------|
| SCMTGBK | Mortgage-backed securities (total) |
| SCRMBPI | Private-issued residential MBS |
| SCCMMB | Commercial MBS (total) |
| SCCMPT | Commercial MBS pass-through |
| SCCPTG | Commercial MBS pass-through - government-issued |
| SCCMOS | Other commercial MBS |
| SCCMOG | Other commercial MBS - government-issued |
| SCCOL | US Agency collateralized MTG - residential |
| SCGTY | US Agency issued or guaranteed - residential |
| SCGNM | US Agency guaranteed by GNMA |
| SCFMN | US Agency issued FNMA - residential |
| SCODPC / SCODPI | CMOs - private issued / private certificates |

**Classification (accounting treatment)**

| Field | Description |
|-------|-------------|
| SCAA | Available-for-sale at amortized cost (total, consolidated) |
| SCAF | AFS at fair value |
| SCHA | Held-to-maturity at amortized cost |
| SCHF | HTM at fair value |
| SCMV | Securities at market value (composite) |
| SCHTMRES | Allowance for credit losses on HTM debt securities |
| SCRDEBT | Debt securities (separate classification) |
| SCPLEDGE | Pledged securities |
| SCLENT | Securities lent |

**Maturity buckets**

| Field | Description |
|-------|-------------|
| SC1LES | Fixed/floating debt securities remaining maturity ≤ 1 year |
| SCNM3LES | Non-mortgage debt securities ≤ 3 months |
| SCNM3T12 / SCNM1T3 / SCNM3T5 / SCNM5T15 / SCNMOV15 | Non-mortgage by maturity bucket |
| SCPT3LES / SCPT3T12 / SCPT1T3 / SCPT3T5 / SCPT5T15 / SCPTOV15 | MBS pass-throughs by bucket |
| SCO3YLES / SCOOV3Y | Other mortgage securities ≤ 3 years / > 3 years |

### Income Statement

**Core aggregates (YTD cumulative unless suffixed Q for quarterly)**

| Field | Description |
|-------|-------------|
| INTINC | Total interest income |
| EINTEXP | Total interest expense |
| NIM | Net interest income |
| NIMY | Net interest margin (% of earning assets) |
| NONII | Total non-interest income |
| NONIX | Total non-interest expense |
| ELNATR | Provision for credit losses (on loans) |
| IGLSEC | Securities gains and losses (realized) |
| IBEFTAX | Income before taxes & discontinued operations |
| ITAX | Applicable income taxes |
| IBEFXTR | Income before discontinued operations |
| EXTRA | Net discontinued operations |
| NETINC | Net income (after tax, after discontinued) |
| NETINCA | Net income - bank - annualized |
| NOIJ | Net operating income (adjusted, excluding gains/losses) |
| PTAXNETINC | Pre-tax net income operating income |
| NETIMIN / NETINBM | Net income minority interest / bank + minority |

**Interest income by source**

| Field | Description |
|-------|-------------|
| ILNLS | Loan & lease interest income (total) |
| ILNDOM / ILNFOR | Loan income - domestic / foreign |
| ILS | Lease financing interest income |
| ILNLSXA | Tax-exempt loan & lease interest income - annualized |
| ILNMUNIQ | Municipal loan income - quarterly |
| ISC | Total security income |
| ITRADE | Interest income on trading accounts |
| IFREPO | Fed funds sold & reverse repos interest income |
| ICHBAL | Interest income on balances from depository institutions |
| IOTHII | Other interest income |

**Interest expense by source**

| Field | Description |
|-------|-------------|
| EDEP | Total deposit interest expense |
| EDEPDOM / EDEPFOR | Deposit interest expense - domestic / foreign |
| ETRANDEP | Transaction accounts interest expense |
| ESAVDP | Non-transaction savings accounts interest expense |
| EOTHTIMA / EOTHTIME | Interest expense on time CDs ≤ $250K |
| ECD100 / ECD100A | Interest expense on time CDs > $250K |
| EFREPP | Fed funds & repos purchased interest expense |
| EFHLBADV | Advances from FHLB interest expense |
| ESUBND | Subordinated notes interest expense |
| EMTGLS | Mortgage debt interest expense |
| ETTLOTBO | TT&L and other borrowings interest expense |
| EOTHINT | Other interest expense |
| INTEXPY | Interest expense / earning assets ratio |

**Non-interest income breakdown**

| Field | Description |
|-------|-------------|
| IFIDUC | Fiduciary activities income (trust fee income) |
| ISERCHG | Service charges on deposit accounts |
| ISERFEE | Servicing fees |
| IGLTRAD | Trading revenues - total |
| IGLRTEX | Trading account - interest rate |
| IGLFXEX | Trading account - foreign exchange |
| IGLEDEX | Trading account - equity derivative |
| IGLCMEX | Trading account - commodity |
| IGLCREX | Trading revenue - credit exposure |
| ISECZ | Securitization income |
| IINVFEE | Investment banking |
| IINSCOM | Insurance commissions & fees |
| IINSOTH | Insurance commissions & fees - other |
| IINSUND | Insurance underwriting income |
| IVENCAP | Venture capital revenue |
| IOTHFEE | Other fee income |
| IOTNII | Other non-interest income |
| NETGNSLN | Net gains/losses on sales of loans |
| NETGNAST | Net gains/losses on sales of fixed assets |
| NETGNSRE | Net gains/losses on other real estate owned |

**Non-interest expense breakdown**

| Field | Description |
|-------|-------------|
| ESAL | Salaries & employee benefits |
| EPREMAGG | Premises & fixed assets expense |
| EINTGW | Goodwill impairment losses |
| EINTOTH | Amortization & impairment - other intangibles |
| EAMINTAN | Amortization & impairment loss - assets |
| EOTHNINT | All other non-interest expense |

### Credit Quality (220+ fields across multiple families)

**Aggregate credit metrics**

| Field | Description |
|-------|-------------|
| NCLNLS | Non-current loans & leases (90+ PD + non-accrual, total) |
| NCLNLSR | NCLs / gross loans & leases (%) |
| NTLNLS | Net charge-offs - loans & leases total |
| NTLNLSR | Net charge-offs / loans & leases (%) |
| NTLNLSQR | Net charge-offs / loans - quarterly rate |
| LNATRES | Allowance for loan & lease losses (ALLL) |
| LNLSNTV | Net loans & leases / assets |
| LNRESNCR | Loan loss reserve / NCLs coverage |
| NPERF | Non-performing assets / total assets |
| ELNATR | Provision for credit losses (YTD) |
| ELNANTR | Loan loss provision / net charge-offs ratio |

**Net charge-offs by loan type (NT*)** — each has Q (quarterly), R (ratio), QR (quarterly ratio) variants

| Field | Description |
|-------|-------------|
| NTRE | Real estate loan NCOs |
| NTREAG / NTRECONS / NTREMULT / NTRENRES / NTRERES / NTRELOC | RE NCOs by sub-category |
| NTRECNFM / NTRECNOT | 1-4 fam construction / other construction NCOs |
| NTRERSFM / NTRERSF2 | 1-4 fam first / junior lien NCOs |
| NTCI | Commercial loan NCOs |
| NTCINUS | Non-US commercial loan NCOs |
| NTCON | Consumer loan NCOs |
| NTCONOTH | Other consumer NCOs |
| NTCRCD | Credit card NCOs |
| NTAUTO | Auto loan NCOs |
| NTAG | Agricultural loan NCOs |
| NTAGSM | Ag NCOs - small banks |
| NTLS | Lease NCOs |
| NTDEP | Depository institution loan NCOs |
| NTFORGV | Foreign government loan NCOs |
| NTOTHER | All other loan NCOs |
| NTCOMRE | Commercial RE NCOs |
| NTREOFFDOM | RE NCOs - domestic offices |

**Gross charge-offs (DR*)** — mirror structure of NT*

| Field | Description |
|-------|-------------|
| DRLNLS | Gross charge-offs (total) |
| DRRE / DRCI / DRCON / DRCRCD / DRAG / DRAUTO / DRLS / DROTHER | By loan category |
| DREAG / DRRECONS / DRREMULT / DRRENRES / DRRERES / DRRELOC | By RE sub-type |
| DRRECNFM / DRRECNOT / DRRERSFM / DRRERSF2 / DRREFOR | RE construction/lien/foreign |

**Recoveries (CR*)** — mirror structure

| Field | Description |
|-------|-------------|
| CRLNLS | Total recoveries |
| CRRE / CRCI / CRCON / CRCRCD / CRAG / CRAUTO / CRLS / CROTHER | By category |
| CRREAG / CRRECONS / CRREMULT / CRRENRES / CRRERES / CRRELOC | RE sub-types |

**Past due 30-89 days (P3*)**

| Field | Description |
|-------|-------------|
| P3ASSET | 30-89 day P/D assets (total) |
| P3LNLS | 30-89 day P/D loans & leases (total) |
| P3RE / P3CI / P3CON / P3CRCD / P3AG / P3AUTO / P3LS | By loan category |
| P3REAG / P3RECONS / P3REMULT / P3RENRES / P3RERES / P3RELOC | RE sub-types |
| P3RECNFM / P3RECNOT / P3RERSFM / P3RERSF2 / P3REFOR | RE construction/lien/foreign |
| P3RENROW / P3RENROT | Owner-occ / other nonfarm nonres |
| P3SCDEBT | 30-89 day P/D debt securities |
| P3LNSALE | 30-89 day P/D loans held for sale |
| P3OTHLN | 30-89 day P/D all other loans |

**Past due 90+ days (P9*)** — mirror P3* structure

| Field | Description |
|-------|-------------|
| P9ASSET | 90+ day P/D assets (total) |
| P9LNLS / P9RE / P9CI / P9CON / P9CRCD / P9AG / P9AUTO / P9LS | By category |
| P9REAG / P9RECONS / P9REMULT / P9RENRES / P9RERES / P9RELOC | RE sub-types |
| P9SCDEBT / P9LNSALE / P9OTHLN | Debt securities / held-for-sale / other |

**Non-accrual (NA*)** — mirror structure, excludes loans still accruing

| Field | Description |
|-------|-------------|
| NALNLS | Non-accrual loans & leases (total) |
| NAASSET | Non-accrual total assets |
| NARE / NACI / NACON / NACRCD / NAAG / NAAUTO / NALS | By category |
| NAREAG / NARECONS / NAREMULT / NARENRES / NARERES / NARELOC | RE sub-types |
| NASCDEBT | Non-accrual debt securities |
| NALNSALE | Non-accrual L&L held for sale |
| NAOTHLN | Non-accrual all other loans |
| NAGTY / NAGTYPAR | Non-accrual guaranteed loans (total / partially-guaranteed) |
| NAGTYGNM | Non-accrual rebooked GNMA loans |

**Restructured (TDR) loans (RS*, NARS*)**

| Field | Description |
|-------|-------------|
| RSLNLTOT | Restructured loans - total |
| RSLNLS | Restructured loans excluding 1-4 family |
| RSLNREFM | Restructured 1-4 family RE loans |
| RSCI | Restructured C&I |
| RSCONS | Restructured construction |
| RSMULT | Restructured multifamily |
| RSNRES | Restructured nonfarm nonresidential |
| RSOTHER | Restructured all other |
| NARSLNLT | Non-accrual restructured - total |
| NARSLNLS | Non-accrual restructured excl 1-4 family |
| NARSLNFM | Non-accrual restructured 1-4 family |
| NARSCI / NARSCONS / NARSMULT / NARSNRES / NARSOTH | Non-accrual restructured by type |
| P9RSLNLT | 90+ P/D restructured - total |
| P3RSLNLT | 30-89 P/D restructured - total |

### Capital & Regulatory Ratios

**Risk-based capital stack**

| Field | Description |
|-------|-------------|
| EQTOT | Total equity capital ($000s) |
| IDT1CER | Common Equity Tier 1 (CET1) capital ratio (%) |
| RBCT1CER | Common Equity Tier 1 ratio (alternate) |
| RBCT1C | Common equity Tier 1 capital ($000s) |
| RBCT1J | Tier 1 RBC adjusted for ALLL - PCA (%) |
| RBCT1JR | Tier 1 RBC adjusted for ALLL - ratio |
| RBCT1 | Tier 1 RBC - PCA |
| RBCT1W | Tier 1 capital - reported |
| RBCT2 | Tier 2 RBC - PCA |
| RBC | Total risk-based capital - PCA |
| RBCRWAJ | Total RBC ratio - PCA (%) |
| RBC1AAJ | Leverage ratio - PCA (%) |
| RBC1RWAJ | Tier 1 RBC ratio - PCA (%) |
| RB2LNRES | Allowance for L&L included in Tier 2 |
| RBCEQUP | Retained earnings - RBC |
| CT1AJTOT | Total adjustments & deductions to CET1 |
| CT1BADJ | CET1 before adjustments |
| RWAJ | RWA - adjusted - PCA - T1 & CET1 |
| RWAJT | RWA - adjusted - PCA - total RBC |
| CBLRIND | Community Bank Leverage Ratio (CBLR) indicator |

**Key ratios**

| Field | Description |
|-------|-------------|
| ROA | Return on assets (annualized %) |
| ROAQ | Quarterly return on assets |
| ROAPTX | Pretax return on assets |
| ROE | Return on equity (annualized %) |
| ROEQ | Quarterly return on equity |
| ROEINJR | Retained earnings / average bank equity |
| NIMY | Net interest margin (annualized %) |
| NIMYQ | NIM - quarterly |
| EEFFR | Efficiency ratio (%) |
| EEFFQR | Efficiency - quarterly |
| LNLSDEPR | Loans / deposits ratio (%) |
| LNLSNTV | Net loans & leases / assets (%) |
| LNCDT1R | Construction & land dev loans / Tier 1 |
| LNRERT1R | RE loans / Tier 1 |
| LNCIT1R | C&I loans / Tier 1 |
| LNCONT1R | Consumer loans / Tier 1 |
| DEPDASTR | Domestic deposits / assets |
| ERNASTR | Earning assets / total assets |
| INTINCY | Interest income / earning assets |
| INTEXPY | Interest expense / earning assets |
| INTEXPYQ | Cost of funding earning assets - quarterly |

### Off-Balance-Sheet Items

**Unused commitments (UC*)**

| Field | Description |
|-------|-------------|
| UC | Unused commitments (total) |
| UCLN | Unused commitments - total loans |
| UCCOMRE | Unused commitments - commercial RE |
| UCCOMRES / UCCOMREU | Unused com RE secured / unsecured |
| UCCRCD | Unused commitments - credit card lines |
| UCLOC | Unused commitments - home equity lines |
| UCSC | Unused commitments - securities underwriting |
| UCOTHER | Unused commitments - all other |
| UCOVER1 | Unused commits over 1 year (RC-R column A) |
| UCSZAUTO / UCSZCI / UCSZCON / UCSZCRCD / UCSZHEL / UCSZRES / UCSZOTH | Unused commits for securitizations by asset type |

**Standby letters of credit (LOC*)**

| Field | Description |
|-------|-------------|
| LOCCOM | Commercial letters of credit |
| LOCFSB | Financial standby letters of credit |
| LOCFSBK | Financial standby LOC - conveyed |
| LOCPSB | Performance standby letters of credit |
| LOCPSBK | Performance standby LOC - conveyed |
| LOCFPSB | Financial + performance standby LOC |
| LOCFPSBK | Fin & perf standby LOC - conveyed |

**Credit derivatives and guarantees**

| Field | Description |
|-------|-------------|
| NACDIR | Notional amount of credit derivatives |
| CTDERBEN | Credit derivatives (net) - purchased protection |
| CTDERGTY | Credit derivatives (net) - sold protection |
| OBSDIR | Off-balance sheet derivatives |
| OTHOFFBS | All other off-balance sheet liabilities |
| TRREVALSUM | Revaluation gains on off-balance sheet contracts |
| TRREVALD / TRREVALF | Derivative positive value - domestic / foreign |
| TRLREVAL | Trade-derivatives negative values |

**Recourse and credit enhancements**

| Field | Description |
|-------|-------------|
| ASCEOTH / ASCERES | Credit enhancement recourse not securitized - other / residential |
| ASDROTH / ASDRRES | Sold with recourse not securitized |
| ABCUBK / ABCUOTH | Asset-backed unused commitments - related / other |
| ABCXBK / ABCXOTH | Asset-backed credit exposure - related / other |
| ENCEAUTO / ENCECI / ENCECON / ENCEOTH / ENCERES | Credit exposure enhancements by asset type |

### Derivatives (Trading & Non-Trading)

| Field | Description |
|-------|-------------|
| FX | Foreign exchange - total contracts (notional) |
| FXFFC | FX - futures & forward contracts |
| FXNVS | FX - notional value of swaps |
| FXSPOT | Spot FX contracts |
| FXPOC / FXWOC | FX - purchased / written option contracts |
| RT | Interest rate - total contracts |
| RTFFC | IR - futures & forwards |
| RTNVS | IR - swaps |
| RTPOC / RTWOC | IR - purchased / written options |
| OTHFFC / OTHNVS / OTHPOC / OTHWOC | Other (equity, commodity) - by contract type |

### Trading Accounts

| Field | Description |
|-------|-------------|
| TRADE | Trading accounts (assets) |
| TRADEL | Trading liabilities |
| TRFOR | Trading accounts - foreign |
| SCTATFR | Assets held in trading accounts for TFR reporters |
| ITRADE | Interest income on trading accounts |
| IGLTRAD | Trading revenues - total (including IGL sub-components above) |

### Securitization Exposures (SZ*)

| Field | Description |
|-------|-------------|
| SZCRAUTO / SZCRCI / SZCRCON / SZCRCRCD / SZCRHEL / SZCRRES / SZCROTH | Receivables sold and securitized by asset type (auto, C&I, consumer, credit card, HEL, residential, other) |
| SZ30AUTO ... SZ30OTH | 30-89 day past due on securitized loans |
| SZ90AUTO ... SZ90OTH | 90+ day past due on securitized loans |
| SZDRAUTO ... SZDROTH | Charge-offs on securitized loans |
| SZISLAUT ... SZISLOTH | Credit exposure on securitizations |
| SZUCAUTO ... SZUCOTH | Unused commitments for securitizations |
| SZCRCDFE | Outstanding credit card fees in securitized CC |
| SZLNCI / SZLNCON / SZLNCRCD / SZLNHEL / SZLNOTH / SZLNRES | Re-principal securitized assets sold |

### Borrowings (FHLB and Other)

| Field | Description |
|-------|-------------|
| FREPP | Fed funds & repos purchased |
| FFPUR | Federal funds purchased |
| REPOPUR | Repurchase agreements |
| OBOR | Other borrowed funds |
| OTHBOR | Other borrowed money |
| OTHBORF | Other borrowed money - foreign |
| OTHBRF | Other borrowed funds (alternate aggregate) |
| OTHBFHLB | FHLB borrowings - total |
| OTBFH1L | FHLB advances - maturity repricing ≤ 1 year |
| OTBFH1T3 | FHLB advances - 1-3 years |
| OTBFH3T5 | FHLB advances - 3-5 years |
| OTBFHOV5 | FHLB advances - over 5 years |
| OTBFHSTA | FHLB structured advances |
| OTHBFH13 / OTHBFH03 | FHLB borrowings - 1-3 years / over 3 years (legacy) |
| OTHBFH1L | FHLB advances with remaining maturity ≤ 1 year (legacy) |
| OTBOT1L / OTBOT1T3 / OTBOT3T5 / OTBOTOV5 | Other borrowings by repricing maturity |
| OTHBOT1L | Other borrowings remaining maturity ≤ 1 year |
| SUBND | Subordinated notes & debentures |
| SUBLLPF | Subordinated debt + limited-life preferred |
| TTL | Treasury, tax & loan option |
| TTLOTBOR | TT&L + other borrowings |
| MTGLS | Mortgage indebtedness & capitalized leases |

### Fiduciary and Trust Activities

**Aggregates**

| Field | Description |
|-------|-------------|
| TFRA | Total fiduciary and related assets |
| NFAA | Number of fiduciary accounts and related asset accounts |
| TRUST | Trust powers flag |
| TRUSTPWR | Trust power granted codes |
| TREXER | Trust powers exercised |
| TRPOWER | Institution has trust power |

**Account categories by type × managed/non-managed × amount/number**

| Field pattern | Description |
|---------------|-------------|
| TPMA / TPMANUM / TPNMA / TPNMNUM | Personal & agency accounts (managed/non-mgd, amount/num) |
| TEBMA / TEBMANUM / TEBNMA / TEBNMNUM | Employee benefit - defined benefit |
| TECMA / TECMANUM / TECNMA / TECNMNUM | Employee benefit - defined contribution |
| TORMA / TORMANUM / TORNMA / TORNMNUM | Other retirement (IRA/Keogh) |
| TFEMA / TFEMANUM / TFENMA / TFENMNUM | Foundation & endowment |
| TCAMA / TCAMANUM / TCANMA / TCANMNUM | Corporate trust & agency |
| TCSNMA / TCSNMNUM | Custody & safekeeping (non-managed) |
| TIMMA / TIMMANUM / TIMNMA / TIMNMNUM | Investment agency |
| TOFMA / TOFMANUM / TOFNMA / TOFNMNUM | Other fiduciary |
| TRHMA / TRHMANUM / TRHNMA / TRHNMNUM | IRA |
| TMAF / TMAFNUM / TNMAF / TNMNUMF | Foreign offices fiduciary |
| TTMA / TTNANUM / TTNMA / TTNMNUM | Total fiduciary accounts |

**Asset composition in fiduciary accounts** (TPIx = Personal/Inv Agency, TEXX = Employee Benefit, TOXX = Other Managed)

| Field | Description |
|-------|-------------|
| TEI / TENI | Interest-bearing / noninterest-bearing (employee benefit) |
| TESCUS / TESCMUN | US Treas & OB / municipal securities |
| TECPS | Common & preferred stock |
| TEEQF / TEOTHF | Equity / other mutual funds |
| TEMMF | Money market fund |
| TESTO / TEOTHB | Short-term / other bonds |
| TERE / TEREMTG | Real estate / RE mortgages |
| TETRF | Trust funds |
| TEMISC | Miscellaneous assets |
| TEUF | Unregistered funds |
| TMATOT | Total managed assets - employee benefit |
| TOMATOT | Total managed assets - other |
| TPIMATOT | Total managed assets - personal & investment agency |

**Fiduciary income (YTD)**

| Field | Description |
|-------|-------------|
| IFIDUC | Fiduciary activities income (P&L line) |
| TICA | Gross income - corporate trust & agency |
| TICS | Gross income - custody |
| TIEB | Gross income - employee benefit - benefit |
| TIEC | Gross income - employee benefit - contribution |
| TIFE | Gross income - foundation & endowment |
| TIMA | Gross income - investment agency |
| TIP | Gross income - personal & agency |
| TIOR | Gross income - other retirement |
| TIOF | Gross income - other fiduciary |
| TIR | Gross income - related services |
| TITOTF | Total foreign office gross fiduciary |
| TINTRA | Intracompany income fiduciary |
| TETOT | Fiduciary expense - YTD |
| TNI | Net fiduciary income - YTD |
| TNL | Net loss from fiduciary - YTD |

### Other Real Estate Owned (Foreclosed)

| Field | Description |
|-------|-------------|
| ORE | Other real estate owned (total) |
| OREAG | All other RE owned - farmland |
| ORECONS | All other RE owned - construction |
| OREMULT | All other RE owned - multifamily |
| ORENRES | All other RE owned - nonfarm |
| ORERES | All other RE owned - 1-4 family |
| OREOTH | Other real estate owned (separate line) |
| OREOTHF | Other RE owned - foreign |
| OREGNMA | All other RE owned - GNMA loans |
| OREINV | Direct & indirect investments in ORE |

### Small Business / Small Farm Lending

| Field | Description |
|-------|-------------|
| LNCI1 / LNCI2 / LNCI3 / LNCI4 | C&I loans by size bucket (< $100K, $100-$250K, $250K-$1M, < $1M total) |
| LNCI1N / LNCI2N / LNCI3N / LNCI4N | C&I loans by size - number of loans |
| LNRENR1 / LNRENR2 / LNRENR3 / LNRENR4 | Nonfarm nonres RE by size bucket |
| LNRENR1N ... LNRENR4N | Nonfarm nonres RE - number of loans |
| LNREAG1 / LNREAG2 / LNREAG3 / LNREAG4 | RE ag loans by size |
| LNAG1 / LNAG2 / LNAG3 / LNAG4 | Agricultural loans by size |
| NTAGSM | Ag NCOs - small banks |
| CRAGSM / DRAGSM | Ag recoveries / charge-offs - small banks |

### Failure-Specific Fields (/failures endpoint)

| Field | Description |
|-------|-------------|
| FAILDATE | Date of failure |
| FAILYR | Year of failure |
| QBFASSET | Total assets at failure ($000s) |
| QBFDEP | Total deposits at failure ($000s) |
| COST | Estimated loss to DIF ($000s) |
| RESTYPE | Failure vs Assistance |
| RESTYPE1 | Resolution type (P&A Purchase & Assumption, PI Payout Insured, PO Payout, A/A Assisted Acquisition, IDT Insured Deposit Transfer, etc.) |
| SAVR | Insurance fund (DIF, BIF, SAIF, RTC, FSLIC) |
| BIDNAME / BIDCITY / BIDSTATE | Acquiring institution details |
| CHCLASS1 | Charter class at failure |

### Financial Presets (60+ curated subsets)

**Overview**

| Preset | Use Case |
|--------|----------|
| default | Quick overview: ASSET, DEP, NETINC, ROA, ROE, NIMY, ELNATR |
| minimal | Bare essentials: ASSET, DEP, NETINC |

**Balance Sheet**

| Preset | Concept |
|--------|---------|
| balance_sheet | Top-level: ASSET, DEP, EQTOT, SC, LNLSNET, FREPP, OBOR, SUBND, LIAB |
| assets | Asset side detail: cash, SC, loans, trading, premises, intangibles, ORE, earning assets |
| liabilities | Liability side: deposits, FREPP, repos, FHLB, other borrowings, subordinated, trading |
| equity | Full equity stack: common, preferred, surplus, retained, AOCI, dividends, merger changes |

**Income Statement**

| Preset | Concept |
|--------|---------|
| income | Core P&L: INTINC, EINTEXP, NIM, NONII, NONIX, ELNATR, IGLSEC, ITAX, NETINC, NOIJ |
| interest_income | Income by source: loans, leases, securities, trading, fed funds, cash |
| interest_expense | Expense by source: deposits (dom/for), FHLB, repos, sub debt, time CDs |
| noninterest_income | Fee income: fiduciary, service charges, trading, securitization, insurance, gains on sales |
| noninterest_expense | Operating: salaries, premises, goodwill impairment, other |
| income_quarterly | Quarterly income components for run-rate analysis |

**Loans**

| Preset | Concept |
|--------|---------|
| loans | Top-level loan composition |
| loans_re | Full RE breakdown (construction, multifamily, CRE, residential, ag, foreign) |
| loans_commercial | C&I detail (by size tier + foreign) |
| loans_consumer | Credit card, auto, other consumer |
| loans_ag | Agricultural loans (production + ag RE) |
| loans_small_business | Small business loans by size bucket (incl. SB sold) |
| loans_maturity | Loan repricing buckets (1-4 family + other, 6 buckets) |
| loans_other | Leases, foreign govt, muni, depository, other lending |

**Deposits**

| Preset | Concept |
|--------|---------|
| deposits | Standard deposit mix: demand, MMDA, time, uninsured, brokered |
| deposits_detail | Interest-bearing/non vs domestic/foreign + core/volatile |
| deposits_transaction | DDA + transaction by counterparty (IPC, US govt, muni, foreign) |
| deposits_nontransaction | MMDA, savings, time by size + counterparty |
| deposits_maturity | Time deposit repricing buckets (≤3mo to 3+ years) |
| deposits_insurance | Insured/uninsured + accounts by size ($250K threshold) |
| deposits_brokered | Brokered + listing service deposits |
| deposits_foreign | Foreign office deposit detail |

**Securities**

| Preset | Concept |
|--------|---------|
| securities | Top-level mix: UST, agency, muni, MBS, ABS, foreign |
| securities_detail | Full SC breakdown (agency, FNMA, GNMA, MBS sub-types, ABS, equity, structured) |
| securities_classification | AFS/HTM/trading split + fair value + pledged + lent |
| securities_mbs | Complete MBS decomposition (residential, commercial, pass-through, CMO, private) |
| securities_maturity | Maturity buckets for debt (≤3mo to 15+ years) |

**Capital**

| Preset | Concept |
|--------|---------|
| capital | Standard regulatory capital: equity, Tier 1, Total, Leverage, CET1, dividends |
| capital_basel | Full Basel III stack: CET1, Tier 1, Tier 2, RWA, leverage, adjustments |
| capital_dividends | Dividend detail: common/preferred, stock issuance, treasury stock, merger changes |

**Credit Quality**

| Preset | Concept |
|--------|---------|
| credit_quality | Standard: NCLs, NCOs, non-accrual, past-dues, ALLL |
| non_accrual | Non-accrual by loan type (RE, C&I, consumer, CC, ag, auto) |
| non_accrual_re | RE non-accrual detail (construction, multifamily, 1-4 family, foreign) |
| past_due_30 | 30-89 day past due by loan type |
| past_due_30_re | 30-89 day past due RE detail |
| past_due_90 | 90+ day past due by loan type |
| past_due_90_re | 90+ day past due RE detail |
| charge_offs | Gross charge-offs by loan type |
| recoveries | Recoveries by loan type |
| net_charge_offs | Net charge-offs by loan type |
| past_due_detail | Combined P3 + P9 + NA across major loan categories |
| restructured | TDR loans (current, 30-89, 90+, non-accrual) by type |
| reserves | Full ALLL structure including HTM securities reserves |

**CRE Concentration**

| Preset | Concept |
|--------|---------|
| cre | Full CRE exposure vs capital (construction, multifamily, nonres, residential, ag + Tier 1 ratios) |

**Off-Balance Sheet**

| Preset | Concept |
|--------|---------|
| off_balance_sheet | Aggregate: unused commits, standby LOCs, derivatives notional, other OBS |
| unused_commitments | Full UC breakdown (loans, CRE, credit card, home equity, securitization) |
| standby_letters | Commercial LOC + financial/performance standby (issued + conveyed) |

**Trading & Derivatives**

| Preset | Concept |
|--------|---------|
| trading | Trading accounts + trading revenue (rate, FX, equity, commodity, credit) |
| derivatives | FX, interest rate, other contracts (futures, swaps, options) + credit derivatives + revaluation |

**Securitization**

| Preset | Concept |
|--------|---------|
| securitization | Sold/securitized balances + past due + charge-offs by asset type (auto, C&I, consumer, CC, HEL, residential) |

**Borrowings**

| Preset | Concept |
|--------|---------|
| borrowings | Complete borrowing mix: fed funds, repos, FHLB by maturity, other, subordinated, TT&L |
| fhlb_advances | FHLB advances by maturity bucket + structured advances |

**Fiduciary / Trust**

| Preset | Concept |
|--------|---------|
| fiduciary | Fiduciary account types (personal, employee benefit, foundation, corporate trust, custody, investment agency, IRA) |
| fiduciary_income | Fee income by fiduciary service type + total expense and net |

**Cash & Earning Assets**

| Preset | Concept |
|--------|---------|
| cash | Cash composition (interest-bearing, due from Fed, due from banks, currency, items in process) |
| earning_assets | Earning asset mix (securities + loans + trading + interest-bearing cash) |

**Other Assets**

| Preset | Concept |
|--------|---------|
| premises_intangibles | Premises + goodwill + mortgage servicing + credit card relationships + other intangibles |
| ore | Other real estate owned by type (farmland, construction, multifamily, 1-4 family, foreign) |
| other_assets | OA + bank-owned life insurance (general/separate/hybrid) + investments in subs |

**Ratios**

| Preset | Concept |
|--------|---------|
| ratios | Standard ratio set: ROA, ROE, NIM, efficiency, NCL, loan/dep, CET1, leverage, funding cost |
| ratios_profitability | Full profitability (YTD + quarterly for ROA, ROE, NIM, efficiency, pretax) |
| ratios_credit | Credit quality ratios (NCL, NCO, past-due, non-accrual, reserve coverage) |
| ratios_capital | Regulatory capital ratios only |
| ratios_funding | Funding cost, yield on earning assets, loan/deposit, earning asset share |

**Interest Rate Risk / Securities Stress**

| Preset | Concept |
|--------|---------|
| unrealized_securities | HTM/AFS amortized vs fair value (SCHA/SCHF and SCAA/SCAF) - the metric that blew up SVB. Implied unrealized loss = amortized cost - fair value |
| securities_fair_value | Compact HTM/AFS book vs fair value for time series analysis |
| interest_rate_risk | Full repricing gap: loans (LN*RS*, LNOT*), securities (SC*), and deposits (CD*) by maturity bucket |

**Institutional Metadata / Structure**

| Preset | Concept |
|--------|---------|
| institution_profile | Holding company lineage + demographics: NAMEHCR, RSSDHCR, STALPHCR, CITYHCR, PARCERT, HCTONE/MULT/NONE, NUMEMP, DENOVO, NEWINST, MINORITY, MNRTYCDE, SPECGRP, CB, BKCLASS, FED, REGAGNT |
| supervisory | Chartering + regulatory metadata: BKCLASS, CLCODE, FED, REGAGNT, CHRTAGNT, FDICDBS/SUPV, OCCDIST, STCHRTR/FEDCHRTR/FORCHRTR, INSDIF/BIF/SAIF, CONSERVE, CLOSED, FAILED, MUTUAL, TRUST, SUBCHAPS |
| cblr | Community Bank Leverage Ratio (CBLRIND), AVASSETJ, EQTOT, IDT1CER |

**COVID Emergency Programs**

| Preset | Concept |
|--------|---------|
| ppp_mmlf | PPP loan balances (PPPLNBAL, PPPLNNUM, PPPLNPLG), MMLF usage (MMLFBAL, AVMMLF), PPP liquidity facility advances by maturity |

**Specialty / Structural**

| Preset | Concept |
|--------|---------|
| mortgage_servicing | MSR detail: INTANMSR, MSRECE, MSRESFCL, MSRNRECE, LNSERV, LNLSSALE, MTGLS |
| foreign_offices | Foreign office exposure: ASSETFOR, LIABFOR, DEPFOR, DEPIFOR/NIFOR, LNCIFOR, LNREFOR, EDEPFOR, TRFOR, OREOTHF |
| size_buckets | Asset size bucket flags (SZ25, SZ100, SZ1BP, SZ10BP, SZ250BP, etc.) for distribution analysis |
| staff_size | Employee count + compensation: NUMEMP, ESAL, EEFFR, NONIX |
| own_securitizations | Bank-originated (own) securitizations of C&I, credit card, HEL with past-due + charge-off + recoveries |
| npa | Composite non-performing assets: NALNLS, P9ASSET, ORE, NPERF, LNRESNCR, NCLNLSR |
| charge_offs_quarterly | Quarterly NCO and recovery rates (Q-suffix) for all loan types (run-rate analysis) |

For any field not in a preset, pass `--fields FIELD1,FIELD2,...` directly. The argparse `--preset` flag exposes all preset names as typed choices. Full RISVIEW schema with descriptions: `https://api.fdic.gov/banks/docs/risview_properties.yaml`

### Notable CERT Numbers

| CERT | Institution | Notes |
|------|-------------|-------|
| 628 | JPMorgan Chase Bank NA | Largest US bank ($3.75T assets) |
| 3510 | Bank of America NA | #2 ($2.64T) |
| 7213 | Citibank NA | #3 ($1.84T) |
| 3511 | Wells Fargo Bank NA | #4 ($1.82T) |
| 33124 | Goldman Sachs Bank USA | Bank sub (Marcus, Apple Card, institutional) |
| 34221 | Morgan Stanley Private Bank NA | Bank sub (wealth management) |
| 6548 | U.S. Bank NA | #5 ($676B) |
| 4297 | Capital One NA | Major consumer bank |
| 9846 | Truist Bank | Regional ($540B) |
| 6384 | PNC Bank NA | Regional ($568B) |
| 24735 | Silicon Valley Bank | Failed 3/10/2023 (ACTIVE:0) |
| 59017 | First Republic Bank | Failed 5/1/2023 (ACTIVE:0) |
| 57053 | Signature Bank | Failed 3/12/2023 (ACTIVE:0) |


## CLI Recipes

All recipe commands support `--json` for structured output. Direct endpoint queries also support `--export csv|json`.

### Direct Endpoint Queries

```bash
# Institutions: search by state, charter, size
python fdic.py institutions --filters 'STALP:NY AND ACTIVE:1' --limit 10
python fdic.py institutions --filters 'STALP:NY AND ACTIVE:1' --fields CERT,NAME,ASSET,DEP --sort-by ASSET --limit 10 --json
python fdic.py institutions --search 'NAME:JPMorgan' --limit 5 --json
python fdic.py institutions --filters 'ACTIVE:1 AND ASSET:[10000000 TO *]' --sort-by ASSET --sort-order DESC --limit 50 --export csv

# Financials: quarterly Call Report data by CERT + REPDTE
python fdic.py financials --filters 'CERT:628' --fields CERT,REPDTE,ASSET,DEP,NETINC,ROA,ROE --sort-by REPDTE --limit 8 --json
python fdic.py financials --filters 'CERT:628' --sort-by REPDTE --limit 20 --export csv
python fdic.py financials --filters 'REPDTE:20251231 AND ASSET:[10000000 TO *]' --fields CERT,REPDTE,ASSET,NIMY,ROA --sort-by ASSET --limit 50 --json

# Failures: all failures or filtered by year/state
python fdic.py failures --sort-by FAILDATE --sort-order DESC --limit 20 --json
python fdic.py failures --filters 'FAILYR:2023' --fields NAME,FAILDATE,QBFASSET,QBFDEP,COST,RESTYPE1 --json
python fdic.py failures --agg-by FAILYR --agg-sum-fields QBFASSET,COST --agg-limit 50 --json

# Summary: industry aggregates by year
python fdic.py summary --filters 'YEAR:2024' --fields STNAME,YEAR,NETINC,ASSET --json
python fdic.py summary --filters 'STNAME:"United States"' --sort-by YEAR --sort-order DESC --limit 50 --json

# Locations: branch network with lat/lng
python fdic.py locations --filters 'CERT:628 AND STALP:CA' --fields NAME,OFFNAME,CITY,LATITUDE,LONGITUDE --limit 100 --json

# SOD: Summary of Deposits (branch-level annual)
python fdic.py sod --filters 'CERT:628 AND YEAR:2023' --fields NAMEFULL,STALPBR,CITYBR,DEPSUMBR --limit 50 --json

# History: structure change events
python fdic.py history --filters 'CERT:628' --sort-by PROCDATE --sort-order DESC --limit 100 --json
python fdic.py history --search 'INSTNAME:Goldman' --limit 20 --json

# Demographics
python fdic.py demographics --filters 'CERT:628 AND REPDTE:20230630' --json
```

### General Recipes

```bash
# Top banks by total assets (US or by state)
python fdic.py largest-banks
python fdic.py largest-banks --top 20
python fdic.py largest-banks --top 10 --state TX
python fdic.py largest-banks --top 5 --json

# Fuzzy bank name search (returns CERT numbers)
python fdic.py bank-lookup --name "Wells Fargo"
python fdic.py bank-lookup --name "Goldman Sachs" --json
python fdic.py bank-lookup --name "JPMorgan" --limit 5

# Quarterly financial time series for a single bank (60+ presets available)
# Run `python fdic.py bank-financials --help` for the full preset list.

# Overview
python fdic.py bank-financials --cert 628 --quarters 20 --preset default
python fdic.py bank-financials --cert 33124 --quarters 4 --preset minimal --json

# Balance sheet breakdowns
python fdic.py bank-financials --cert 628 --quarters 40 --preset balance_sheet
python fdic.py bank-financials --cert 628 --quarters 20 --preset assets
python fdic.py bank-financials --cert 628 --quarters 20 --preset liabilities
python fdic.py bank-financials --cert 628 --quarters 20 --preset equity

# Income statement
python fdic.py bank-financials --cert 628 --quarters 20 --preset income --json
python fdic.py bank-financials --cert 628 --quarters 20 --preset interest_income
python fdic.py bank-financials --cert 628 --quarters 20 --preset interest_expense
python fdic.py bank-financials --cert 628 --quarters 20 --preset noninterest_income
python fdic.py bank-financials --cert 628 --quarters 20 --preset noninterest_expense
python fdic.py bank-financials --cert 628 --quarters 8 --preset income_quarterly

# Loan composition (multiple granularity levels)
python fdic.py bank-financials --cert 628 --quarters 20 --preset loans
python fdic.py bank-financials --cert 628 --quarters 20 --preset loans_re
python fdic.py bank-financials --cert 628 --quarters 20 --preset loans_commercial
python fdic.py bank-financials --cert 628 --quarters 20 --preset loans_consumer
python fdic.py bank-financials --cert 628 --quarters 20 --preset loans_ag
python fdic.py bank-financials --cert 628 --quarters 20 --preset loans_small_business
python fdic.py bank-financials --cert 628 --quarters 20 --preset loans_maturity

# Deposits
python fdic.py bank-financials --cert 628 --quarters 20 --preset deposits
python fdic.py bank-financials --cert 628 --quarters 20 --preset deposits_detail
python fdic.py bank-financials --cert 628 --quarters 20 --preset deposits_transaction
python fdic.py bank-financials --cert 628 --quarters 20 --preset deposits_nontransaction
python fdic.py bank-financials --cert 628 --quarters 20 --preset deposits_maturity
python fdic.py bank-financials --cert 628 --quarters 20 --preset deposits_insurance
python fdic.py bank-financials --cert 628 --quarters 20 --preset deposits_brokered
python fdic.py bank-financials --cert 628 --quarters 20 --preset deposits_foreign

# Securities
python fdic.py bank-financials --cert 628 --quarters 20 --preset securities
python fdic.py bank-financials --cert 628 --quarters 20 --preset securities_detail
python fdic.py bank-financials --cert 628 --quarters 20 --preset securities_classification
python fdic.py bank-financials --cert 628 --quarters 20 --preset securities_mbs
python fdic.py bank-financials --cert 628 --quarters 20 --preset securities_maturity

# Capital
python fdic.py bank-financials --cert 628 --quarters 20 --preset capital
python fdic.py bank-financials --cert 628 --quarters 20 --preset capital_basel
python fdic.py bank-financials --cert 628 --quarters 20 --preset capital_dividends

# Credit quality (detailed by loan type)
python fdic.py bank-financials --cert 628 --quarters 20 --preset credit_quality
python fdic.py bank-financials --cert 628 --quarters 12 --preset non_accrual
python fdic.py bank-financials --cert 628 --quarters 12 --preset non_accrual_re
python fdic.py bank-financials --cert 628 --quarters 12 --preset past_due_30
python fdic.py bank-financials --cert 628 --quarters 12 --preset past_due_90
python fdic.py bank-financials --cert 628 --quarters 12 --preset past_due_30_re
python fdic.py bank-financials --cert 628 --quarters 12 --preset past_due_90_re
python fdic.py bank-financials --cert 628 --quarters 12 --preset charge_offs
python fdic.py bank-financials --cert 628 --quarters 12 --preset recoveries
python fdic.py bank-financials --cert 628 --quarters 12 --preset net_charge_offs
python fdic.py bank-financials --cert 628 --quarters 12 --preset past_due_detail
python fdic.py bank-financials --cert 628 --quarters 12 --preset restructured
python fdic.py bank-financials --cert 628 --quarters 12 --preset reserves

# CRE concentration
python fdic.py bank-financials --cert 628 --quarters 20 --preset cre

# Off-balance sheet
python fdic.py bank-financials --cert 628 --quarters 20 --preset off_balance_sheet
python fdic.py bank-financials --cert 628 --quarters 20 --preset unused_commitments
python fdic.py bank-financials --cert 628 --quarters 20 --preset standby_letters

# Trading and derivatives
python fdic.py bank-financials --cert 628 --quarters 20 --preset trading
python fdic.py bank-financials --cert 628 --quarters 20 --preset derivatives

# Securitization
python fdic.py bank-financials --cert 628 --quarters 20 --preset securitization

# Borrowings
python fdic.py bank-financials --cert 628 --quarters 20 --preset borrowings
python fdic.py bank-financials --cert 628 --quarters 20 --preset fhlb_advances

# Fiduciary/Trust (for banks with trust powers)
python fdic.py bank-financials --cert 628 --quarters 20 --preset fiduciary
python fdic.py bank-financials --cert 628 --quarters 20 --preset fiduciary_income

# Other assets
python fdic.py bank-financials --cert 628 --quarters 20 --preset cash
python fdic.py bank-financials --cert 628 --quarters 20 --preset earning_assets
python fdic.py bank-financials --cert 628 --quarters 20 --preset premises_intangibles
python fdic.py bank-financials --cert 628 --quarters 20 --preset ore
python fdic.py bank-financials --cert 628 --quarters 20 --preset other_assets

# Ratios (specialized)
python fdic.py bank-financials --cert 628 --quarters 20 --preset ratios
python fdic.py bank-financials --cert 628 --quarters 20 --preset ratios_profitability
python fdic.py bank-financials --cert 628 --quarters 20 --preset ratios_credit
python fdic.py bank-financials --cert 628 --quarters 20 --preset ratios_capital
python fdic.py bank-financials --cert 628 --quarters 20 --preset ratios_funding

# Recent failures
python fdic.py recent-failures
python fdic.py recent-failures --top 25
python fdic.py recent-failures --top 10 --json

# Failures aggregated by year
python fdic.py failures-by-year
python fdic.py failures-by-year --json

# State banking summary for a year
python fdic.py state-summary
python fdic.py state-summary --year 2024
python fdic.py state-summary --year 2023 --json

# All branch locations for a bank
python fdic.py branches --cert 628
python fdic.py branches --cert 628 --json

# Structure change history (mergers, acquisitions, name changes)
python fdic.py bank-history --cert 628
python fdic.py bank-history --cert 628 --json

# SOD deposit rankings by year/state
python fdic.py deposit-rankings
python fdic.py deposit-rankings --year 2024
python fdic.py deposit-rankings --year 2023 --state CA
python fdic.py deposit-rankings --year 2023 --state CA --json

# Community banks by state
python fdic.py community-banks
python fdic.py community-banks --state TX
python fdic.py community-banks --state TX --json

# Show all field presets for all endpoints
python fdic.py field-catalog
```

### Deposit & Funding Recipes

```bash
# Granular deposit composition: demand, MMDA, time, uninsured, brokered
python fdic.py deposit-mix --cert 628
python fdic.py deposit-mix --cert 628 --quarters 20
python fdic.py deposit-mix --cert 628 --quarters 20 --json

# Uninsured deposit concentration screen
python fdic.py uninsured-screen
python fdic.py uninsured-screen --min-assets 10000000
python fdic.py uninsured-screen --min-assets 1000000 --json

# System-wide deposit trends (from /summary, 1934-present)
python fdic.py system-deposits
python fdic.py system-deposits --years 20
python fdic.py system-deposits --years 40 --json

# Funding cost comparison across banks
python fdic.py funding-costs
python fdic.py funding-costs --certs '628,3510,7213,3511,33124'
python fdic.py funding-costs --certs '628,3510,7213,3511,33124' --json

# Geographic deposit market share
python fdic.py geo-deposits --state CA
python fdic.py geo-deposits --year 2023 --state CA
python fdic.py geo-deposits --year 2023 --state CA --json
```

### Credit & System Health Recipes

```bash
# System health: assets, deposits, income, provisions from 1934
python fdic.py system-health
python fdic.py system-health --json

# Failure waves: count + total assets + DIF cost by year
python fdic.py failure-waves
python fdic.py failure-waves --json

# Credit cycle: NCL rates, provisions, past-dues across large banks
python fdic.py credit-cycle
python fdic.py credit-cycle --min-assets 10000000
python fdic.py credit-cycle --min-assets 10000000 --repdte 20251231
python fdic.py credit-cycle --min-assets 10000000 --repdte 20251231 --json

# NIM regime across top banks
python fdic.py nim-regime
python fdic.py nim-regime --top 50
python fdic.py nim-regime --top 50 --repdte 20251231
python fdic.py nim-regime --top 50 --repdte 20251231 --json

# Capital ratio distribution (sorted weakest first)
python fdic.py capital-distribution
python fdic.py capital-distribution --min-assets 1000000
python fdic.py capital-distribution --min-assets 1000000 --repdte 20251231
python fdic.py capital-distribution --min-assets 1000000 --repdte 20251231 --json
```

### Balance Sheet & Loan Recipes

```bash
# CRE concentration screen
python fdic.py cre-screen
python fdic.py cre-screen --min-assets 1000000
python fdic.py cre-screen --min-assets 1000000 --repdte 20251231
python fdic.py cre-screen --min-assets 1000000 --repdte 20251231 --json

# Loan growth decomposition time series
python fdic.py loan-growth --cert 33124
python fdic.py loan-growth --cert 33124 --quarters 40
python fdic.py loan-growth --cert 33124 --quarters 40 --json

# Reserve adequacy: reserves vs NCLs vs past-dues
python fdic.py reserve-adequacy
python fdic.py reserve-adequacy --min-assets 10000000
python fdic.py reserve-adequacy --min-assets 10000000 --repdte 20251231
python fdic.py reserve-adequacy --min-assets 10000000 --repdte 20251231 --json

# Securities portfolio composition (single bank or top banks by size)
python fdic.py securities-portfolio --cert 628
python fdic.py securities-portfolio --cert 628 --quarters 20
python fdic.py securities-portfolio --cert 628 --quarters 20 --json
python fdic.py securities-portfolio --quarters 20 --json

# Multi-bank peer comparison on any preset (any of the 60+ presets works)
python fdic.py peer-comparison --certs '628,3510,7213,3511'
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset default
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset balance_sheet
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset equity
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset income
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset noninterest_income
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset ratios
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset ratios_profitability
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset ratios_credit
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset ratios_funding
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset deposits_detail
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset deposits_insurance
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset loans_re
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset securities_mbs
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset credit_quality
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset non_accrual
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset past_due_detail
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset reserves
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset capital_basel
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset cre
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset off_balance_sheet
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset derivatives
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset trading
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset securitization
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset borrowings
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset fiduciary
python fdic.py peer-comparison --certs '628,3510,7213,3511' --repdte 20251231 --preset ratios --json

# Past-due and non-accrual detail by loan type
python fdic.py past-due-detail --cert 628
python fdic.py past-due-detail --cert 628 --quarters 12
python fdic.py past-due-detail --cert 628 --quarters 12 --json
```

### Rate Risk / Capital / Credit Deep-Dive Recipes

```bash
# HTM unrealized loss screen (SVB-style interest rate risk)
# Reveals implied unrealized loss = SCHA (book) - SCHF (fair value)
python fdic.py htm-stress --min-assets 10000000 --repdte 20251231
python fdic.py htm-stress --min-assets 10000000 --repdte 20251231 --json

# AFS unrealized loss screen (AOCI hit)
python fdic.py afs-stress --min-assets 10000000 --repdte 20251231
python fdic.py afs-stress --min-assets 10000000 --repdte 20251231 --json

# Single-bank securities fair value time series (HTM + AFS + municipal + structured)
python fdic.py securities-fair-value --cert 628 --quarters 20
python fdic.py securities-fair-value --cert 3510 --quarters 20 --json

# Interest rate risk / repricing gap for one bank
# Combines loan (LN*RS*, LNOT*), securities (SC*), and deposit (CD*) maturity buckets
python fdic.py interest-rate-risk --cert 628 --quarters 8
python fdic.py interest-rate-risk --cert 628 --quarters 8 --json

# Community Bank Leverage Ratio opt-in roster (post-2020 simplified capital rule)
python fdic.py cblr-screen --repdte 20251231
python fdic.py cblr-screen --repdte 20251231 --json

# Non-performing asset ratio screen
python fdic.py npf-screen --min-assets 1000000 --repdte 20251231
python fdic.py npf-screen --min-assets 1000000 --repdte 20251231 --json

# Detailed net charge-off waterfall for a single bank (by loan type, YTD + Q)
python fdic.py charge-off-waterfall --cert 4297 --quarters 8
python fdic.py charge-off-waterfall --cert 4297 --quarters 8 --json

# Efficiency ratio distribution (sorted worst first)
python fdic.py efficiency-distribution --min-assets 1000000 --repdte 20251231
python fdic.py efficiency-distribution --min-assets 1000000 --repdte 20251231 --json

# Banks with largest foreign office asset exposure
python fdic.py foreign-exposure --min-foreign 100000 --repdte 20251231
python fdic.py foreign-exposure --min-foreign 100000 --repdte 20251231 --json

# System-wide asset size distribution (count by bucket)
python fdic.py asset-size-distribution --repdte 20251231
python fdic.py asset-size-distribution --repdte 20251231 --json
```

### Institutional Structure / Demographics

```bash
# Holding company lineage + all bank subsidiaries under the same HC
python fdic.py holding-company --cert 628
python fdic.py holding-company --cert 33124 --json

# Roster of all banks under a specific holding company (by name or RSSD ID)
python fdic.py holding-company-roster --hcr 'JPMORGAN CHASE&CO'
python fdic.py holding-company-roster --hcr 1039502 --json

# Newly chartered institutions in a reporting period
python fdic.py new-banks --repdte 20251231
python fdic.py new-banks --repdte 20251231 --json

# De novo banks (DENOVO=1, new charters - not recharters)
python fdic.py de-novo --repdte 20251231
python fdic.py de-novo --repdte 20251231 --json

# Minority Depository Institutions (MDIs)
# MNRTYCDE: 1=Black, 2=Asian, 3=Chinese, 4=Korean, 5=Japanese,
# 6=Indian/Arabic, 7=Hispanic, 8=Multi-racial, 9=Native American
python fdic.py minority-banks --repdte 20251231
python fdic.py minority-banks --repdte 20251231 --json

# Structure change events aggregated by CHANGECODE
# 110/120=acquisition, 211-224=merger, 310/320=consolidation,
# 420/430=relocation, 470=name change, 510+=branch events
python fdic.py structure-changes --start 2020-01-01 --end 2024-12-31
python fdic.py structure-changes --start 2023-01-01 --end 2023-12-31 --json

# M&A activity aggregated by year
python fdic.py mergers-by-year --start-year 2000 --end-year 2025
python fdic.py mergers-by-year --start-year 2020 --end-year 2024 --json

# Bank count + total assets by Federal Reserve district
# 1=Boston, 2=NY, 3=Philadelphia, 4=Cleveland, 5=Richmond,
# 6=Atlanta, 7=Chicago, 8=St. Louis, 9=Minneapolis, 10=KC, 11=Dallas, 12=SF
python fdic.py fed-district-banks --repdte 20251231
python fdic.py fed-district-banks --repdte 20251231 --json
```

### Specialty / Sector Recipes

```bash
# Banking system breakdown by SPECGRP (specialty group)
# 1=International, 2=Agricultural, 3=Credit Card, 4=Commercial Lending,
# 5=Mortgage Lending, 6=Consumer Lending, 7=Other Specialized,
# 8=All Other <$1B, 9=All Other >$1B
python fdic.py specialty-breakdown --repdte 20251231
python fdic.py specialty-breakdown --repdte 20251231 --json

# Agricultural banks (SPECGRP=2) with ag loan + credit-quality detail
python fdic.py ag-banks --min-assets 100000 --repdte 20251231
python fdic.py ag-banks --min-assets 500000 --repdte 20251231 --json

# Credit card monoline banks (SPECGRP=3)
python fdic.py credit-card-banks --repdte 20251231
python fdic.py credit-card-banks --repdte 20251231 --json

# Banks with significant fiduciary / trust activities (IFIDUC threshold)
python fdic.py trust-banks --min-ifiduc 10000 --repdte 20251231
python fdic.py trust-banks --min-ifiduc 10000 --repdte 20251231 --json

# Banks with material mortgage servicing portfolios (INTANMSR threshold)
python fdic.py mortgage-originators --min-msr 10000 --repdte 20251231
python fdic.py mortgage-originators --min-msr 10000 --repdte 20251231 --json

# PPP loan balances outstanding across banks (residual from 2020-2023 program)
python fdic.py ppp-exposure --min-ppp 1000 --repdte 20251231
python fdic.py ppp-exposure --min-ppp 1000 --repdte 20251231 --json

# Comprehensive multi-section bank profile in one command (~200 fields across 11 sections)
# Covers: institution profile, balance sheet, income, deposits, loans, credit quality,
# capital (Basel III), CRE, securities (incl. unrealized), derivatives, ratios
python fdic.py bank-snapshot --cert 628
python fdic.py bank-snapshot --cert 628 --repdte 20251231 --json
```

### Bulk Export

```bash
python fdic.py bulk-export --endpoint institutions --filters 'ACTIVE:1 AND STALP:CA' --format csv
python fdic.py bulk-export --endpoint financials --filters 'REPDTE:20251231' --max-records 5000 --format json
python fdic.py bulk-export --endpoint financials --filters 'REPDTE:20251231' --fields CERT,REPDTE,ASSET,DEP,ROA --format csv
python fdic.py bulk-export --endpoint failures --format csv
python fdic.py bulk-export --endpoint institutions --filters 'ACTIVE:1' --max-records 0 --format json
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv` | Export to CSV file | Endpoint queries |
| `--export json` | Export to JSON file | Endpoint queries |
| `--filters EXPR` | Elasticsearch filter expression | Endpoint queries |
| `--fields F1,F2,...` | Comma-separated field list (UPPERCASE) | Endpoint queries |
| `--sort-by FIELD` | Sort field (UPPERCASE) | Endpoint queries |
| `--sort-order ASC\|DESC` | Sort direction (default: DESC) | Endpoint queries |
| `--limit N` | Max records (max 10,000) | Endpoint queries |
| `--offset N` | Skip N records (pagination) | Endpoint queries |
| `--search TEXT` | Fuzzy text search | institutions, history |
| `--cert N` | FDIC certificate number | Bank-specific recipes |
| `--quarters N` | Number of quarters | Financial time series |
| `--preset NAME` | Field preset name | bank-financials, peer-comparison |
| `--top N` | Number of results | largest-banks, recent-failures, nim-regime |
| `--state XX` | State abbreviation | largest-banks, deposit-rankings, community-banks, geo-deposits |
| `--year YYYY` | Year | state-summary, deposit-rankings, geo-deposits |
| `--certs 'N,N,...'` | Comma-separated CERTs | funding-costs, peer-comparison |
| `--min-assets N` | Minimum assets in $000s | Screen commands |
| `--repdte YYYYMMDD` | Report date | credit-cycle, nim-regime, capital-distribution, cre-screen, reserve-adequacy |
| `--agg-by FIELD` | Aggregate by field | Endpoint queries (financials, summary, failures, history, sod) |
| `--agg-sum-fields F1,F2` | Fields to sum in aggregation | Endpoint queries |
| `--agg-limit N` | Aggregation bucket limit | Endpoint queries |
| `--max-records N` | Max records for bulk export (0=all) | bulk-export |
| `--format csv\|json` | Output format for bulk export | bulk-export |


## Python Recipes

### Direct API via Internal Helpers

```python
from fdic import _get, _get_all, _extract_rows, FINANCIAL_FIELDS, INSTITUTION_FIELDS

# Single bank latest quarter
resp = _get("financials", {
    "filters": "CERT:628",
    "fields": FINANCIAL_FIELDS["default"],
    "sort_by": "REPDTE",
    "sort_order": "DESC",
    "limit": 1,
})
rows, total = _extract_rows(resp)

# All active institutions in a state
resp = _get("institutions", {
    "filters": "STALP:NY AND ACTIVE:1",
    "fields": INSTITUTION_FIELDS["default"],
    "sort_by": "ASSET",
    "sort_order": "DESC",
    "limit": 50,
})
rows, total = _extract_rows(resp)

# Bank financial time series (20 quarters, any of 60+ presets)
for preset in ["default", "balance_sheet", "assets", "liabilities", "equity",
               "income", "interest_income", "interest_expense",
               "noninterest_income", "noninterest_expense",
               "loans", "loans_re", "loans_commercial", "loans_consumer",
               "deposits", "deposits_detail", "deposits_maturity",
               "securities", "securities_detail", "securities_mbs",
               "capital", "capital_basel", "capital_dividends",
               "credit_quality", "non_accrual", "past_due_30", "past_due_90",
               "charge_offs", "recoveries", "net_charge_offs", "restructured", "reserves",
               "cre", "off_balance_sheet", "unused_commitments", "standby_letters",
               "trading", "derivatives", "securitization",
               "borrowings", "fhlb_advances",
               "fiduciary", "fiduciary_income",
               "cash", "earning_assets", "premises_intangibles", "ore", "other_assets",
               "ratios", "ratios_profitability", "ratios_credit", "ratios_capital", "ratios_funding"]:
    resp = _get("financials", {
        "filters": "CERT:628",
        "fields": FINANCIAL_FIELDS[preset],
        "sort_by": "REPDTE",
        "sort_order": "DESC",
        "limit": 20,
    })
    rows, total = _extract_rows(resp)

# Failures in 2023
resp = _get("failures", {
    "filters": "FAILYR:2023",
    "fields": "NAME,FAILDATE,QBFASSET,QBFDEP,COST,RESTYPE1",
    "sort_by": "FAILDATE",
    "sort_order": "DESC",
    "limit": 25,
})
rows, total = _extract_rows(resp)

# Industry aggregates
resp = _get("summary", {
    "filters": 'STNAME:"United States"',
    "fields": "STNAME,YEAR,ASSET,DEP,INTINC,EINTEXP,NIM,NETINC",
    "sort_by": "YEAR",
    "sort_order": "DESC",
    "limit": 50,
})
rows, total = _extract_rows(resp)

# Bulk export: paginate through all active CA banks
all_rows = list(_get_all("institutions", {
    "filters": "ACTIVE:1 AND STALP:CA",
    "fields": "CERT,NAME,ASSET,DEP,ROA",
}, max_records=5000))

# Peer comparison: multiple CERTs, latest quarter
cert_filter = " OR ".join(f"CERT:{c}" for c in [628, 3510, 7213, 3511])
resp = _get("financials", {
    "filters": f"REPDTE:20251231 AND ({cert_filter})",
    "fields": FINANCIAL_FIELDS["ratios"],
    "sort_by": "ASSET",
    "sort_order": "DESC",
    "limit": 20,
})
rows, total = _extract_rows(resp)
```

### Direct API via Requests

```python
import requests

BASE = "https://api.fdic.gov/banks"

def fdic_get(endpoint, filters=None, fields=None, sort_by=None,
             sort_order="DESC", limit=100):
    params = {"limit": limit, "sort_order": sort_order}
    if filters:
        params["filters"] = filters
    if fields:
        params["fields"] = fields
    if sort_by:
        params["sort_by"] = sort_by
    resp = requests.get(f"{BASE}/{endpoint}", params=params)
    data = resp.json()
    rows = [r.get("data", r) for r in data.get("data", [])]
    total = data.get("meta", {}).get("total", 0)
    return rows, total

# Top 20 largest banks
rows, total = fdic_get("institutions",
    filters="ACTIVE:1",
    fields="CERT,NAME,ASSET,DEP,ROA",
    sort_by="ASSET",
    limit=20)

# JPMorgan last 8 quarters
rows, total = fdic_get("financials",
    filters="CERT:628",
    fields="CERT,REPDTE,ASSET,DEP,NETINC,ROA,ROE,NIMY",
    sort_by="REPDTE",
    limit=8)

# Bank failures in 2023
rows, total = fdic_get("failures",
    filters="FAILYR:2023",
    fields="NAME,FAILDATE,QBFASSET,QBFDEP,COST,RESTYPE1",
    sort_by="FAILDATE")

# All active banks in California
rows, total = fdic_get("institutions",
    filters='STALP:CA AND ACTIVE:1',
    fields='CERT,NAME,ASSET,DEP,ROA',
    sort_by='ASSET',
    limit=50)

# Industry summary for a year
rows, total = fdic_get("summary",
    filters='YEAR:2024',
    fields='STNAME,YEAR,ASSET,DEP,NETINC,INTINC,EINTEXP')
```

### Subprocess Wrapper

```python
import subprocess, json

def fdic_query(command, args_str=""):
    cmd = f"python projects/apis/fdic/fdic.py {command} {args_str} --json"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout else None

# Top 20 largest US banks
largest = fdic_query("largest-banks", "--top 20")

# JPMorgan quarterly financials (default preset)
jpm = fdic_query("bank-financials", "--cert 628 --quarters 20 --preset default")

# JPMorgan deposit composition
deposits = fdic_query("deposit-mix", "--cert 628 --quarters 20")

# Recent failures
failures = fdic_query("recent-failures", "--top 25")

# System health (1934-present)
health = fdic_query("system-health")

# Credit cycle indicators
credit = fdic_query("credit-cycle", "--min-assets 10000000 --repdte 20251231")

# CRE concentration screen
cre = fdic_query("cre-screen", "--min-assets 1000000 --repdte 20251231")

# Peer comparison on ratios
peers = fdic_query("peer-comparison",
    "--certs '628,3510,7213,3511' --preset ratios --repdte 20251231")

# Uninsured deposit screen
uninsured = fdic_query("uninsured-screen", "--min-assets 10000000")

# NIM regime
nim = fdic_query("nim-regime", "--top 50 --repdte 20251231")

# Failure waves
waves = fdic_query("failure-waves")

# Capital distribution
capital = fdic_query("capital-distribution", "--min-assets 1000000 --repdte 20251231")

# Loan growth decomposition
loans = fdic_query("loan-growth", "--cert 33124 --quarters 40")

# Reserve adequacy
reserves = fdic_query("reserve-adequacy", "--min-assets 10000000 --repdte 20251231")

# Securities portfolio
securities = fdic_query("securities-portfolio", "--cert 628 --quarters 20")

# Past-due detail
pastdue = fdic_query("past-due-detail", "--cert 628 --quarters 12")

# Funding costs
funding = fdic_query("funding-costs", "--certs '628,3510,7213,3511,33124'")

# HTM/AFS unrealized loss screens (interest rate risk)
htm = fdic_query("htm-stress", "--min-assets 10000000 --repdte 20251231")
afs = fdic_query("afs-stress", "--min-assets 10000000 --repdte 20251231")
sec_fv = fdic_query("securities-fair-value", "--cert 628 --quarters 20")

# Interest rate risk / repricing gap
irr = fdic_query("interest-rate-risk", "--cert 628 --quarters 8")

# Holding company analysis
hc = fdic_query("holding-company", "--cert 33124")
hc_roster = fdic_query("holding-company-roster", "--hcr 1039502")

# Industry structure
mdi = fdic_query("minority-banks", "--repdte 20251231")
new = fdic_query("new-banks", "--repdte 20251231")
denovo = fdic_query("de-novo", "--repdte 20251231")
cblr = fdic_query("cblr-screen", "--repdte 20251231")
structure = fdic_query("structure-changes", "--start 2020-01-01 --end 2024-12-31")
mergers = fdic_query("mergers-by-year", "--start-year 2000 --end-year 2025")
fed_dist = fdic_query("fed-district-banks", "--repdte 20251231")
size_dist = fdic_query("asset-size-distribution", "--repdte 20251231")

# Specialty banking
spec = fdic_query("specialty-breakdown", "--repdte 20251231")
ag = fdic_query("ag-banks", "--min-assets 100000 --repdte 20251231")
cc = fdic_query("credit-card-banks", "--repdte 20251231")
trust = fdic_query("trust-banks", "--min-ifiduc 10000 --repdte 20251231")
msr = fdic_query("mortgage-originators", "--min-msr 10000 --repdte 20251231")
ppp = fdic_query("ppp-exposure", "--min-ppp 1000 --repdte 20251231")
foreign = fdic_query("foreign-exposure", "--min-foreign 100000 --repdte 20251231")

# Comprehensive 11-section bank profile in one call
snapshot = fdic_query("bank-snapshot", "--cert 628")

# Operational / credit distribution
eff = fdic_query("efficiency-distribution", "--min-assets 1000000 --repdte 20251231")
npf = fdic_query("npf-screen", "--min-assets 1000000 --repdte 20251231")
nco = fdic_query("charge-off-waterfall", "--cert 4297 --quarters 8")
```


## Composite Recipes

### Individual Bank Deep Dive

```bash
python fdic.py bank-lookup --name "Goldman Sachs" --json
python fdic.py bank-financials --cert 33124 --quarters 4 --preset default --json
python fdic.py bank-financials --cert 33124 --quarters 20 --preset balance_sheet --json
python fdic.py bank-financials --cert 33124 --quarters 20 --preset credit_quality --json
python fdic.py bank-financials --cert 33124 --quarters 20 --preset deposits --json
python fdic.py bank-financials --cert 33124 --quarters 20 --preset cre --json
python fdic.py bank-history --cert 33124 --json
```

PRISM receives: CERT identification, 4Q overview (assets, deposits, income, ROA, ROE, NIM, provisions), 20Q balance sheet trajectory (asset growth, securities vs loans mix, equity), 20Q credit quality (NCLs by type, past-dues, non-accruals, reserves), 20Q deposit franchise (demand vs MMDA vs time vs uninsured vs brokered), 20Q CRE composition (construction, non-res, multifamily, resi, ag vs capital), corporate lineage and M&A history.

### Banking System Health Check

```bash
python fdic.py system-health --json
python fdic.py credit-cycle --min-assets 10000000 --repdte 20251231 --json
python fdic.py nim-regime --top 50 --repdte 20251231 --json
python fdic.py capital-distribution --min-assets 1000000 --repdte 20251231 --json
python fdic.py failure-waves --json
```

PRISM receives: 90-year industry aggregates (assets, deposits, income, provisions), current credit cycle (NCL rates, past-dues, provisions across large banks), NIM regime (margin, funding cost, ROA/ROE for top 50), capital distribution (Tier 1 ratios sorted weakest first), historical failure counts and asset totals by year.

### Deposit & Funding Analysis

```bash
python fdic.py system-deposits --years 20 --json
python fdic.py uninsured-screen --min-assets 10000000 --json
python fdic.py funding-costs --certs '628,3510,7213,3511,33124' --json
python fdic.py geo-deposits --year 2023 --state CA --json
python fdic.py peer-comparison --certs '628,3510,7213,3511,33124' --preset deposits --json
```

PRISM receives: 20-year system deposit trends (total, composition, NIM, funding costs), uninsured deposit concentrations for large banks (DEPUNA as % of DEP), funding cost comparison for Big 5 (interest expense on deposits, NIM, brokered share), California deposit market share rankings, peer deposit franchise breakdown (demand vs MMDA vs time vs brokered vs uninsured).

### Peer Comparison (Multi-Dimensional)

```bash
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset default --json
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset ratios --json
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset deposits --json
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset credit_quality --json
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset capital --json
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset cre --json
```

PRISM receives: overview (assets, deposits, income, ROA, ROE, NIM), performance ratios (ROA, ROE, NIM, efficiency, NCL rate, Tier 1), deposit franchise (demand, MMDA, time, uninsured, brokered, funding cost), asset quality (NCLs by type, past-dues, non-accruals), capital (equity, Tier 1, leverage, RWA, dividends), CRE (real estate loans by type vs equity and capital).

### CRE Concentration Deep Dive

```bash
python fdic.py cre-screen --min-assets 1000000 --repdte 20251231 --json
python fdic.py bank-financials --cert {flagged_cert} --quarters 20 --preset cre --json
python fdic.py bank-financials --cert {flagged_cert} --quarters 12 --preset past_due --json
python fdic.py bank-financials --cert {flagged_cert} --quarters 12 --preset capital --json
```

PRISM receives: system-wide CRE screen (RE loans by type, equity, Tier 1 for banks >$1B), 20Q CRE composition for flagged bank (construction, non-res, multifamily, resi, ag), past-due progression by loan type, capital adequacy vs CRE exposure.

### Failure Analysis

```bash
python fdic.py failure-waves --json
python fdic.py recent-failures --top 25 --json
python fdic.py bank-financials --cert 24735 --quarters 20 --preset ratios --json
python fdic.py capital-distribution --min-assets 1000000 --repdte 20251231 --json
python fdic.py uninsured-screen --min-assets 10000000 --json
python fdic.py cre-screen --min-assets 1000000 --repdte 20251231 --json
```

PRISM receives: historical failure counts by year (S&L crisis, GFC, 2023 regional), recent failures with resolution details and DIF cost, pre-failure financial trajectory for SVB (CERT 24735), current capital distribution (weakest buffers), uninsured deposit concentrations, CRE concentration screen.

### Credit Cycle Monitor

```bash
python fdic.py credit-cycle --min-assets 10000000 --repdte 20251231 --json
python fdic.py reserve-adequacy --min-assets 10000000 --repdte 20251231 --json
python fdic.py bank-financials --cert 628 --quarters 20 --preset credit_quality --json
python fdic.py bank-financials --cert 3510 --quarters 20 --preset credit_quality --json
```

PRISM receives: system-wide NCL rates, provisions, past-dues for large banks, reserve coverage ratios (allowance vs NCLs vs past-dues), 20Q credit quality time series for JPMorgan and BofA as bellwethers.

### Securities / Rate Shock Stress (SVB-Style Analysis)

```bash
python fdic.py htm-stress --min-assets 10000000 --repdte 20251231 --json
python fdic.py afs-stress --min-assets 10000000 --repdte 20251231 --json
python fdic.py securities-fair-value --cert 628 --quarters 20 --json
python fdic.py securities-fair-value --cert 3510 --quarters 20 --json
python fdic.py interest-rate-risk --cert 628 --quarters 8 --json
```

PRISM receives: cross-sectional HTM and AFS amortized-cost vs fair-value snapshots for large banks (reveals implied unrealized losses as SCHA-SCHF and SCAA-SCAF), 20Q time series of HTM/AFS position and fair value marks for bellwether banks, 8Q repricing gap analysis (loans, deposits, securities by maturity bucket) showing interest rate sensitivity.

### Institutional Structure / Industry Evolution

```bash
python fdic.py holding-company --cert 33124 --json
python fdic.py holding-company-roster --hcr 'JPMORGAN CHASE&CO' --json
python fdic.py new-banks --repdte 20251231 --json
python fdic.py de-novo --repdte 20251231 --json
python fdic.py minority-banks --repdte 20251231 --json
python fdic.py structure-changes --start 2023-01-01 --end 2025-12-31 --json
python fdic.py mergers-by-year --start-year 2000 --end-year 2025 --json
python fdic.py fed-district-banks --repdte 20251231 --json
python fdic.py asset-size-distribution --repdte 20251231 --json
```

PRISM receives: bank-to-holding-company mapping with sibling roster (all subs under the same RSSDHCR), current newly chartered + de novo institutions, full Minority Depository Institution (MDI) roster with minority type code, aggregated structure events by CHANGECODE for policy / M&A wave analysis, 25+ year merger-and-acquisition activity trend, Federal Reserve district-level bank counts and assets, system-wide asset size distribution (count of banks in each tier from <$25M to $250B+).

### Specialty Banking Sectors

```bash
python fdic.py specialty-breakdown --repdte 20251231 --json
python fdic.py ag-banks --min-assets 100000 --repdte 20251231 --json
python fdic.py credit-card-banks --repdte 20251231 --json
python fdic.py trust-banks --min-ifiduc 10000 --repdte 20251231 --json
python fdic.py mortgage-originators --min-msr 10000 --repdte 20251231 --json
python fdic.py ppp-exposure --min-ppp 1000 --repdte 20251231 --json
python fdic.py foreign-exposure --min-foreign 100000 --repdte 20251231 --json
```

PRISM receives: specialty group asset distribution (how many banks specialize in what), agricultural bank roster with ag loan + credit quality detail (NCOs, past-dues, non-accrual on ag book), credit card monoline roster with CC loan composition and NCOs, trust bank roster with fiduciary assets under management + fee income, mortgage originator roster with MSR assets and loans serviced for others, PPP loan residual balances (program ended in 2023 but balances remain), banks with material foreign office exposure.

### Comprehensive Single-Bank Profile

```bash
python fdic.py bank-snapshot --cert 628 --json
python fdic.py bank-snapshot --cert 33124 --repdte 20251231 --json
python fdic.py bank-snapshot --cert 24735 --repdte 20221231 --json
```

PRISM receives: 11-section multi-dimensional profile for a single bank in one command: institution profile (holding company, regulators, demographics), balance sheet, income statement, deposits detail, loans, credit quality, Basel III capital, CRE concentration, securities with unrealized losses, derivatives, key ratios. Automatic latest-REPDTE lookup if date not specified.


## Cross-Source Recipes

### Bank Health + QT Pace

```bash
python projects/apis/fdic/fdic.py credit-cycle --min-assets 10000000 --repdte 20251231 --json
python projects/apis/nyfed/nyfed.py qt-monitor --weeks 26 --json
```

PRISM receives: bank-level credit quality indicators (NCLs, provisions, past-dues) + Fed balance sheet runoff pace. Reserve tightening impact on bank funding.

### Bank Deposits + Overnight Funding

```bash
python projects/apis/fdic/fdic.py funding-costs --certs '628,3510,7213,3511,33124' --json
python projects/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: bank-level deposit costs and NIM + overnight rate complex (SOFR, EFFR, OBFR). Calibrates bank funding costs against prevailing overnight rates.

### Bank System + Weekly H.8

```bash
python projects/apis/fdic/fdic.py system-deposits --years 5 --json
python projects/apis/fred/fred.py series H8B1058NCBCMG --obs 52 --json
```

PRISM receives: quarterly FDIC deposit aggregates + weekly H.8 commercial bank deposits. Higher-frequency signal between quarterly FDIC filings.

### Bank Failures + Policy Expectations

```bash
python projects/apis/fdic/fdic.py recent-failures --top 10 --json
python projects/apis/fdic/fdic.py capital-distribution --min-assets 1000000 --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: recent failure details + capital distribution (weakest banks) + market-implied policy probabilities. Bank-level stress vs market expectations for rate relief.

### Bank CRE + BIS Cross-Border

```bash
python projects/apis/fdic/fdic.py cre-screen --min-assets 1000000 --repdte 20251231 --json
python projects/apis/bis/bis.py lbs --json
```

PRISM receives: US bank CRE concentration + BIS cross-border banking exposures. International transmission channels for CRE stress.

### Bank NIM + Treasury Curve

```bash
python projects/apis/fdic/fdic.py nim-regime --top 50 --repdte 20251231 --json
python projects/apis/treasury/treasury.py get rates --json
```

PRISM receives: bank NIM distribution + Treasury yield curve. Curve shape mapping to bank profitability.

### Bank Deposits + SEC Filings

```bash
python projects/apis/fdic/fdic.py deposit-mix --cert 628 --quarters 20 --json
python projects/apis/sec_edgar/sec_edgar.py filings --cik 0000019617 --form-type 10-K --json
```

PRISM receives: quarterly deposit composition from Call Reports + holding company 10-K narrative. Quantitative + qualitative deposit franchise assessment.


## Setup

1. No API key required
2. `pip install requests`
3. Test: `python fdic.py largest-banks --top 5`
4. Full test: `python fdic.py bank-financials --cert 628 --quarters 4 --preset default`


## Architecture

```
fdic.py
  Constants       BASE, FIELD_CATALOGS (8 endpoints), FINANCIAL_FIELDS (75+ presets
                  covering balance sheet, income, loans, deposits, securities,
                  capital, credit quality, off-balance sheet, trading, derivatives,
                  securitization, borrowings, fiduciary, ratios, plus:
                  unrealized_securities, interest_rate_risk, institution_profile,
                  supervisory, cblr, ppp_mmlf, mortgage_servicing, foreign_offices,
                  size_buckets, staff_size, own_securitizations, npa,
                  charge_offs_quarterly),
                  INSTITUTION_FIELDS (6 presets incl. holding_company, regulatory,
                  demographics), LOCATION_FIELDS, SUMMARY_FIELDS, FAILURE_FIELDS,
                  HISTORY_FIELDS, SOD_FIELDS, DEMOGRAPHICS_FIELDS
  HTTP            _get() single request, _get_all() auto-paginating bulk fetcher
  Extraction      _extract_rows() flattens FDIC response wrapper
  Display         _print_table(), _prompt(), _prompt_fields(), _display_response()
  Endpoints (8)   institutions, locations, financials, summary, failures,
                  history, sod, demographics
  General (11)    largest-banks, bank-lookup, bank-financials, recent-failures,
                  failures-by-year, state-summary, branches, bank-history,
                  deposit-rankings, community-banks, bulk-export
  Deposit (5)     deposit-mix, uninsured-screen, system-deposits,
                  funding-costs, geo-deposits
  Credit (5)      system-health, failure-waves, credit-cycle,
                  nim-regime, capital-distribution
  Balance (6)     cre-screen, loan-growth, reserve-adequacy,
                  securities-portfolio, peer-comparison, past-due-detail
  Rate Risk (10)  htm-stress, afs-stress, securities-fair-value,
                  interest-rate-risk, cblr-screen, npf-screen,
                  charge-off-waterfall, efficiency-distribution,
                  foreign-exposure, asset-size-distribution
  Structure (8)   holding-company, holding-company-roster, new-banks,
                  de-novo, minority-banks, structure-changes,
                  mergers-by-year, fed-district-banks
  Specialty (7)   specialty-breakdown, ag-banks, credit-card-banks,
                  trust-banks, mortgage-originators, ppp-exposure,
                  bank-snapshot (comprehensive 11-section profile)
  Tools (2)       raw-query (interactive only), field-catalog
  Interactive     Full menu-driven CLI (runs without arguments)
  Argparse        60+ subcommands, all with --json
```

API endpoints:
```
/institutions    -> bank demographics, assets, deposits, charter
/financials      -> quarterly Call Report data (2,377 RISVIEW fields)
/failures        -> bank failures with resolution details and DIF cost
/summary         -> industry aggregates by year from 1934
/locations       -> branch locations with lat/lng
/sod             -> Summary of Deposits (branch-level annual)
/history         -> structure change events (mergers, M&A)
/demographics    -> community demographics
```

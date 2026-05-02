#!/usr/bin/env python3
"""
FDIC BankFind Suite API Explorer
================================

Complete programmatic access to every FDIC-insured institution in the United States,
covering the full universe of bank balance sheets, income statements, credit quality,
deposit flows, branch networks, failures, and structural changes from 1934 to present.

This is the canonical dataset used by bank regulators (FDIC, OCC, Fed) and Treasury
officials to monitor the health of the US banking system. The underlying data comes
from Call Reports (FFIEC forms 031/041) filed quarterly by every insured institution.

API Details
-----------
Base URL:   https://api.fdic.gov/banks
Docs:       https://api.fdic.gov/banks/docs/
Swagger:    https://api.fdic.gov/banks/docs/swagger.yaml
Auth:       None required (optional API key registration at https://api.fdic.gov)
Rate Limit: Not formally documented; no key required for moderate usage.
Format:     JSON (default) or CSV via Accept header / format param.
Max Limit:  10,000 records per request; use offset-based pagination for larger pulls.

Endpoints (8 total)
-------------------
/institutions  Financial institution demographics: name, location, charter class,
               total assets, deposits, net income, ROA/ROE, regulator, web address.
               Supports both exact Elasticsearch filters and fuzzy text search.
               ~4,300 active + ~10,000 inactive institutions.

/locations     Branch and office locations for all institutions. Includes full street
               address, city, state, ZIP, latitude/longitude (for mapping), service type
               (full-service, drive-thru, mobile, etc.), and main office flag.
               ~80,000+ active branch records.

/financials    The deepest dataset: quarterly Call Report data from the RISVIEW system.
               2,377 fields covering every line item on a bank's balance sheet, income
               statement, and regulatory schedules. This includes:
                 - Balance sheet: assets, liabilities, equity, securities (HTM/AFS)
                 - Income: NII, non-interest income/expense, provisions, net income
                 - Loans: granular by type (CRE, C&I, consumer, credit card, resi, ag)
                   including 15+ RE sub-categories and size buckets
                 - Credit quality: NCLs, gross charge-offs, recoveries, past-dues
                   (30-89 and 90+), non-accruals, TDRs, reserves - all by loan type
                 - Capital: Basel III - CET1, Tier 1, Tier 2, Total, Leverage, RWA
                 - Ratios: ROA, ROE, NIM, efficiency, NCL rate, loan-to-deposit, etc.
                 - Liquidity: brokered deposits, FHLB borrowings (by maturity), repos
                 - Deposits: transaction/non-transaction, by counterparty, by insurance
                   tier ($250K threshold), maturity buckets, core vs. volatile
                 - Securities: UST, agency, muni, MBS (residential + commercial),
                   ABS, equity, structured products, by AFS/HTM/trading classification
                 - Off-balance-sheet: unused commitments, standby LOCs, credit
                   derivatives, revaluation gains
                 - Trading: trading assets/liabilities, trading revenue (rate, FX,
                   equity, commodity, credit exposure), derivative contracts
                 - Fiduciary: trust accounts by type (personal, employee benefit,
                   foundation, corporate trust, custody, investment agency, IRA),
                   fee income
                 - Securitization: sold/serviced loans, past dues, charge-offs,
                   recoveries, credit exposure, unused commitments by asset type
               Each record keyed by CERT (institution) + REPDTE (quarter end YYYYMMDD).
               History typically goes back 60-80+ quarters per institution.

/summary       Historical aggregate data from 1934 to present, subtotaled by year.
               Industry-level totals for assets, deposits, net income, provisions, etc.
               Filterable by state (STNAME) and institution type (CB_SI: community
               bank vs savings institution). Use for long-run trend analysis of the
               entire banking system or state-level comparisons.

/failures      Every FDIC bank failure from 1934 to present (~4,100+ records).
               Includes institution name, location, failure date, resolution type
               (P&A, payout, assistance), insurance fund (BIF/SAIF/DIF), acquiring
               institution, total deposits/assets at failure, and estimated loss
               to the Deposit Insurance Fund.

/history       Structure change events: mergers, acquisitions, name changes, charter
               conversions, branch openings/closings. Each event has a CHANGECODE
               identifying the type. Supports fuzzy text search. Use to trace an
               institution's corporate lineage or track M&A activity system-wide.

/sod           Summary of Deposits: branch-level deposit data published annually.
               Each record is one branch for one year, with the deposit amount held
               at that branch. Aggregating by CERT gives total institutional deposits;
               slicing by geography reveals deposit market share by city/state/MSA.
               Available from ~1994 to present.

/demographics  Community demographics tied to institution reporting periods.
               Relatively sparse; primarily useful when cross-referenced with
               CERT and REPDTE from the financials endpoint.

Filter Syntax (Elasticsearch Query Strings)
-------------------------------------------
All filter values and field names must be UPPERCASE.

  NAME:"First Bank"                           Exact phrase match
  STALP:IA AND ACTIVE:1                      Boolean AND
  NAME:"First Bank" OR NAME:"Unibank"        Boolean OR
  STNAME:("West Virginia","Delaware")         Multi-value (any of)
  !(STNAME:"Virginia")                        Exclusion (NOT)
  DEP:[50000 TO *]                            Numeric range, inclusive (thousands $)
  DATEUPDT:["2010-01-01" TO "2010-12-31"]     Date range, inclusive
  FAILYR:{2015 TO 2016}                       Date/numeric range, exclusive
  DATEUPDT:[2010-01-01 TO *]                  Open-ended range

Key Identifiers
---------------
CERT    Unique FDIC certificate number. The primary key for any institution.
        Use this across all endpoints to link institution -> financials -> locations -> etc.
REPDTE  Report date in YYYYMMDD format (e.g. 20251231 = Q4 2025).
        Quarter ends: 0331, 0630, 0930, 1231.
UNINUM  FDIC unique number for branches/offices within an institution.

Monetary Units
--------------
All dollar amounts are in THOUSANDS unless otherwise noted.
ASSET:3752662000 means $3.75 TRILLION (3,752,662,000 thousands = $3,752,662,000,000).
This applies to: ASSET, DEP, DEPDOM, NETINC, LNLSNET, EQTOT, SC, INTINC, EINTEXP,
QBFASSET, QBFDEP, COST, and all other monetary fields.

Analytical Use Cases (Treasury / Banking System Monitoring)
-----------------------------------------------------------
- Deposit flow tracking: where are deposits migrating across institutions and geographies?
- Credit condition monitoring: NCL rates, past-dues, provision expense by loan type
- CRE concentration risk: which institutions are over-concentrated in commercial real estate?
- NIM and funding cost dynamics: how is the rate environment affecting bank profitability?
- Capital adequacy: Tier 1 ratios, leverage ratios across the system
- Failure early-warning: historical patterns, current stress indicators
- Industry structure: M&A pace, de novo formation, branch consolidation
- Uninsured deposit concentration: deposit flight risk (the dynamic that killed SVB)

Dependencies
------------
pip install requests

Dual-Mode CLI
-------------
Running without arguments launches the interactive menu.
Running with a subcommand (e.g. `python fdic_demo.py largest-banks --top 10`) runs
non-interactively for scripting and automation.
"""

import argparse
import json
import sys
import time
import os
import csv
import io

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

BASE = "https://api.fdic.gov/banks"

# ── Field presets per endpoint ────────────────────────────────────────────────
#
# Each endpoint has a curated set of field presets for common analytical tasks.
# The /financials endpoint draws from the full RISVIEW schema with 2,377 fields
# covering every line item from the quarterly Call Report (FFIEC 031/041/051).
# Full schema: https://api.fdic.gov/banks/docs/risview_properties.yaml
# Any valid RISVIEW field name can be passed in `fields`; presets are curated
# subsets for common balance sheet, income, credit quality, and off-balance
# sheet workflows.
#
# The RISVIEW field namespace follows a prefix convention:
#   ASSET/DEP/LIAB    Top-level balance sheet ($000s unless noted)
#   LN*               Loans by type (272 fields) - RE, C&I, consumer, ag, etc.
#   DEP*              Deposits by type (93 fields) - demand, MMDA, time, foreign
#   SC*               Securities by type (118 fields) - UST, agency, MBS, muni
#   EQ*               Equity capital components (26 fields)
#   RBC*/IDT1*        Capital ratios (12 fields) - Tier 1, Total, Leverage, CET1
#   INT*/NON*/NET*    Income statement (57 fields)
#   ILN*/ISC*/IFR*/II* Interest income by asset type
#   EDEP*/EFR*/ESAL*/EOTH* Expense categories
#   NC*/NT*           Non-current / Net charge-offs by loan type (144 fields)
#   P3*/P9*           Past-due 30-89 / 90+ by loan type (107 fields)
#   NA*               Non-accrual by loan type (55 fields)
#   DR*               Gross charge-offs by loan type (54 fields)
#   CR*               Loan recoveries by loan type (54 fields)
#   RS*               Restructured loans by type (7 fields)
#   UC*               Unused commitments (16 fields)
#   LOC*              Standby letters of credit (7 fields)
#   SZ*               Securitization exposures (68 fields)
#   FX*/RT*/OTH*      Derivative contracts (30+ fields)
#   TRADE*/TR*        Trading accounts and revenue
#   TC*/TE*/TF*/TI*/T[MOP]* Fiduciary / trust accounts (~150 fields)
#   OTB*/OTHB*        FHLB advances and other borrowings by maturity
#   CR* repricing     Not to be confused with CR* recoveries; see CD* for time
#                     deposit maturity buckets
#   CH*               Cash and balances due
#   ORE*              Other real estate owned (foreclosed)
#   INTAN*            Intangibles (goodwill, servicing rights, other)
#   OA/OALI*          Other assets (incl. bank-owned life insurance)
#   BKPREM            Premises & fixed assets
#
# Field suffix convention:
#   ""     Base dollar value (thousands of USD)
#   "R"    Ratio (%, typically as % of assets or base)
#   "Q"    Quarterly (vs default YTD cumulative)
#   "A"    Annualized
#   "J"    Adjusted (e.g. LNATRESJ includes allocated transfer risk)
#   "FOR"  Foreign offices
#   "DOM"  Domestic offices

INSTITUTION_FIELDS = {
    "default": "CERT,NAME,STALP,CITY,ACTIVE,ASSET,DEP,NETINC,ROE,ROA,BKCLASS,DATEUPDT",
    "full": "CERT,NAME,STALP,STNAME,CITY,COUNTY,ADDRESS,ZIP,ACTIVE,ASSET,DEP,DEPDOM,NETINC,ROE,ROA,BKCLASS,CB,CBSA,OFFICES,OFFDOM,CHARTER_CLASS,REGAGENT,DATEUPDT,RISDATE,WEBADDR",
    "minimal": "CERT,NAME,STALP,ACTIVE,ASSET",
    "holding_company": "CERT,NAME,STALP,ACTIVE,ASSET,NAMEHCR,RSSDHCR,STALPHCR,CITYHCR,PARCERT,CERTCONS,HCTONE,HCTMULT",
    "regulatory": "CERT,NAME,STALP,ACTIVE,ASSET,BKCLASS,CB,CLCODE,FED,REGAGNT,CHRTAGNT,FDICDBS,FDICSUPV,OCCDIST,STCHRTR,FEDCHRTR,FORCHRTR,INSDIF,INSBIF,INSSAIF,CONSERVE,CLOSED,FAILED,MUTUAL,TRUST,SUBCHAPS",
    "demographics": "CERT,NAME,STALP,STNAME,CITY,ASSET,CBSA,CBSA_NAME,MSA,MSA_NAME,CSA,METRO,MICRO,COUNTY,ZIP,MINORITY,MNRTYCDE,SPECGRP,SPECGRPDESC,CB,OFFICES,OFFDOM,NUMEMP",
}

LOCATION_FIELDS = {
    "default": "CERT,NAME,UNINUM,OFFNAME,SERVTYPE_DESC,CITY,STALP,ZIP,MAINOFF",
    "full": "CERT,NAME,UNINUM,OFFNAME,OFFNUM,SERVTYPE,SERVTYPE_DESC,ADDRESS,CITY,STALP,STNAME,ZIP,COUNTY,LATITUDE,LONGITUDE,MAINOFF,BKCLASS,RUNDATE,ESTYMD",
    "minimal": "CERT,NAME,CITY,STALP,MAINOFF",
}

# ── FINANCIAL_FIELDS: 40+ curated presets covering the full RISVIEW universe ──
# Every field below has been verified to exist in the current risview_properties.yaml
# schema. Presets are grouped by analytical theme: overview, balance sheet, income
# statement, loans, deposits, securities, capital, credit quality, CRE, off-balance
# sheet, trading/derivatives, securitization, borrowings, fiduciary, and ratios.
FINANCIAL_FIELDS = {
    # === OVERVIEW ===
    "default": "CERT,REPDTE,ASSET,DEP,NETINC,ROA,ROE,NIMY,ELNATR",
    "minimal": "CERT,REPDTE,ASSET,DEP,NETINC",

    # === BALANCE SHEET ===
    "balance_sheet": "CERT,REPDTE,ASSET,DEP,DEPDOM,DEPFOR,EQTOT,SC,LNLSNET,FREPP,OBOR,SUBND,LIAB,LIABEQ",
    "assets": "CERT,REPDTE,ASSET,CHBAL,CHFRB,SC,LNLSNET,LNLSGR,TRADE,BKPREM,INTAN,ORE,OA,AOA,ERNAST,ASSTLT",
    "liabilities": "CERT,REPDTE,LIAB,DEP,DEPI,DEPNI,FREPP,REPOPUR,OBOR,OTHBFHLB,OTHBOR,TRADEL,SUBND,SUBLLPF,ALLOTHL",
    "equity": "CERT,REPDTE,EQTOT,EQCS,EQPP,EQSUR,EQUPTOT,EQUP,EQCCOMPI,EQCTRSTX,EQOTHCC,EQCONSUB,EQCDIV,EQCDIVC,EQCDIVP,EQNWCERT",

    # === INCOME STATEMENT ===
    "income": "CERT,REPDTE,INTINC,EINTEXP,NIM,NONII,NONIX,ELNATR,IGLSEC,ITAX,IBEFTAX,EXTRA,NETINC,NOIJ,PTAXNETINC",
    "interest_income": "CERT,REPDTE,INTINC,ILNLS,ILNDOM,ILNFOR,ILS,ISC,ITRADE,IFREPO,ICHBAL,IOTHII,NIM",
    "interest_expense": "CERT,REPDTE,EINTEXP,EDEP,EDEPDOM,EDEPFOR,EFREPP,EFHLBADV,ESUBND,ETRANDEP,ESAVDP,EOTHTIME,EOTHINT,EMTGLS,INTEXPY",
    "noninterest_income": "CERT,REPDTE,NONII,IFIDUC,ISERCHG,ISERFEE,IGLTRAD,ISECZ,IINVFEE,IINSCOM,IINSUND,IVENCAP,IOTHFEE,IOTNII,NETGNSLN,NETGNAST,NETGNSRE",
    "noninterest_expense": "CERT,REPDTE,NONIX,ESAL,EPREMAGG,EINTGW,EINTOTH,EAMINTAN,EOTHNINT",
    "income_quarterly": "CERT,REPDTE,INTINQ,EINTXQ,NIMQ,NONIIQ,NONIXQ,ELNATQ,IGLSECQ,ITAXQ,NOIQ,NETINCQ,PTAXNETINCQ",

    # === LOAN COMPOSITION ===
    "loans": "CERT,REPDTE,LNLSNET,LNLSGR,LNRE,LNCI,LNCON,LNCRCD,LNCONOTH,LNAG,LNMUNI,LS,LNATRES,NCLNLS,UNINC",
    "loans_re": "CERT,REPDTE,LNRE,LNRECONS,LNRECNFM,LNRECNOT,LNREMULT,LNRENRES,LNRENROW,LNRENROT,LNRERES,LNRERSFM,LNRERSF2,LNRELOC,LNREAG,LNREFOR,LNCOMRE",
    "loans_commercial": "CERT,REPDTE,LNCI,LNCI1,LNCI2,LNCI3,LNCI4,LNCINUS,LNCIFOR,LNNDEPD,LNOTCI,LNCOMRE,LNDEP,LNDEPCB",
    "loans_consumer": "CERT,REPDTE,LNCON,LNCRCD,LNAUTO,LNCONOTH,LNCONORP,LNCONRP,LNCRCDRP",
    "loans_ag": "CERT,REPDTE,LNAG,LNREAG,LNAG1,LNAG2,LNAG3,LNAG4,LNAGFOR",
    "loans_small_business": "CERT,REPDTE,LNCI1,LNCI2,LNCI3,LNCI4,LNRENR1,LNRENR2,LNRENR3,LNRENR4,LNAG1,LNAG2,LNAG3,LNAG4,LNSB",
    "loans_maturity": "CERT,REPDTE,LNRS3LES,LNRS3T12,LNRS1T3,LNRS3T5,LNRS5T15,LNRSOV15,LNOT3LES,LNOT3T12,LNOT1T3,LNOT3T5,LNOT5T15,LNOTOV15",
    "loans_other": "CERT,REPDTE,LNFG,LNMUNI,LNDEPAC,LNACOTH,LNOTHER,LNPLEDGE,LNLSSALE,LNSERV,LSALNLS",

    # === DEPOSITS ===
    "deposits": "CERT,REPDTE,DEP,DEPDOM,DEPFOR,DDT,NTRSMMDA,NTRTMLG,NTRSOTH,DEPUNA,BRO,EDEPDOM,COREDEP",
    "deposits_detail": "CERT,REPDTE,DEP,DEPI,DEPIDOM,DEPIFOR,DEPNI,DEPNIDOM,DEPNIFOR,DEPDOM,DEPFOR,COREDEP,VOLIAB,IRAKEOGH",
    "deposits_transaction": "CERT,REPDTE,TRN,DDT,TRNIPC,TRNIPCOC,TRNUSGOV,TRNMUNI,TRNCBO,TRNFC,TRNFG,TRNNIA",
    "deposits_nontransaction": "CERT,REPDTE,NTR,NTRSMMDA,NTRSOTH,NTRTIME,NTRTMLG,NTRTMLGJ,NTRTMMED,NTRCDSM,NTRIPC,NTRUSGOV,NTRMUNI,NTRCOMOT,NTRFC",
    "deposits_maturity": "CERT,REPDTE,CD3LES,CD3LESS,CD3T12,CD3T12S,CD1T3,CD1T3S,CDOV3,CDOV3S",
    "deposits_insurance": "CERT,REPDTE,DEPINS,DEPUNA,DEPUNINS,DEPLGAMT,DEPLGB,DEPSMAMT,DEPSMB,ESTINS",
    "deposits_brokered": "CERT,REPDTE,BRO,BROINS,BROINSLG,DEPLSNB",
    "deposits_foreign": "CERT,REPDTE,DEPFOR,DEPIFOR,DEPNIFOR,DEPFBKF,DEPFGOVF,DEPIPCCF,DEPIPCF,DEPUSBKF,DEPUSMF,EDEPFOR",

    # === SECURITIES ===
    "securities": "CERT,REPDTE,SC,SCUST,SCUSO,SCAGE,SCMUNI,SCMTGBK,SCABS,SCEQ,SCFORD,SCDOMO",
    "securities_detail": "CERT,REPDTE,SC,SCUST,SCUSO,SCAGE,SCAOT,SCGTY,SCGNM,SCFMN,SCCOL,SCMUNI,SCMTGBK,SCCMMB,SCCMPT,SCCMOS,SCRMBPI,SCABS,SCEQ,SCEQFV,SCFORD,SCDOMO,SCSFP",
    "securities_classification": "CERT,REPDTE,SC,SCAA,SCAF,SCHA,SCHF,SCMV,SCPLEDGE,SCLENT,SCHTMRES,SCRDEBT",
    "securities_mbs": "CERT,REPDTE,SCMTGBK,SCCMMB,SCCMPT,SCCMOS,SCCMOG,SCCPTG,SCRMBPI,SCCOL,SCGTY,SCFMN,SCGNM",
    "securities_maturity": "CERT,REPDTE,SC1LES,SCNM3LES,SCNM3T12,SCNM1T3,SCNM3T5,SCNM5T15,SCNMOV15,SCPT3LES,SCPT3T12,SCPT1T3,SCPT3T5,SCPT5T15,SCPTOV15,SCO3YLES,SCOOV3Y",

    # === CAPITAL ===
    "capital": "CERT,REPDTE,EQTOT,EQPP,EQCS,EQSUR,EQUPTOT,EQCCOMPI,IDT1CER,RBCT1J,RBCT1,RBCT2,RBCRWAJ,RBC1AAJ,EQCDIV,RWAJT",
    "capital_basel": "CERT,REPDTE,RBCT1C,RBCT1CER,RBCT1J,RBCT1JR,RBCT1W,RBCT1,RBCT2,RBCRWAJ,RBC1AAJ,RWAJT,RWAJ,CT1AJTOT,CT1BADJ,RB2LNRES",
    "capital_dividends": "CERT,REPDTE,EQCDIV,EQCDIVC,EQCDIVP,EQCDIVQ,EQCDIVNTINC,EQCSTKRX,EQCTRSTX,EQCMRG,EQCREST,EQCFCTA",

    # === CREDIT QUALITY ===
    "credit_quality": "CERT,REPDTE,NCLNLS,NTLNLS,NTRE,NTCI,NTCON,NTCRCD,NALNLS,P3ASSET,P9ASSET,LNATRES,LNLSNTV,NPERF,ELNATR",
    "non_accrual": "CERT,REPDTE,NALNLS,NAASSET,NARE,NACI,NACON,NACRCD,NAAG,NAAUTO,NADEP,NAFG,NALS,NASCDEBT,NAOTHLN,NARSLNLT",
    "non_accrual_re": "CERT,REPDTE,NARE,NAREAG,NARECONS,NARECNFM,NARECNOT,NAREMULT,NARENRES,NARENROW,NARENROT,NARERES,NARERSFM,NARERSF2,NARELOC,NAREFOR",
    "past_due_30": "CERT,REPDTE,P3ASSET,P3LNLS,P3RE,P3CI,P3CON,P3CRCD,P3AG,P3AUTO,P3LS,P3SCDEBT,P3OTHLN,P3LNSALE,P3RSLNLT",
    "past_due_30_re": "CERT,REPDTE,P3RE,P3REAG,P3RECONS,P3RECNFM,P3RECNOT,P3REMULT,P3RENRES,P3RENROW,P3RENROT,P3RERES,P3RERSFM,P3RERSF2,P3RELOC,P3REFOR",
    "past_due_90": "CERT,REPDTE,P9ASSET,P9LNLS,P9RE,P9CI,P9CON,P9CRCD,P9AG,P9AUTO,P9LS,P9SCDEBT,P9OTHLN,P9LNSALE,P9RSLNLT",
    "past_due_90_re": "CERT,REPDTE,P9RE,P9REAG,P9RECONS,P9RECNFM,P9RECNOT,P9REMULT,P9RENRES,P9RENROW,P9RENROT,P9RERES,P9RERSFM,P9RERSF2,P9RELOC,P9REFOR",
    "charge_offs": "CERT,REPDTE,DRLNLS,DRRE,DRCI,DRCON,DRCRCD,DRAG,DRAUTO,DRLS,DROTHER,DRREAG,DRRECONS,DRRENRES,DRREMULT,DRRERES,DRRELOC",
    "recoveries": "CERT,REPDTE,CRLNLS,CRRE,CRCI,CRCON,CRCRCD,CRAG,CRAUTO,CRLS,CROTHER,CRREAG,CRRECONS,CRRENRES,CRREMULT,CRRERES,CRRELOC",
    "net_charge_offs": "CERT,REPDTE,NTLNLS,NTRE,NTCI,NTCON,NTCRCD,NTAG,NTAUTO,NTLS,NTOTHER,NTREAG,NTRECONS,NTRENRES,NTREMULT,NTRERES,NTRELOC",
    "past_due_detail": "CERT,REPDTE,P3ASSET,P9ASSET,NALNLS,P3RE,P9RE,NARE,P3CI,P9CI,NACI,P3CON,P9CON,NACON,P3CRCD,P9CRCD,NACRCD,P3AG,P9AG,NAAG",
    "restructured": "CERT,REPDTE,RSLNLTOT,RSCI,RSCONS,RSMULT,RSNRES,RSLNREFM,RSOTHER,RSLNLS,NARSLNLT,NARSCI,NARSCONS,NARSMULT,NARSNRES,NARSLNFM,P9RSLNLT,P3RSLNLT",
    "reserves": "CERT,REPDTE,LNATRES,LNATRESJ,LNLSRES,LNRESRE,LNRESNCR,SCHTMRES,RB2LNRES,ELNATR,ELNANTR,ELNLOS",

    # === CRE CONCENTRATION ===
    "cre": "CERT,REPDTE,LNRE,LNRECONS,LNRENRES,LNRENROT,LNRENROW,LNREMULT,LNRERES,LNRERSFM,LNRERSF2,LNRELOC,LNREAG,LNCOMRE,ASSET,EQTOT,IDT1CER,LNCDT1R,LNRERT1R",

    # === OFF-BALANCE SHEET ===
    "off_balance_sheet": "CERT,REPDTE,UC,UCLN,UCCOMRE,UCCRCD,UCLOC,UCSC,UCOTHER,LOCCOM,LOCFSB,LOCPSB,LOCFPSB,OBSDIR,NACDIR,OTHOFFBS,TRREVALSUM",
    "unused_commitments": "CERT,REPDTE,UC,UCLN,UCCOMRE,UCCOMRES,UCCOMREU,UCCRCD,UCLOC,UCSC,UCOTHER,UCOVER1,UCSZAUTO,UCSZCI,UCSZCON,UCSZCRCD,UCSZHEL,UCSZRES,UCSZOTH",
    "standby_letters": "CERT,REPDTE,LOCCOM,LOCFSB,LOCFSBK,LOCPSB,LOCPSBK,LOCFPSB,LOCFPSBK",

    # === TRADING AND DERIVATIVES ===
    "trading": "CERT,REPDTE,TRADE,TRADEL,TRFOR,SCTATFR,ITRADE,IGLTRAD,IGLRTEX,IGLFXEX,IGLEDEX,IGLCMEX,IGLCREX",
    "derivatives": "CERT,REPDTE,FX,FXFFC,FXNVS,FXSPOT,FXPOC,FXWOC,RT,RTFFC,RTNVS,RTPOC,RTWOC,OTHFFC,OTHNVS,OTHPOC,OTHWOC,CTDERBEN,CTDERGTY,NACDIR,TRREVALSUM,TRLREVAL",

    # === SECURITIZATION ===
    "securitization": "CERT,REPDTE,SZCRAUTO,SZCRCI,SZCRCON,SZCRCRCD,SZCRHEL,SZCRRES,SZCROTH,SZCRCDFE,SZ30AUTO,SZ30CI,SZ30CON,SZ30CRCD,SZ30HEL,SZ30RES,SZ90AUTO,SZ90CI,SZ90CON,SZ90CRCD,SZ90HEL,SZ90RES",

    # === BORROWINGS ===
    "borrowings": "CERT,REPDTE,FFPUR,FREPP,FREPO,REPOPUR,OBOR,OTHBOR,OTHBRF,OTHBFHLB,OTBFH1L,OTBFH1T3,OTBFH3T5,OTBFHOV5,OTBFHSTA,OTBOT1L,OTBOT1T3,OTBOT3T5,OTBOTOV5,SUBND,SUBLLPF,TTL,TTLOTBOR",
    "fhlb_advances": "CERT,REPDTE,OTHBFHLB,OTBFH1L,OTBFH1T3,OTBFH3T5,OTBFHOV5,OTBFHSTA,OTHBFH03,OTHBFH13,OTHBFH1L",

    # === FIDUCIARY / TRUST ===
    "fiduciary": "CERT,REPDTE,TFRA,NFAA,TPMA,TEBMA,TEBNMA,TFEMA,TCAMA,TCSNMA,TIMMA,TIMNMA,TOFMA,TORMA,TRHMA,TMAF,TTMA,TTNMA",
    "fiduciary_income": "CERT,REPDTE,IFIDUC,TNI,TETOT,TICA,TICS,TIEB,TIEC,TIFE,TIMA,TIOR,TIP,TIR,TIOF,TITOTF,TINTRA",

    # === CASH AND EARNING ASSETS ===
    "cash": "CERT,REPDTE,CHBAL,CHBALI,CHBALNI,CHFRB,CHCOIN,CHUS,CHNUS,CHCIC,CHITEM",
    "earning_assets": "CERT,REPDTE,ERNAST,ASSET,ERNASTR,SC,LNLSNET,TRADE,CHBALI,ASSTLT",

    # === OTHER ASSETS ===
    "premises_intangibles": "CERT,REPDTE,BKPREM,INTAN,INTANGW,INTANGCC,INTANMSR,INTANOTH",
    "ore": "CERT,REPDTE,ORE,OREAG,ORECONS,OREMULT,ORENRES,ORERES,OREOTH,OREOTHF,OREGNMA,OREINV",
    "other_assets": "CERT,REPDTE,OA,AOA,OAIENC,OALIFINS,OALIFGEN,OALIFSEP,OALIFHYB,INVSUB,INVSUORE",

    # === RATIOS ===
    "ratios": "CERT,REPDTE,ROA,ROAQ,ROE,ROEQ,NIMY,NIMYQ,EEFFR,NTLNLSR,NCLNLSR,LNLSDEPR,LNLSNTV,IDT1CER,RBCRWAJ,RBC1AAJ,INTEXPY,INTINCY",
    "ratios_profitability": "CERT,REPDTE,ROA,ROAQ,ROAPTX,ROAPTXQ,ROE,ROEQ,NIMY,NIMYQ,EEFFR,EEFFQR,NOIJY,NOIJYQ,PTAXNETINCR",
    "ratios_credit": "CERT,REPDTE,NCLNLSR,NTLNLSR,P3ASSETR,P9ASSETR,NAASSETR,LNRESNCR,LNLSNTV,NPERF",
    "ratios_capital": "CERT,REPDTE,IDT1CER,RBCT1JR,RBCRWAJ,RBC1AAJ,EQV",
    "ratios_funding": "CERT,REPDTE,LNLSDEPR,INTEXPY,INTEXPYQ,INTINCY,INTINCYQ,ERNASTR,DEPDASTR",

    # === UNREALIZED SECURITIES (HTM vs AFS amortized vs fair value) ===
    # Implied unrealized loss = amortized cost - fair value
    # SCAA vs SCAF = AFS portfolio, SCHA vs SCHF = HTM portfolio (this is the
    # metric that blew up SVB - HTM bonds marked at amortized cost but with
    # massive unrealized losses at fair value).
    "unrealized_securities": "CERT,REPDTE,ASSET,EQTOT,SC,SCAA,SCAF,SCHA,SCHF,SCMV,SCMUNIAA,SCMUNIAF,SCMUNIHA,SCMUNIHF,SCASPNAF,SCASPNHA,SCSNHAA,SCSNHAF,SCHTMRES",
    "securities_fair_value": "CERT,REPDTE,SC,SCAA,SCAF,SCHA,SCHF,SCMV,SCAFR,SCHAR,ASSET,EQTOT",

    # === INTEREST RATE RISK (repricing gap across loans, deposits, securities) ===
    # Combines maturity/repricing buckets from loans (LN*RS* / LNOT*),
    # securities (SC*), and deposits (CD*) to assess interest rate sensitivity.
    "interest_rate_risk": "CERT,REPDTE,ASSET,LNRS3LES,LNRS3T12,LNRS1T3,LNRS3T5,LNRS5T15,LNRSOV15,LNOT3LES,LNOT3T12,LNOT1T3,LNOT3T5,LNOT5T15,LNOTOV15,SC1LES,SCNM3LES,SCNM3T12,SCNM1T3,SCNM3T5,SCNM5T15,SCNMOV15,CD3LES,CD3LESS,CD3T12,CD3T12S,CD1T3,CD1T3S,CDOV3,CDOV3S",

    # === COVID EMERGENCY PROGRAMS (PPP, MMLF) ===
    # Paycheck Protection Program (PPP) balances, MMLF usage.
    # Peaked 2020-2021; some balances still outstanding as of 2026.
    "ppp_mmlf": "CERT,REPDTE,ASSET,PPPLNBAL,PPPLNNUM,PPPLNPLG,PPPLF1LS,PPPLFOV1,AVPPPPLG,MMLFBAL,AVMMLF",

    # === INSTITUTIONAL METADATA AND HOLDING COMPANY ===
    # Holding company lineage, regulator, specialty, de novo/minority flags.
    # Use this to map bank subs to parent HC, identify new banks, etc.
    "institution_profile": "CERT,REPDTE,ASSET,NAME,NAMEHCR,RSSDHCR,RSSDID,STALPHCR,CITYHCR,PARCERT,CERTCONS,HCTONE,HCTMULT,HCTNONE,NUMEMP,DENOVO,NEWINST,MINORITY,MNRTYCDE,SPECGRP,SPECGRPDESC,CB,BKCLASS,CLCODE,MUTUAL,TRUST,TRUSTPWR,FED,REGAGNT,SUBCHAPS,SASSER",
    "supervisory": "CERT,REPDTE,BKCLASS,CB,CLCODE,FED,FEDDESC,REGAGNT,CHRTAGNT,FDICDBS,FDICDBSDESC,FDICSUPV,FDICSUPVDESC,OCCDIST,OCCDISTDESC,STCHRTR,FEDCHRTR,FORCHRTR,INSDIF,INSBIF,INSSAIF,INSAGNT2,INSFDIC,CONSERVE,CLOSED,FAILED,TRUST",

    # === COMMUNITY BANK LEVERAGE RATIO (CBLR) ===
    # Post-2020 simplified capital framework for qualifying community banks
    # (< $10B assets, limited trading, limited off-B/S). CBLR replaces the
    # full risk-based capital calculation with a single leverage ratio.
    "cblr": "CERT,REPDTE,ASSET,AVASSETJ,EQTOT,CBLRIND,IDT1CER,RBC1AAJ,CB,BKCLASS",

    # === MORTGAGE SERVICING AND REAL ESTATE ===
    # Mortgage servicing assets (MSRs), loans held for sale, indebtedness on mortgages.
    "mortgage_servicing": "CERT,REPDTE,ASSET,INTANMSR,INTANMSRR,MSRECE,MSRNRECE,MSRESFCL,LNSERV,LNLSSALE,LNREPP,LIPMTG,LIPNMTG,MTGLS",

    # === FOREIGN OFFICES ===
    # Foreign office deposits, loans, income, liabilities (for international banks).
    "foreign_offices": "CERT,REPDTE,ASSET,ASSETFOR,LIABFOR,OFFFOR,DEPFOR,DEPIFOR,DEPNIFOR,EDEPFOR,CHBALFOR,CHUS,CHNUS,CHUSFBK,CHNUSFBK,LNCIFOR,LNREFOR,LNAGFOR,LNCONFOR,ILNFOR,UNINCFOR,TRFOR,OREOTHF,REPOPURF,REPOSLDF",

    # === ASSET SIZE BUCKETS ===
    # Flags (1/0) for various asset size tiers. Useful for cross-sectional
    # distribution analysis and filtering by institution scale.
    "size_buckets": "CERT,REPDTE,ASSET,SZ25,SZ25T50,SZ50T100,SZ100,SZ100T1B,SZ100T3,SZ100T5,SZ100MP,SZ1BP,SZ1BT3B,SZ1BT5B,SZ1BT10B,SZ3BT10B,SZ5BP,SZ10BP,SZ250BP,S10T250B,SZ300T5,SZ500T1B",

    # === STAFF AND EMPLOYEES ===
    # Number of employees, efficiency ratio, assets per employee.
    "staff_size": "CERT,REPDTE,ASSET,NUMEMP,ESAL,ESALR,EEFFR,EEFFQR,NONIX",

    # === OWNER-ORIGINATED CREDIT / SECURITIZATION EXPOSURE ===
    # Banks that securitized their own loans (CI, credit card, HEL) retain
    # specific risks tracked separately from third-party securitizations.
    "own_securitizations": "CERT,REPDTE,OWNLNCI,OWNLNCRD,OWNLNHEL,OWNCRCI,OWNCRCRD,OWNCRHEL,OWNDRCI,OWNDRCRD,OWNDRHEL,OWNP3CI,OWNP3CRD,OWNP3HEL,OWNP9CI,OWNP9CRD,OWNP9HEL,OWNSCCI,OWNSCCRD,OWNSCHEL",

    # === NON-PERFORMING ASSETS (composite) ===
    # Non-performing assets ratio: 90+ PD + non-accrual loans + ORE.
    "npa": "CERT,REPDTE,ASSET,NALNLS,P9ASSET,P9LNLS,ORE,NPERF,NPERFV,LNATRES,LNRESNCR,NCLNLS,NCLNLSR",

    # === QUARTERLY CHARGE-OFFS AND RECOVERIES (run-rate) ===
    # Quarterly (Q suffix) NCO/recovery rates across loan types for run-rate
    # analysis rather than YTD cumulative.
    "charge_offs_quarterly": "CERT,REPDTE,NTLNLSQ,NTLNLSQR,NTREQ,NTREQR,NTCIQ,NTCIQR,NTCONQ,NTCONQR,NTCRCDQ,NTCRCDQR,NTAGQ,NTAGQR,NTAUTOQ,NTAUTOQR,NTLSQ,NTLSQR,NTOTHQ,NTOTHQR,DRLNLSQ,DRLNLSQR,CRLNLSQ,CRLNLSQR",

    # === BACKWARD-COMPAT (original presets, keep names) ===
    "past_due": "CERT,REPDTE,P3ASSET,P9ASSET,NALNLS,P3RE,P9RE,P3CI,P9CI",
}

SUMMARY_FIELDS = {
    "default": "STNAME,YEAR,INTINC,EINTEXP,NIM,NONII,NONIX,ELNATR,NETINC",
    "full": "STNAME,YEAR,CB_SI,INTINC,EINTEXP,NIM,NONII,NONIX,ELNATR,ITAXR,IGLSEC,ITAX,EXTRA,NETINC,ASSET,DEP",
    "minimal": "YEAR,NETINC,ASSET,DEP",
}

FAILURE_FIELDS = {
    "default": "NAME,CERT,CITYST,FAILDATE,SAVR,RESTYPE,RESTYPE1,QBFDEP,QBFASSET,COST",
    "full": "NAME,CERT,FIN,CITYST,FAILDATE,FAILYR,SAVR,RESTYPE,RESTYPE1,CHCLASS1,QBFDEP,QBFASSET,COST,PSTALP,BIDNAME,BIDCITY,BIDSTATE",
    "minimal": "NAME,CERT,FAILDATE,QBFASSET,COST",
}

HISTORY_FIELDS = {
    "default": "INSTNAME,CERT,PCITY,PSTALP,PZIP5,PROCDATE,ACESSION,CLASS,CHANGECODE",
    "full": "INSTNAME,CERT,PCITY,PSTALP,PZIP5,PROCDATE,ACESSION,CLASS,CHANGECODE,CHARTER_CLASS,REGAGENT,OFF_NAME,OFF_CITY,OFF_STALP,ENTEFDT,EFFDATE,TRUST",
    "minimal": "INSTNAME,CERT,PROCDATE,CHANGECODE",
}

SOD_FIELDS = {
    "default": "CERT,NAMEFULL,YEAR,STALPBR,CITYBR,DEPSUMBR,ASSET,BKCLASS",
    "full": "CERT,NAMEFULL,YEAR,STALPBR,STNAMEBR,CITYBR,ADDRESBR,ZIPBR,CNTYNAMB,DEPSUMBR,DEPDOM,DEPSUM,ASSET,BKCLASS,BRNUM,BRSERTYP,NAMEHCR",
    "minimal": "CERT,NAMEFULL,YEAR,DEPSUMBR",
}

DEMOGRAPHICS_FIELDS = {
    "default": "CERT,REPDTE",
}

FIELD_CATALOGS = {
    "institutions": INSTITUTION_FIELDS,
    "locations": LOCATION_FIELDS,
    "financials": FINANCIAL_FIELDS,
    "summary": SUMMARY_FIELDS,
    "failures": FAILURE_FIELDS,
    "history": HISTORY_FIELDS,
    "sod": SOD_FIELDS,
    "demographics": DEMOGRAPHICS_FIELDS,
}

ENDPOINT_DESCRIPTIONS = {
    "institutions": "Financial institution demographics, location, charter, assets",
    "locations": "Branch/office locations with addresses, lat/lng, service types",
    "financials": "Quarterly Call Report data (balance sheet, income, ratios) - 2,377 RISVIEW fields",
    "summary": "Historical aggregate data from 1934 onward, subtotaled by year",
    "failures": "Bank failures from 1934 to present with resolution details and costs",
    "history": "Structure change events (mergers, name changes, charter conversions)",
    "sod": "Summary of Deposits: branch-level deposit data, annual",
    "demographics": "Community demographics tied to institution reporting",
}


# ── HTTP helpers ──────────────────────────────────────────────────────────────
#
# The FDIC API returns JSON with this structure:
#   {
#     "meta": {"total": N, "parameters": {...}, "index": {...}},
#     "data": [{"data": {field: value, ...}, "score": N}, ...],
#     "totals": {"count": N, ...}
#   }
#
# Each record in "data" is wrapped: the actual fields live inside record["data"].
# The "score" field is for relevance ranking (used by fuzzy search).
# The "meta.total" field gives the total matching count (not just returned count).
# Pagination: use limit (max 10000) + offset to page through results.

def _get(path, params=None, raw_json=False):
    """Single API request. Returns parsed JSON response dict or None on error."""
    url = f"{BASE}/{path}"
    r = requests.get(url, params=params, timeout=30)
    if r.status_code >= 400:
        print(f"  [!] HTTP {r.status_code}: {r.text[:500]}")
        return None
    try:
        data = r.json()
    except Exception:
        print(f"  [!] Non-JSON response: {r.text[:300]}")
        return None
    if raw_json:
        return data
    return data


def _get_all(path, params, max_records=None, progress=True):
    """Auto-paginate through all results, yielding flat data dicts.
    Uses offset-based pagination with limit=10000 per page.
    Prints progress every 5000 records for long-running bulk exports."""
    params = dict(params)
    params.setdefault("limit", 10000)
    offset = int(params.get("offset", 0))
    fetched = 0
    total = None

    while True:
        params["offset"] = offset
        resp = _get(path, params)
        if not resp:
            break
        meta = resp.get("meta", {})
        if total is None:
            total = meta.get("total", 0)
            if progress:
                print(f"  Total records available: {total:,}")
        records = resp.get("data", [])
        if not records:
            break
        for rec in records:
            yield rec.get("data", rec)
            fetched += 1
            if max_records and fetched >= max_records:
                return
        if progress and fetched % 5000 == 0:
            print(f"  ... fetched {fetched:,} / {total:,}")
        offset += len(records)
        if offset >= total:
            break
    if progress and total and total > 0:
        shown = min(fetched, max_records) if max_records else fetched
        print(f"  Fetched {shown:,} records")


def _extract_rows(resp):
    """Pull flat data dicts from FDIC response."""
    if not resp:
        return [], 0
    meta = resp.get("meta", {})
    total = meta.get("total", 0)
    raw = resp.get("data", [])
    rows = []
    for item in raw:
        if isinstance(item, dict) and "data" in item:
            rows.append(item["data"])
        else:
            rows.append(item)
    return rows, total


# ── Display helpers ───────────────────────────────────────────────────────────

def _print_table(rows, max_col_width=30):
    if not rows:
        print("  (no data)")
        return
    headers = list(rows[0].keys())
    col_widths = {h: len(h) for h in headers}
    display_rows = []
    for row in rows:
        dr = {}
        for h in headers:
            val = str(row.get(h, ""))
            if len(val) > max_col_width:
                val = val[:max_col_width - 3] + "..."
            dr[h] = val
            col_widths[h] = max(col_widths[h], len(val))
        display_rows.append(dr)

    header_line = "  " + " | ".join(f"{h:<{col_widths[h]}}" for h in headers)
    sep_line = "  " + "-+-".join("-" * col_widths[h] for h in headers)
    print(header_line)
    print(sep_line)
    for dr in display_rows:
        print("  " + " | ".join(f"{dr[h]:<{col_widths[h]}}" for h in headers))


def _prompt(msg, default=""):
    suffix = f" [{default}]" if default else ""
    val = input(f"  {msg}{suffix}: ").strip()
    return val if val else default


def _prompt_fields(endpoint):
    catalog = FIELD_CATALOGS.get(endpoint, {})
    presets = list(catalog.keys())
    if not presets:
        return _prompt("Fields (comma-separated, UPPERCASE, or empty for all)")

    print(f"  Field presets for /{endpoint}:")
    for i, name in enumerate(presets):
        fields_preview = catalog[name][:70]
        print(f"    {i + 1}. {name:15s} -> {fields_preview}...")
    print(f"    {len(presets) + 1}. custom          -> enter your own field list")
    print(f"    {len(presets) + 2}. none            -> return all fields")

    choice = _prompt("Choose preset number or name", "1")
    if choice.isdigit():
        idx = int(choice) - 1
        if idx < len(presets):
            return catalog[presets[idx]]
        elif idx == len(presets):
            return _prompt("Custom fields (comma-separated, UPPERCASE)")
        else:
            return ""
    elif choice in catalog:
        return catalog[choice]
    else:
        return choice


def _prompt_common_params(endpoint, include_search=False, include_agg=False):
    """Gather the standard params shared across endpoints."""
    params = {}

    filt = _prompt("Filter expression (Elasticsearch syntax, empty for none)")
    if filt:
        params["filters"] = filt

    if include_search:
        search = _prompt("Text search (fuzzy name match, empty to skip)")
        if search:
            params["search"] = search

    fields = _prompt_fields(endpoint)
    if fields:
        params["fields"] = fields

    sort_by = _prompt("Sort by field (UPPERCASE, empty for default)")
    if sort_by:
        params["sort_by"] = sort_by
        sort_order = _prompt("Sort order (ASC/DESC)", "DESC")
        params["sort_order"] = sort_order

    limit = _prompt("Limit (max 10000)", "25")
    params["limit"] = int(limit)

    offset = _prompt("Offset", "0")
    if int(offset) > 0:
        params["offset"] = int(offset)

    if include_agg:
        agg_by = _prompt("Aggregate by field (empty to skip)")
        if agg_by:
            params["agg_by"] = agg_by
            agg_term = _prompt("Aggregation term fields (counted per unique value)")
            if agg_term:
                params["agg_term_fields"] = agg_term
            agg_sum = _prompt("Aggregation sum fields (summed)")
            if agg_sum:
                params["agg_sum_fields"] = agg_sum
            agg_limit = _prompt("Aggregation limit", "10")
            params["agg_limit"] = int(agg_limit)

    return params


def _display_response(resp, endpoint_name):
    if not resp:
        return
    meta = resp.get("meta", {})
    total = meta.get("total", 0)
    rows, _ = _extract_rows(resp)

    print(f"\n  Total matching: {total:,}")
    print(f"  Returned:      {len(rows)}")

    if rows:
        _print_table(rows)

    agg = resp.get("aggregations", resp.get("agg", None))
    if agg:
        print(f"\n  Aggregations:")
        print(json.dumps(agg, indent=4, default=str))

    totals = resp.get("totals", {})
    if totals and len(totals) > 1:
        print(f"\n  Totals:")
        for k, v in totals.items():
            if k != "count":
                print(f"    {k}: {v}")

    _prompt_export(rows, endpoint_name)


def _prompt_export(rows, prefix):
    if not rows:
        return
    export = _prompt("Export? (json/csv/no)", "no")
    if export.lower() in ("no", "n", ""):
        return
    ts = time.strftime("%Y%m%d_%H%M%S")
    if export.lower() == "json":
        fname = f"{prefix}_{ts}.json"
        with open(fname, "w") as f:
            json.dump(rows, f, indent=2, default=str)
        print(f"  Saved {len(rows)} records to {fname}")
    elif export.lower() == "csv":
        fname = f"{prefix}_{ts}.csv"
        if rows:
            headers = list(rows[0].keys())
            with open(fname, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=headers)
                w.writeheader()
                w.writerows(rows)
            print(f"  Saved {len(rows)} records to {fname}")


# ── Interactive commands ──────────────────────────────────────────────────────

def cmd_institutions():
    """GET /institutions -- search FDIC-insured financial institutions.
    curl: curl 'https://api.fdic.gov/banks/institutions?filters=STALP:NY AND ACTIVE:1&fields=CERT,NAME,ASSET,DEP&limit=10'
    Supports both exact filters and fuzzy text search (search param).
    Key fields: CERT (unique ID), NAME, STALP (state), ACTIVE (1/0), ASSET, DEP, NETINC, ROE, ROA,
    BKCLASS (charter class), CB (community bank flag), OFFICES, DATEUPDT."""
    print("\n== Search Institutions ==")
    params = _prompt_common_params("institutions", include_search=True)
    resp = _get("institutions", params)
    _display_response(resp, "institutions")


def cmd_locations():
    """GET /locations -- search institution branch/office locations.
    curl: curl 'https://api.fdic.gov/banks/locations?filters=STALP:CA AND CERT:628&fields=NAME,OFFNAME,CITY,STALP,ZIP&limit=20'
    Key fields: CERT, NAME, UNINUM, OFFNAME, OFFNUM, SERVTYPE (service type code),
    CITY, STALP, ZIP, LATITUDE, LONGITUDE, MAINOFF (1=main office)."""
    print("\n== Search Locations ==")
    params = _prompt_common_params("locations")
    resp = _get("locations", params)
    _display_response(resp, "locations")


def cmd_financials():
    """GET /financials -- quarterly Call Report data (RISVIEW).
    curl: curl 'https://api.fdic.gov/banks/financials?filters=CERT:628&fields=CERT,REPDTE,ASSET,DEP,NETINC,ROA,ROE&sort_by=REPDTE&sort_order=DESC&limit=10'
    This is the deepest dataset with 2,377 fields covering balance sheet, income statement,
    loan composition, capital adequacy, asset quality, and performance ratios.
    Key fields: CERT, REPDTE (report date YYYYMMDD), ASSET, DEP, NETINC, ROA, ROE, NIMY (NIM),
    LNLSNET (net loans), EQTOT (total equity), INTINC, EINTEXP, ELNATR (provision expense)."""
    print("\n== Financial Data (Call Reports) ==")
    params = _prompt_common_params("financials", include_agg=True)
    resp = _get("financials", params)
    _display_response(resp, "financials")


def cmd_summary():
    """GET /summary -- historical aggregate data by year from 1934.
    curl: curl 'https://api.fdic.gov/banks/summary?filters=STNAME:"New York"&fields=YEAR,NETINC,ASSET,DEP&sort_by=YEAR&sort_order=DESC&limit=20'
    Aggregate financial and structure data subtotaled by year. Filter by state, CB/SI type, year range.
    Key fields: STNAME, YEAR, CB_SI, INTINC, EINTEXP, NIM, NONII, NONIX, ELNATR, NETINC, ASSET, DEP."""
    print("\n== Historical Summary (by Year) ==")
    params = _prompt_common_params("summary", include_agg=True)
    resp = _get("summary", params)
    _display_response(resp, "summary")


def cmd_failures():
    """GET /failures -- bank failures from 1934 to present.
    curl: curl 'https://api.fdic.gov/banks/failures?fields=NAME,CERT,CITYST,FAILDATE,QBFASSET,COST&sort_by=FAILDATE&sort_order=DESC&limit=20'
    Key fields: NAME, CERT, CITYST, FAILDATE, FAILYR, SAVR (insurance fund), RESTYPE (Failure/Assistance),
    RESTYPE1 (transaction type), QBFDEP (total deposits at failure), QBFASSET (total assets), COST (est. loss)."""
    print("\n== Bank Failures ==")
    params = _prompt_common_params("failures", include_agg=True)

    total_fields = _prompt("Total fields to sum (e.g. QBFDEP,QBFASSET,COST; empty to skip)")
    if total_fields:
        params["total_fields"] = total_fields
    subtotal_by = _prompt("Subtotal by field (e.g. RESTYPE; empty to skip)")
    if subtotal_by:
        params["subtotal_by"] = subtotal_by

    resp = _get("failures", params)
    _display_response(resp, "failures")


def cmd_history():
    """GET /history -- structure change events (mergers, name changes, etc).
    curl: curl 'https://api.fdic.gov/banks/history?filters=CERT:628&fields=INSTNAME,CERT,PCITY,PSTALP,PROCDATE,CHANGECODE&sort_by=PROCDATE&sort_order=DESC&limit=20'
    Supports fuzzy text search. Key fields: INSTNAME, CERT, PCITY, PSTALP, PZIP5,
    PROCDATE, ACESSION, CLASS, CHANGECODE, EFFDATE."""
    print("\n== Structure Change History ==")
    params = _prompt_common_params("history", include_search=True, include_agg=True)
    resp = _get("history", params)
    _display_response(resp, "history")


def cmd_sod():
    """GET /sod -- Summary of Deposits (branch-level, annual).
    curl: curl 'https://api.fdic.gov/banks/sod?filters=CERT:628&fields=CERT,NAMEFULL,YEAR,STALPBR,CITYBR,DEPSUMBR&sort_by=YEAR&sort_order=DESC&limit=20'
    Branch-level deposit data published annually. Key fields: CERT, NAMEFULL, YEAR,
    STALPBR (branch state), CITYBR, DEPSUMBR (branch deposits), DEPDOM, DEPSUM, ASSET."""
    print("\n== Summary of Deposits ==")
    params = _prompt_common_params("sod", include_agg=True)
    resp = _get("sod", params)
    _display_response(resp, "sod")


def cmd_demographics():
    """GET /demographics -- community demographics for institutions.
    curl: curl 'https://api.fdic.gov/banks/demographics?filters=CERT:628 AND REPDTE:20230630'
    Tied to institution CERT and report date. Relatively sparse dataset."""
    print("\n== Demographics ==")
    params = {}
    filt = _prompt("Filter (e.g. CERT:628 AND REPDTE:20230630)")
    if filt:
        params["filters"] = filt
    resp = _get("demographics", params)
    _display_response(resp, "demographics")


# ── Recipe commands (pre-built queries) ───────────────────────────────────────
#
# Recipes are opinionated, pre-built queries for common analytical tasks.
# They set sensible defaults for filters, fields, sorting, and limits so
# you can get useful output with minimal input. Each recipe maps to one or
# more API calls under the hood.

def cmd_recipe_largest_banks():
    """Top N largest banks by total assets."""
    print("\n== Recipe: Largest Banks ==")
    n = int(_prompt("How many", "25"))
    state = _prompt("Filter by state abbreviation (e.g. NY, or empty for all)")
    filt = "ACTIVE:1"
    if state:
        filt += f' AND STALP:"{state.upper()}"'
    resp = _get("institutions", {
        "filters": filt,
        "fields": "CERT,NAME,STALP,CITY,ASSET,DEP,NETINC,ROE,ROA,OFFICES",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": n,
    })
    _display_response(resp, "largest_banks")


def cmd_recipe_bank_lookup():
    """Look up a bank by name (fuzzy search)."""
    print("\n== Recipe: Bank Lookup ==")
    name = _prompt("Bank name (partial/fuzzy ok)")
    if not name:
        return
    resp = _get("institutions", {
        "search": f"NAME:{name}",
        "fields": "CERT,NAME,STALP,CITY,ACTIVE,ASSET,DEP,BKCLASS,WEBADDR,DATEUPDT",
        "limit": 10,
    })
    _display_response(resp, "bank_lookup")


def cmd_recipe_bank_financials_ts():
    """Pull quarterly financial time series for a single bank."""
    print("\n== Recipe: Bank Financial Time Series ==")
    cert = _prompt("CERT number (use bank lookup to find it)")
    if not cert:
        return
    quarters = int(_prompt("How many quarters", "20"))
    available = ", ".join(sorted(FINANCIAL_FIELDS.keys()))
    print(f"  Available presets: {available}")
    field_choice = _prompt("Preset", "default")
    fields = FINANCIAL_FIELDS.get(field_choice, FINANCIAL_FIELDS["default"])
    resp = _get("financials", {
        "filters": f"CERT:{cert}",
        "fields": fields,
        "sort_by": "REPDTE",
        "sort_order": "DESC",
        "limit": quarters,
    })
    _display_response(resp, f"financials_cert{cert}")


def cmd_recipe_recent_failures():
    """Recent bank failures."""
    print("\n== Recipe: Recent Failures ==")
    n = int(_prompt("How many", "25"))
    resp = _get("failures", {
        "fields": "NAME,CERT,CITYST,FAILDATE,SAVR,RESTYPE1,QBFDEP,QBFASSET,COST",
        "sort_by": "FAILDATE",
        "sort_order": "DESC",
        "limit": n,
    })
    _display_response(resp, "recent_failures")


def cmd_recipe_failures_by_year():
    """Aggregate failure count and total assets by year."""
    print("\n== Recipe: Failures by Year ==")
    resp = _get("failures", {
        "fields": "NAME,CERT,FAILDATE,QBFASSET,COST",
        "sort_by": "FAILDATE",
        "sort_order": "DESC",
        "limit": 1,
        "agg_by": "FAILYR",
        "agg_sum_fields": "QBFASSET,COST",
        "agg_limit": 50,
    })
    if resp:
        meta = resp.get("meta", {})
        print(f"  Total failures in database: {meta.get('total', 'N/A'):,}")
        _display_response(resp, "failures_by_year")


def cmd_recipe_state_banking():
    """Compare banking industry across states (summary endpoint)."""
    print("\n== Recipe: State Banking Summary ==")
    year = _prompt("Year", "2024")
    resp = _get("summary", {
        "filters": f'YEAR:{year}',
        "fields": "STNAME,YEAR,INTINC,NETINC,ASSET,DEP",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 60,
    })
    _display_response(resp, f"state_summary_{year}")


def cmd_recipe_branch_map():
    """Get all branches for a bank (with lat/lng for mapping)."""
    print("\n== Recipe: Branch Locations ==")
    cert = _prompt("CERT number")
    if not cert:
        return
    resp = _get("locations", {
        "filters": f"CERT:{cert}",
        "fields": "CERT,NAME,OFFNAME,ADDRESS,CITY,STALP,ZIP,LATITUDE,LONGITUDE,SERVTYPE_DESC,MAINOFF",
        "sort_by": "STALP",
        "sort_order": "ASC",
        "limit": 10000,
    })
    _display_response(resp, f"branches_cert{cert}")


def cmd_recipe_bank_history():
    """Full structure change history for a bank."""
    print("\n== Recipe: Bank History ==")
    cert = _prompt("CERT number")
    if not cert:
        return
    resp = _get("history", {
        "filters": f"CERT:{cert}",
        "fields": "INSTNAME,CERT,PCITY,PSTALP,PROCDATE,CHANGECODE,EFFDATE",
        "sort_by": "PROCDATE",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"history_cert{cert}")


def cmd_recipe_deposit_rankings():
    """SOD deposit rankings for a given year."""
    print("\n== Recipe: Deposit Rankings ==")
    year = _prompt("Year", "2024")
    state = _prompt("State abbreviation (empty for all)")
    filt = f"YEAR:{year}"
    if state:
        filt += f' AND STALPBR:"{state.upper()}"'
    resp = _get("sod", {
        "filters": filt,
        "fields": "CERT,NAMEFULL,YEAR,STALPBR,CITYBR,DEPSUMBR,ASSET",
        "sort_by": "DEPSUMBR",
        "sort_order": "DESC",
        "limit": 25,
        "agg_by": "CERT",
        "agg_sum_fields": "DEPSUMBR",
        "agg_limit": 25,
    })
    _display_response(resp, f"deposits_{year}")


def cmd_recipe_community_banks():
    """List community banks by state."""
    print("\n== Recipe: Community Banks ==")
    state = _prompt("State abbreviation", "NY")
    resp = _get("institutions", {
        "filters": f'ACTIVE:1 AND CB:1 AND STALP:"{state.upper()}"',
        "fields": "CERT,NAME,CITY,STALP,ASSET,DEP,NETINC,ROA,ROE,OFFICES",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 50,
    })
    _display_response(resp, f"community_banks_{state}")


def cmd_recipe_bulk_export():
    """Bulk export: paginate through all matching records and save to file."""
    print("\n== Recipe: Bulk Export ==")
    endpoint = _prompt("Endpoint (institutions/locations/financials/summary/failures/history/sod)", "institutions")
    filt = _prompt("Filter expression (e.g. ACTIVE:1 AND STALP:NY)")
    fields = _prompt_fields(endpoint)
    max_rec = int(_prompt("Max records to export (0 for all)", "10000"))
    if max_rec == 0:
        max_rec = None

    params = {}
    if filt:
        params["filters"] = filt
    if fields:
        params["fields"] = fields

    all_rows = list(_get_all(endpoint, params, max_records=max_rec))
    if not all_rows:
        print("  No records found.")
        return

    fmt = _prompt("Output format (json/csv)", "csv")
    ts = time.strftime("%Y%m%d_%H%M%S")
    fname = f"{endpoint}_export_{ts}.{fmt}"

    if fmt == "json":
        with open(fname, "w") as f:
            json.dump(all_rows, f, indent=2, default=str)
    else:
        headers = list(all_rows[0].keys())
        with open(fname, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            w.writeheader()
            w.writerows(all_rows)

    print(f"  Exported {len(all_rows)} records to {fname}")


# ── Treasurer recipes ─────────────────────────────────────────────────────────
#
# Oriented toward a global treasurer / deposit franchise manager:
# deposit flows, funding costs, uninsured concentration, liquidity.

def cmd_treasurer_deposit_mix():
    """Granular deposit composition for a bank: demand, MMDA, time, foreign, uninsured, brokered."""
    print("\n== Treasurer: Deposit Mix ==")
    cert = _prompt("CERT number (use bank-lookup to find it)")
    if not cert:
        return
    quarters = int(_prompt("How many quarters", "20"))
    resp = _get("financials", {
        "filters": f"CERT:{cert}",
        "fields": "CERT,REPDTE,DEP,DEPDOM,DEPFOR,DDT,NTRSMMDA,NTRTMLG,NTRSOTH,DEPUNA,BRO,EDEPDOM",
        "sort_by": "REPDTE",
        "sort_order": "DESC",
        "limit": quarters,
    })
    _display_response(resp, f"deposit_mix_cert{cert}")


def cmd_treasurer_uninsured_screen():
    """Screen for banks with highest uninsured deposit concentration.
    This is the metric that flagged SVB, Signature, and First Republic before they failed."""
    print("\n== Treasurer: Uninsured Deposit Concentration Screen ==")
    min_assets = _prompt("Minimum assets ($000s, e.g. 1000000 = $1B)", "1000000")
    resp = _get("financials", {
        "filters": f"REPDTE:20251231 AND ASSET:[{min_assets} TO *]",
        "fields": "CERT,REPDTE,ASSET,DEP,DEPUNA,BRO,EQTOT,IDT1CER",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, "uninsured_screen")


def cmd_treasurer_system_deposits():
    """System-wide deposit trends from the /summary endpoint (1934-present)."""
    print("\n== Treasurer: System Deposit Trends ==")
    years = int(_prompt("How many years back", "20"))
    resp = _get("summary", {
        "filters": 'STNAME:"United States"',
        "fields": "STNAME,YEAR,ASSET,DEP,INTINC,EINTEXP,NIM,NETINC,ELNATR",
        "sort_by": "YEAR",
        "sort_order": "DESC",
        "limit": years * 2,
    })
    _display_response(resp, "system_deposits")


def cmd_treasurer_funding_costs():
    """Compare funding cost (interest expense on deposits) across top banks."""
    print("\n== Treasurer: Funding Cost Comparison ==")
    certs = _prompt("CERT numbers comma-separated (e.g. 628,3510,7213,3511,33124)", "628,3510,7213,3511,33124")
    cert_filter = " OR ".join(f"CERT:{c.strip()}" for c in certs.split(","))
    resp = _get("financials", {
        "filters": f"REPDTE:20251231 AND ({cert_filter})",
        "fields": "CERT,REPDTE,ASSET,DEP,DEPDOM,EDEPDOM,INTINC,EINTEXP,NIMY,BRO,DEPUNA",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 20,
    })
    _display_response(resp, "funding_costs")


def cmd_treasurer_deposit_rankings_geo():
    """Deposit market share by state or MSA -- who dominates deposits where."""
    print("\n== Treasurer: Geographic Deposit Rankings ==")
    year = _prompt("Year", "2023")
    state = _prompt("State abbreviation")
    if not state:
        return
    resp = _get("sod", {
        "filters": f'YEAR:{year} AND STALPBR:"{state.upper()}"',
        "fields": "CERT,NAMEFULL,YEAR,STALPBR,CITYBR,DEPSUMBR,ASSET",
        "sort_by": "DEPSUMBR",
        "sort_order": "DESC",
        "limit": 50,
        "agg_by": "CERT",
        "agg_sum_fields": "DEPSUMBR",
        "agg_limit": 25,
    })
    _display_response(resp, f"geo_deposits_{state}_{year}")


# ── Bank Macro Analyst recipes ────────────────────────────────────────────────
#
# Oriented toward a macro/credit analyst who studies the banking system as a
# leading indicator: credit cycles, failure waves, NIM regimes, capital builds.

def cmd_macro_system_health():
    """Long-run system health: assets, deposits, income, provisions from 1934."""
    print("\n== Macro: System Health (1934-present) ==")
    resp = _get("summary", {
        "filters": 'STNAME:"United States"',
        "fields": "STNAME,YEAR,CB_SI,ASSET,DEP,INTINC,EINTEXP,NIM,NETINC,ELNATR",
        "sort_by": "YEAR",
        "sort_order": "DESC",
        "limit": 200,
    })
    _display_response(resp, "system_health_history")


def cmd_macro_failure_waves():
    """Failure count, total assets, and DIF cost by year -- shows every crisis wave."""
    print("\n== Macro: Failure Waves ==")
    resp = _get("failures", {
        "fields": "NAME,CERT,FAILDATE,QBFASSET,QBFDEP,COST",
        "sort_by": "FAILDATE",
        "sort_order": "DESC",
        "limit": 1,
        "agg_by": "FAILYR",
        "agg_sum_fields": "QBFASSET,QBFDEP,COST",
        "agg_limit": 100,
    })
    if resp:
        meta = resp.get("meta", {})
        print(f"  Total failures in database: {meta.get('total', 'N/A'):,}")
        _display_response(resp, "failure_waves")


def cmd_macro_credit_cycle():
    """Cross-bank credit cycle indicators: NCL rate, provision expense, reserve levels.
    Pulls the latest quarter for all banks above a size threshold."""
    print("\n== Macro: Credit Cycle Indicators ==")
    min_assets = _prompt("Minimum assets ($000s, e.g. 10000000 = $10B)", "10000000")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND ASSET:[{min_assets} TO *]",
        "fields": "CERT,REPDTE,ASSET,NCLNLS,NCLNLSR,NTLNLSR,ELNATR,LNATRES,P3ASSET,P9ASSET,NALNLS,LNLSNTV",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"credit_cycle_{repdte}")


def cmd_macro_nim_regime():
    """NIM across the largest banks -- reveals the rate regime."""
    print("\n== Macro: NIM Regime Across Top Banks ==")
    n = int(_prompt("How many banks (by asset size)", "50"))
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte}",
        "fields": "CERT,REPDTE,ASSET,DEP,NIMY,INTINC,EINTEXP,EDEPDOM,ROA,ROE",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": n,
    })
    _display_response(resp, f"nim_regime_{repdte}")


def cmd_macro_capital_distribution():
    """Capital ratio distribution across the system -- where are the thin and thick buffers."""
    print("\n== Macro: Capital Distribution ==")
    min_assets = _prompt("Minimum assets ($000s, e.g. 1000000 = $1B)", "1000000")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND ASSET:[{min_assets} TO *]",
        "fields": "CERT,REPDTE,ASSET,EQTOT,IDT1CER,RBCRWAJ,RBC1AAJ,EQCDIV,RBCT1J",
        "sort_by": "IDT1CER",
        "sort_order": "ASC",
        "limit": 100,
    })
    _display_response(resp, f"capital_dist_{repdte}")


# ── Balance Sheet Economist recipes ───────────────────────────────────────────
#
# Oriented toward a bank balance sheet economist who studies loan composition,
# CRE risk, reserve adequacy, and structural shifts in bank intermediation.

def cmd_economist_cre_screen():
    """Screen for CRE concentration risk: banks where CRE is high relative to capital.
    Regulators flag institutions where CRE > 300% of total capital."""
    print("\n== Economist: CRE Concentration Screen ==")
    min_assets = _prompt("Minimum assets ($000s, e.g. 1000000 = $1B)", "1000000")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND ASSET:[{min_assets} TO *]",
        "fields": "CERT,REPDTE,ASSET,LNRE,LNRECONS,LNRENRES,LNREMULT,LNRERES,LNREAG,EQTOT,IDT1CER,NCLNLSR",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"cre_screen_{repdte}")


def cmd_economist_loan_growth():
    """Loan composition time series for a bank -- tracks shifts in lending strategy."""
    print("\n== Economist: Loan Growth Decomposition ==")
    cert = _prompt("CERT number")
    if not cert:
        return
    quarters = int(_prompt("How many quarters", "20"))
    resp = _get("financials", {
        "filters": f"CERT:{cert}",
        "fields": "CERT,REPDTE,LNLSNET,LNRE,LNRECONS,LNRENRES,LNREMULT,LNRERES,LNCI,LNCRCD,LNCONOTH,LNREAG",
        "sort_by": "REPDTE",
        "sort_order": "DESC",
        "limit": quarters,
    })
    _display_response(resp, f"loan_growth_cert{cert}")


def cmd_economist_reserve_adequacy():
    """Reserve adequacy: loan loss reserves vs NCLs and past-dues across the system."""
    print("\n== Economist: Reserve Adequacy Screen ==")
    min_assets = _prompt("Minimum assets ($000s, e.g. 10000000 = $10B)", "10000000")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND ASSET:[{min_assets} TO *]",
        "fields": "CERT,REPDTE,ASSET,LNATRES,LNLSNTV,NCLNLS,NCLNLSR,P9ASSET,NALNLS,ELNATR",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"reserve_adequacy_{repdte}")


def cmd_economist_securities_portfolio():
    """Securities portfolio composition: UST, muni, MBS, ABS across top banks."""
    print("\n== Economist: Securities Portfolio Composition ==")
    cert = _prompt("CERT number (or empty for top banks by size)")
    quarters = int(_prompt("How many quarters", "20"))
    if cert:
        filt = f"CERT:{cert}"
    else:
        filt = "REPDTE:20251231"
    resp = _get("financials", {
        "filters": filt,
        "fields": "CERT,REPDTE,ASSET,SC,SCUST,SCUSO,SCMUNI,SCMTGBK,SCABS,DEP,EQTOT",
        "sort_by": "REPDTE" if cert else "ASSET",
        "sort_order": "DESC",
        "limit": quarters if cert else 50,
    })
    _display_response(resp, f"securities_portfolio")


def cmd_economist_peer_comparison():
    """Side-by-side comparison of multiple banks on any financial preset."""
    print("\n== Economist: Peer Comparison ==")
    certs = _prompt("CERT numbers comma-separated (e.g. 628,3510,7213,3511,33124)")
    if not certs:
        return
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    available = ", ".join(sorted(FINANCIAL_FIELDS.keys()))
    print(f"  Available presets: {available}")
    preset = _prompt("Preset", "default")
    fields = FINANCIAL_FIELDS.get(preset, FINANCIAL_FIELDS["default"])
    cert_filter = " OR ".join(f"CERT:{c.strip()}" for c in certs.split(","))
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND ({cert_filter})",
        "fields": fields,
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 20,
    })
    _display_response(resp, f"peer_comparison_{repdte}")


def cmd_economist_past_due_detail():
    """Past-due and non-accrual detail by loan type for a bank."""
    print("\n== Economist: Past Due & Non-Accrual Detail ==")
    cert = _prompt("CERT number")
    if not cert:
        return
    quarters = int(_prompt("How many quarters", "12"))
    resp = _get("financials", {
        "filters": f"CERT:{cert}",
        "fields": "CERT,REPDTE,ASSET,P3ASSET,P9ASSET,NALNLS,P3RE,P9RE,P3CI,P9CI,NCLNLS,LNATRES",
        "sort_by": "REPDTE",
        "sort_order": "DESC",
        "limit": quarters,
    })
    _display_response(resp, f"past_due_cert{cert}")


# ── Interest Rate Risk / Securities Stress recipes ───────────────────────────
#
# HTM/AFS unrealized loss analysis (the dynamic that blew up SVB in 2023),
# repricing gap analysis, fair value marks on securities portfolios.

def cmd_htm_stress():
    """HTM securities unrealized loss screen.
    SCHA = HTM at amortized cost (book), SCHF = HTM at fair value.
    Unrealized loss = SCHA - SCHF (positive = underwater).
    Ratio to equity reveals capital vulnerability."""
    print("\n== HTM Unrealized Loss Screen ==")
    min_assets = _prompt("Minimum assets ($000s, e.g. 10000000 = $10B)", "10000000")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND ASSET:[{min_assets} TO *]",
        "fields": "CERT,REPDTE,ASSET,EQTOT,SC,SCHA,SCHF,SCAA,SCAF,SCMV,SCHTMRES,IDT1CER",
        "sort_by": "SCHA",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"htm_stress_{repdte}")


def cmd_afs_stress():
    """AFS securities unrealized loss screen.
    SCAA = AFS at amortized cost (book), SCAF = AFS at fair value.
    AFS losses flow through AOCI (equity) but not regulatory capital for
    most banks under opt-out rules (opt-in banks do recognize them).
    Still signals interest rate sensitivity."""
    print("\n== AFS Unrealized Loss Screen ==")
    min_assets = _prompt("Minimum assets ($000s, e.g. 10000000 = $10B)", "10000000")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND ASSET:[{min_assets} TO *]",
        "fields": "CERT,REPDTE,ASSET,EQTOT,SC,SCAA,SCAF,SCHA,SCHF,SCMV,EQCCOMPI,IDT1CER",
        "sort_by": "SCAA",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"afs_stress_{repdte}")


def cmd_securities_fair_value():
    """Full securities portfolio fair value mark for one bank.
    Time series of AFS and HTM amortized cost vs fair value, plus
    a composite unrealized loss trajectory over N quarters."""
    print("\n== Securities Fair Value Time Series ==")
    cert = _prompt("CERT number")
    if not cert:
        return
    quarters = int(_prompt("How many quarters", "20"))
    resp = _get("financials", {
        "filters": f"CERT:{cert}",
        "fields": "CERT,REPDTE,ASSET,EQTOT,SC,SCAA,SCAF,SCHA,SCHF,SCMV,SCMUNIAA,SCMUNIAF,SCMUNIHA,SCMUNIHF,EQCCOMPI,SCHTMRES",
        "sort_by": "REPDTE",
        "sort_order": "DESC",
        "limit": quarters,
    })
    _display_response(resp, f"securities_fv_cert{cert}")


def cmd_interest_rate_risk():
    """Repricing gap analysis for a single bank.
    Combines loan repricing (LN*RS*, LNOT*), deposit maturity (CD*),
    and securities maturity (SC*) buckets to assess interest rate
    sensitivity across the balance sheet."""
    print("\n== Interest Rate Risk (Repricing Gap) ==")
    cert = _prompt("CERT number")
    if not cert:
        return
    quarters = int(_prompt("How many quarters", "8"))
    resp = _get("financials", {
        "filters": f"CERT:{cert}",
        "fields": FINANCIAL_FIELDS["interest_rate_risk"],
        "sort_by": "REPDTE",
        "sort_order": "DESC",
        "limit": quarters,
    })
    _display_response(resp, f"interest_rate_risk_cert{cert}")


# ── Holding Company / Institution Structure recipes ───────────────────────────
#
# FDIC data links bank subsidiaries to their holding companies via NAMEHCR
# and RSSDHCR. Use these to roll up bank-level data to the HC level.

def cmd_holding_company():
    """Show holding company lineage for a CERT + all sibling banks under the same HC.
    NAMEHCR = top-holder name, RSSDHCR = Fed's RSSD ID of the top-holder.
    Helpful for understanding consolidated entity exposure (e.g. a HC with
    multiple bank subs all contributing to the same risk envelope)."""
    print("\n== Holding Company Lookup ==")
    cert = _prompt("CERT number")
    if not cert:
        return

    resp = _get("institutions", {
        "filters": f"CERT:{cert}",
        "fields": "CERT,NAME,STALP,NAMEHCR,RSSDHCR,STALPHCR,CITYHCR,PARCERT,CERTCONS",
        "limit": 1,
    })
    rows, _ = _extract_rows(resp)
    if not rows:
        print(f"  No institution found with CERT {cert}")
        return
    rssd_hcr = rows[0].get("RSSDHCR")
    name_hcr = rows[0].get("NAMEHCR") or ""
    print(f"\n  Bank: {rows[0].get('NAME')} (CERT {cert})")
    print(f"  Holding company: {name_hcr} (RSSD {rssd_hcr})")

    if rssd_hcr:
        sib = _get("institutions", {
            "filters": f'RSSDHCR:{rssd_hcr} AND ACTIVE:1',
            "fields": "CERT,NAME,STALP,CITY,ASSET,DEP,NETINC,BKCLASS,NAMEHCR",
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": 50,
        })
        print(f"\n  Bank subsidiaries under HC RSSD {rssd_hcr}:")
        _display_response(sib, f"hc_siblings_cert{cert}")


def cmd_holding_company_roster():
    """List all bank subsidiaries under a given holding company by name or RSSD ID."""
    print("\n== Holding Company Roster ==")
    hcr = _prompt("HC name (NAMEHCR, case-insensitive) or RSSD ID")
    if not hcr:
        return
    if hcr.isdigit():
        filt = f"RSSDHCR:{hcr}"
    else:
        filt = f'NAMEHCR:"{hcr.upper()}"'
    filt += " AND ACTIVE:1"
    resp = _get("institutions", {
        "filters": filt,
        "fields": "CERT,NAME,STALP,CITY,ASSET,DEP,NETINC,BKCLASS,NAMEHCR,RSSDHCR",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"hc_roster_{hcr}")


def cmd_new_banks():
    """Recently chartered institutions (NEWINST=1 flag at most recent quarter).
    These are new charters or recharters in the current reporting period."""
    print("\n== Newly Chartered Institutions ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND NEWINST:1",
        "fields": "CERT,REPDTE,NAME,STALP,ASSET,DEP,NEWINST,DENOVO,BKCLASS",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"new_banks_{repdte}")


def cmd_de_novo():
    """De novo banks (DENOVO=1 flag) for a given reporting period.
    Denotes a new institution that is not a recharter - true new bank formation."""
    print("\n== De Novo Banks ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND DENOVO:1",
        "fields": "CERT,REPDTE,NAME,STALP,ASSET,DEP,DENOVO,NEWINST,BKCLASS",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"de_novo_{repdte}")


def cmd_minority_banks():
    """Minority Depository Institutions (MDIs) currently active.
    MNRTYCDE classifies the minority type:
      1=Black, 2=Asian American, 3=Chinese American, 4=Korean American,
      5=Japanese American, 6=Indian/Arabic American, 7=Hispanic American,
      8=Multi-racial American, 9=Native American."""
    print("\n== Minority Depository Institutions ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND MINORITY:1",
        "fields": "CERT,REPDTE,NAME,STALP,ASSET,DEP,NETINC,ROA,ROE,MINORITY,MNRTYCDE,CB",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 200,
    })
    _display_response(resp, f"minority_banks_{repdte}")


def cmd_structure_changes():
    """Structure changes aggregated by CHANGECODE for a date range.
    CHANGECODE maps to merger, acquisition, name change, charter conversion, etc.
    Key codes: 110/120=acquisition, 211-224=merger, 310/320=consolidation,
    420/430=relocation, 470=name change, 510+=branch events."""
    print("\n== Structure Changes Aggregated ==")
    start = _prompt("Start date YYYY-MM-DD", "2020-01-01")
    end = _prompt("End date YYYY-MM-DD", "2025-12-31")
    resp = _get("history", {
        "filters": f'PROCDATE:["{start}" TO "{end}"]',
        "fields": "INSTNAME,CERT,CHANGECODE,PROCDATE",
        "agg_by": "CHANGECODE",
        "agg_limit": 50,
        "sort_by": "PROCDATE",
        "sort_order": "DESC",
        "limit": 1,
    })
    if resp:
        meta = resp.get("meta", {})
        print(f"  Total structure events in range: {meta.get('total', 'N/A'):,}")
        _display_response(resp, f"structure_changes_{start}_{end}")


def cmd_mergers_by_year():
    """Merger and acquisition count by year.
    Filters to CHANGECODE ranges indicating M&A and consolidations."""
    print("\n== Mergers & Acquisitions by Year ==")
    start_year = _prompt("Start year", "2000")
    end_year = _prompt("End year", "2025")
    resp = _get("history", {
        "filters": f'PROCDATE:["{start_year}-01-01" TO "{end_year}-12-31"] AND CHANGECODE:[110 TO 399]',
        "fields": "INSTNAME,CERT,CHANGECODE,PROCDATE",
        "agg_by": "PROCDATE",
        "agg_limit": 500,
        "sort_by": "PROCDATE",
        "sort_order": "DESC",
        "limit": 1,
    })
    if resp:
        meta = resp.get("meta", {})
        print(f"  Total M&A events {start_year}-{end_year}: {meta.get('total', 'N/A'):,}")
        _display_response(resp, f"mergers_{start_year}_{end_year}")


# ── Specialty / Sector recipes ────────────────────────────────────────────────
#
# Banks are categorized by SPECGRP (1-9) based on asset concentration.
# 1=International, 2=Agricultural, 3=Credit Card, 4=Commercial Lending,
# 5=Mortgage Lending, 6=Consumer Lending, 7=Other Specialized, 8=All Other
# <$1B, 9=All Other >$1B.

def cmd_specialty_breakdown():
    """Banking system breakdown by SPECGRP (specialty group).
    Aggregates bank count and total assets by specialty category."""
    print("\n== Specialty Group Breakdown ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte}",
        "fields": "CERT,REPDTE,ASSET,SPECGRP,SPECGRPDESC",
        "agg_by": "SPECGRP",
        "agg_sum_fields": "ASSET",
        "agg_limit": 15,
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 1,
    })
    _display_response(resp, f"specialty_breakdown_{repdte}")


def cmd_ag_banks():
    """Agricultural banks (SPECGRP=2): heavy ag + ag RE concentration.
    Key metrics: ag loans vs capital, ag NCO rate, ag past-dues."""
    print("\n== Agricultural Banks ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    min_assets = _prompt("Minimum assets ($000s)", "100000")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND SPECGRP:2 AND ASSET:[{min_assets} TO *]",
        "fields": "CERT,REPDTE,ASSET,LNAG,LNREAG,LNLSNET,EQTOT,IDT1CER,NTAG,NTAGR,P9AG,NAAG,ROA,SPECGRPDESC",
        "sort_by": "LNAG",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"ag_banks_{repdte}")


def cmd_credit_card_banks():
    """Credit card monoline banks (SPECGRP=3): high LNCRCD / loans."""
    print("\n== Credit Card Banks ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND SPECGRP:3",
        "fields": "CERT,REPDTE,ASSET,LNCRCD,LNCRCDRP,LNCON,LNLSNET,EQTOT,NTCRCD,NTCRCDR,P9CRCD,NACRCD,ROA,SPECGRPDESC",
        "sort_by": "LNCRCD",
        "sort_order": "DESC",
        "limit": 50,
    })
    _display_response(resp, f"credit_card_banks_{repdte}")


def cmd_trust_banks():
    """Banks with significant fiduciary / trust activities.
    Key signal: IFIDUC (trust fee income) + TFRA (total fiduciary assets).
    Banks with trust powers hold billions in customer assets off-balance-sheet."""
    print("\n== Trust Banks ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    min_ifiduc = _prompt("Minimum YTD fiduciary income ($000s)", "10000")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND IFIDUC:[{min_ifiduc} TO *]",
        "fields": "CERT,REPDTE,ASSET,TFRA,NFAA,IFIDUC,TNI,TETOT,TRUST,TRUSTPWR",
        "sort_by": "TFRA",
        "sort_order": "DESC",
        "limit": 50,
    })
    _display_response(resp, f"trust_banks_{repdte}")


def cmd_mortgage_originators():
    """Banks with material mortgage servicing portfolios.
    Key field: INTANMSR (mortgage servicing assets) and LNSERV (servicing balance)."""
    print("\n== Mortgage Originators (MSR holders) ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    min_msr = _prompt("Minimum MSR ($000s)", "10000")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND INTANMSR:[{min_msr} TO *]",
        "fields": "CERT,REPDTE,ASSET,INTANMSR,INTANMSRR,LNSERV,LNLSSALE,LNREPP,MTGLS,LNRERES",
        "sort_by": "INTANMSR",
        "sort_order": "DESC",
        "limit": 50,
    })
    _display_response(resp, f"mortgage_originators_{repdte}")


# ── COVID Emergency Programs ──────────────────────────────────────────────────

def cmd_ppp_exposure():
    """PPP loan exposure across banks.
    PPPLNBAL = outstanding PPP loan balance ($000s), PPPLNNUM = count of loans,
    PPPLNPLG = pledged to PPP Lending Facility. Most PPP loans were forgiven
    by end of 2023 but residual balances exist."""
    print("\n== PPP Loan Exposure ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    min_ppp = _prompt("Minimum PPP balance ($000s)", "1000")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND PPPLNBAL:[{min_ppp} TO *]",
        "fields": "CERT,REPDTE,ASSET,PPPLNBAL,PPPLNNUM,PPPLNPLG,PPPLF1LS,PPPLFOV1,AVPPPPLG,MMLFBAL",
        "sort_by": "PPPLNBAL",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"ppp_exposure_{repdte}")


# ── Capital / Regulatory recipes ──────────────────────────────────────────────

def cmd_cblr_screen():
    """Banks using the Community Bank Leverage Ratio framework (CBLRIND=1).
    Post-2020 simplified capital rule: qualifying banks < $10B with limited
    off-B/S and trading. CBLR replaces full risk-based capital calculation."""
    print("\n== CBLR (Community Bank Leverage Ratio) Screen ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND CBLRIND:1",
        "fields": "CERT,REPDTE,ASSET,AVASSETJ,EQTOT,CBLRIND,IDT1CER,RBC1AAJ,CB,BKCLASS,ROA",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"cblr_screen_{repdte}")


def cmd_asset_size_distribution():
    """Asset size distribution: count and total assets by size bucket.
    Uses the SZ* flags to count banks in each tier."""
    print("\n== Asset Size Distribution ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    buckets = [
        ("<$25M", "SZ25:1"),
        ("$25M-$50M", "SZ25T50:1"),
        ("$50M-$100M", "SZ50T100:1"),
        ("$100M-$1B", "SZ100T1B:1"),
        ("$1B-$10B", "SZ1BT10B:1"),
        ("$10B+", "SZ10BP:1"),
        ("$250B+", "SZ250BP:1"),
    ]
    print(f"\n  Report date: {repdte}")
    results = []
    for label, filt in buckets:
        resp = _get("financials", {
            "filters": f"REPDTE:{repdte} AND {filt}",
            "fields": "CERT,ASSET",
            "limit": 1,
        })
        if resp:
            total_ct = resp.get("meta", {}).get("total", 0)
            results.append({"size_bucket": label, "bank_count": total_ct})
    _print_table(results)


def cmd_foreign_exposure():
    """Banks with largest foreign office exposure.
    Ranks banks by ASSETFOR (foreign office assets) and shows foreign deposits,
    foreign loans, and foreign-office earnings contribution."""
    print("\n== Foreign Office Exposure ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    min_for = _prompt("Minimum foreign assets ($000s)", "100000")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND ASSETFOR:[{min_for} TO *]",
        "fields": "CERT,REPDTE,ASSET,ASSETFOR,LIABFOR,DEPFOR,DEPIFOR,LNCIFOR,LNREFOR,ILNFOR,EDEPFOR",
        "sort_by": "ASSETFOR",
        "sort_order": "DESC",
        "limit": 50,
    })
    _display_response(resp, f"foreign_exposure_{repdte}")


def cmd_efficiency_distribution():
    """Efficiency ratio (NONIX / (NIM + NONII)) distribution across large banks.
    Lower is better. 50-60% = healthy, 70%+ = stressed/inefficient operations."""
    print("\n== Efficiency Ratio Distribution ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    min_assets = _prompt("Minimum assets ($000s)", "1000000")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND ASSET:[{min_assets} TO *]",
        "fields": "CERT,REPDTE,ASSET,EEFFR,EEFFQR,NONIX,NONII,NIM,ESAL,NUMEMP,ROA",
        "sort_by": "EEFFR",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"efficiency_dist_{repdte}")


def cmd_charge_off_waterfall():
    """Detailed net charge-off waterfall for a bank by loan category.
    Shows NCOs broken down by RE (with sub-types), C&I, consumer, credit card,
    ag, auto, leases, other - both YTD and quarterly rates."""
    print("\n== Charge-Off Waterfall ==")
    cert = _prompt("CERT number")
    if not cert:
        return
    quarters = int(_prompt("How many quarters", "8"))
    resp = _get("financials", {
        "filters": f"CERT:{cert}",
        "fields": "CERT,REPDTE,NTLNLS,NTLNLSR,NTRE,NTREAG,NTRECONS,NTREMULT,NTRENRES,NTRERES,NTRELOC,NTCI,NTCON,NTCRCD,NTAG,NTAUTO,NTLS,NTOTHER,NTLNLSQ,NTLNLSQR",
        "sort_by": "REPDTE",
        "sort_order": "DESC",
        "limit": quarters,
    })
    _display_response(resp, f"charge_off_waterfall_cert{cert}")


def cmd_npf_screen():
    """Non-performing asset ratio screen.
    NPA = 90+ past-due + non-accrual + ORE (foreclosed properties).
    High NPA ratio = bank health stress signal."""
    print("\n== Non-Performing Asset Screen ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    min_assets = _prompt("Minimum assets ($000s)", "1000000")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte} AND ASSET:[{min_assets} TO *]",
        "fields": "CERT,REPDTE,ASSET,NALNLS,P9ASSET,P9LNLS,ORE,NPERF,NPERFV,LNATRES,LNRESNCR,NCLNLS,NCLNLSR",
        "sort_by": "NPERF",
        "sort_order": "DESC",
        "limit": 100,
    })
    _display_response(resp, f"npf_screen_{repdte}")


def cmd_fed_district_banks():
    """Banks by Federal Reserve district.
    Fed districts: 1=Boston, 2=NY, 3=Philadelphia, 4=Cleveland, 5=Richmond,
    6=Atlanta, 7=Chicago, 8=St. Louis, 9=Minneapolis, 10=KC, 11=Dallas, 12=SF."""
    print("\n== Federal Reserve District Breakdown ==")
    repdte = _prompt("Report date YYYYMMDD", "20251231")
    resp = _get("financials", {
        "filters": f"REPDTE:{repdte}",
        "fields": "CERT,REPDTE,ASSET,FED,FEDDESC",
        "agg_by": "FED",
        "agg_sum_fields": "ASSET",
        "agg_limit": 15,
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": 1,
    })
    _display_response(resp, f"fed_district_{repdte}")


def cmd_bank_snapshot():
    """Comprehensive snapshot of a bank across 15+ dimensions.
    Combines: identification, balance sheet, income, deposits, loans, credit quality,
    capital, CRE, securities (incl. HTM unrealized), derivatives, holding company."""
    print("\n== Bank Snapshot (Comprehensive Profile) ==")
    cert = _prompt("CERT number")
    if not cert:
        return
    repdte = _prompt("Report date YYYYMMDD (empty for latest)", "")

    if not repdte:
        latest = _get("financials", {
            "filters": f"CERT:{cert}",
            "fields": "REPDTE",
            "sort_by": "REPDTE",
            "sort_order": "DESC",
            "limit": 1,
        })
        rows, _ = _extract_rows(latest)
        if not rows:
            print(f"  No financials found for CERT {cert}")
            return
        repdte = str(rows[0].get("REPDTE"))

    print(f"\n  CERT: {cert}, Report Date: {repdte}")

    sections = [
        ("Institution Profile", FINANCIAL_FIELDS["institution_profile"]),
        ("Balance Sheet", FINANCIAL_FIELDS["balance_sheet"]),
        ("Income Statement", FINANCIAL_FIELDS["income"]),
        ("Deposits", FINANCIAL_FIELDS["deposits_detail"]),
        ("Loans", FINANCIAL_FIELDS["loans"]),
        ("Credit Quality", FINANCIAL_FIELDS["credit_quality"]),
        ("Capital (Basel III)", FINANCIAL_FIELDS["capital_basel"]),
        ("CRE Concentration", FINANCIAL_FIELDS["cre"]),
        ("Securities (incl. unrealized)", FINANCIAL_FIELDS["unrealized_securities"]),
        ("Derivatives", FINANCIAL_FIELDS["derivatives"]),
        ("Key Ratios", FINANCIAL_FIELDS["ratios"]),
    ]

    for label, fields in sections:
        resp = _get("financials", {
            "filters": f"CERT:{cert} AND REPDTE:{repdte}",
            "fields": fields,
            "limit": 1,
        })
        rows, _ = _extract_rows(resp)
        if rows:
            print(f"\n  === {label} ===")
            _print_table(rows)


def cmd_raw_query():
    """Execute a fully custom raw API call."""
    print("\n== Raw API Query ==")
    endpoint = _prompt("Endpoint (institutions/locations/financials/summary/failures/history/sod/demographics)")
    print("  Build query parameters (leave empty to skip):")
    params = {}
    for key in ["filters", "search", "fields", "sort_by", "sort_order", "limit", "offset",
                 "agg_by", "agg_term_fields", "agg_sum_fields", "agg_limit",
                 "total_fields", "subtotal_by", "max_value", "max_value_by"]:
        val = _prompt(f"  {key}")
        if val:
            params[key] = val

    resp = _get(endpoint, params)
    if resp:
        print(json.dumps(resp, indent=2, default=str)[:5000])
        rows, total = _extract_rows(resp)
        _prompt_export(rows, f"raw_{endpoint}")


def cmd_field_catalog():
    """Show available field presets for each endpoint."""
    print("\n== Field Catalog ==")
    endpoint = _prompt("Endpoint (institutions/locations/financials/summary/failures/history/sod/demographics, or 'all')", "all")
    if endpoint == "all":
        for ep, cat in FIELD_CATALOGS.items():
            print(f"\n  /{ep}:")
            for name, fields in cat.items():
                print(f"    {name:15s} -> {fields}")
    else:
        cat = FIELD_CATALOGS.get(endpoint, {})
        if not cat:
            print(f"  No field catalog for /{endpoint}")
            return
        print(f"\n  /{endpoint} field presets:")
        for name, fields in cat.items():
            print(f"    {name:15s} -> {fields}")


# ── Command registry ──────────────────────────────────────────────────────────
#
# Maps interactive menu numbers to command functions. Numbers 1-8 are direct
# endpoint query builders. 10-20 are recipes. 30+ are utility tools.

COMMAND_MAP = {
    "1": cmd_institutions,
    "2": cmd_locations,
    "3": cmd_financials,
    "4": cmd_summary,
    "5": cmd_failures,
    "6": cmd_history,
    "7": cmd_sod,
    "8": cmd_demographics,
    "10": cmd_recipe_largest_banks,
    "11": cmd_recipe_bank_lookup,
    "12": cmd_recipe_bank_financials_ts,
    "13": cmd_recipe_recent_failures,
    "14": cmd_recipe_failures_by_year,
    "15": cmd_recipe_state_banking,
    "16": cmd_recipe_branch_map,
    "17": cmd_recipe_bank_history,
    "18": cmd_recipe_deposit_rankings,
    "19": cmd_recipe_community_banks,
    "20": cmd_recipe_bulk_export,
    "40": cmd_treasurer_deposit_mix,
    "41": cmd_treasurer_uninsured_screen,
    "42": cmd_treasurer_system_deposits,
    "43": cmd_treasurer_funding_costs,
    "44": cmd_treasurer_deposit_rankings_geo,
    "50": cmd_macro_system_health,
    "51": cmd_macro_failure_waves,
    "52": cmd_macro_credit_cycle,
    "53": cmd_macro_nim_regime,
    "54": cmd_macro_capital_distribution,
    "60": cmd_economist_cre_screen,
    "61": cmd_economist_loan_growth,
    "62": cmd_economist_reserve_adequacy,
    "63": cmd_economist_securities_portfolio,
    "64": cmd_economist_peer_comparison,
    "65": cmd_economist_past_due_detail,
    "70": cmd_htm_stress,
    "71": cmd_afs_stress,
    "72": cmd_securities_fair_value,
    "73": cmd_interest_rate_risk,
    "74": cmd_cblr_screen,
    "75": cmd_npf_screen,
    "76": cmd_charge_off_waterfall,
    "77": cmd_efficiency_distribution,
    "78": cmd_foreign_exposure,
    "79": cmd_asset_size_distribution,
    "80": cmd_holding_company,
    "81": cmd_holding_company_roster,
    "82": cmd_new_banks,
    "83": cmd_de_novo,
    "84": cmd_minority_banks,
    "85": cmd_structure_changes,
    "86": cmd_mergers_by_year,
    "87": cmd_fed_district_banks,
    "88": cmd_specialty_breakdown,
    "89": cmd_ag_banks,
    "92": cmd_credit_card_banks,
    "93": cmd_trust_banks,
    "94": cmd_mortgage_originators,
    "95": cmd_ppp_exposure,
    "96": cmd_bank_snapshot,
    "90": cmd_raw_query,
    "91": cmd_field_catalog,
}


def interactive_loop():
    while True:
        print("\n" + "=" * 76)
        print("  FDIC BankFind Suite API Explorer")
        print("=" * 76)
        print("\n  ENDPOINTS (full query builder):")
        print("    1.  Institutions     - bank demographics, charter, assets")
        print("    2.  Locations        - branch/office locations, lat/lng")
        print("    3.  Financials       - quarterly Call Report data (2,377 fields, 60+ presets)")
        print("    4.  Summary          - historical aggregates by year (from 1934)")
        print("    5.  Failures         - bank failures with resolution details")
        print("    6.  History          - structure changes (mergers, name changes)")
        print("    7.  SOD              - Summary of Deposits (branch-level)")
        print("    8.  Demographics     - community demographics")
        print()
        print("  GENERAL RECIPES:")
        print("    10. Largest banks (by total assets)")
        print("    11. Bank lookup (fuzzy name search)")
        print("    12. Bank financial time series (quarterly)")
        print("    13. Recent failures")
        print("    14. Failures by year (aggregated)")
        print("    15. State banking summary")
        print("    16. Branch locations (with lat/lng)")
        print("    17. Bank structure history")
        print("    18. Deposit rankings (SOD)")
        print("    19. Community banks by state")
        print("    20. Bulk export (paginated)")
        print()
        print("  TREASURER (deposit flows, funding, liquidity):")
        print("    40. Deposit mix (demand/MMDA/time/uninsured/brokered)")
        print("    41. Uninsured deposit concentration screen")
        print("    42. System deposit trends (1934-present)")
        print("    43. Funding cost comparison (multi-bank)")
        print("    44. Geographic deposit market share (SOD)")
        print()
        print("  MACRO ANALYST (credit cycles, system risk, NIM regimes):")
        print("    50. System health history (1934-present)")
        print("    51. Failure wave analysis (count + assets by year)")
        print("    52. Credit cycle indicators (NCL, provisions, past-due)")
        print("    53. NIM regime across top banks")
        print("    54. Capital ratio distribution")
        print()
        print("  BALANCE SHEET ECONOMIST (loans, CRE, reserves, structure):")
        print("    60. CRE concentration screen")
        print("    61. Loan growth decomposition (time series)")
        print("    62. Reserve adequacy screen")
        print("    63. Securities portfolio composition")
        print("    64. Peer comparison (any preset)")
        print("    65. Past-due & non-accrual detail")
        print()
        print("  RATE RISK / CAPITAL / CREDIT DEEP DIVE:")
        print("    70. HTM unrealized loss screen (SVB-style rate risk)")
        print("    71. AFS unrealized loss screen (AOCI hit)")
        print("    72. Securities fair value time series (single bank)")
        print("    73. Interest rate risk (repricing gap)")
        print("    74. CBLR (Community Bank Leverage Ratio) screen")
        print("    75. Non-performing asset ratio screen")
        print("    76. Charge-off waterfall (by loan type)")
        print("    77. Efficiency ratio distribution")
        print("    78. Foreign office exposure")
        print("    79. Asset size distribution (system-wide)")
        print()
        print("  INSTITUTIONAL STRUCTURE / DEMOGRAPHICS:")
        print("    80. Holding company lookup (CERT -> HC + siblings)")
        print("    81. Holding company roster (all subs under HC)")
        print("    82. Newly chartered banks (NEWINST=1)")
        print("    83. De novo banks (DENOVO=1)")
        print("    84. Minority Depository Institutions")
        print("    85. Structure changes (aggregated by CHANGECODE)")
        print("    86. Mergers & acquisitions by year")
        print("    87. Fed district breakdown")
        print()
        print("  SPECIALTY / SECTOR:")
        print("    88. Specialty group breakdown (SPECGRP)")
        print("    89. Agricultural banks")
        print("    92. Credit card monoline banks")
        print("    93. Trust banks (fiduciary income)")
        print("    94. Mortgage originators (MSR holders)")
        print("    95. PPP loan exposure")
        print("    96. Bank snapshot (comprehensive 10-section profile)")
        print()
        print("  TOOLS:")
        print("    90. Raw query (fully custom)")
        print("    91. Field catalog")
        print()
        print("    q.  Quit")

        choice = input("\n  Choice: ").strip()
        if choice.lower() in ("q", "quit", "exit"):
            print("  Bye.")
            break
        if choice in COMMAND_MAP:
            try:
                COMMAND_MAP[choice]()
            except KeyboardInterrupt:
                print("\n  (interrupted)")
            except Exception as e:
                print(f"  [!] Error: {e}")
        else:
            print("  Invalid choice.")


# ── Non-interactive CLI ───────────────────────────────────────────────────────
#
# Full argparse interface mirroring every interactive command. Designed for:
#   - Scripted automation (cron jobs, pipelines)
#   - Cursor/LLM tool use (run commands, parse JSON output)
#   - Quick one-off queries from the terminal
#
# The --json flag on any subcommand outputs raw API JSON for programmatic parsing.
# The --export flag saves results to a local file.

def build_argparse():
    parser = argparse.ArgumentParser(
        description="FDIC BankFind Suite API Explorer - public bank data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python fdic_demo.py institutions --filters 'STALP:NY AND ACTIVE:1' --limit 10
  python fdic_demo.py institutions --search 'NAME:JPMorgan' --limit 5
  python fdic_demo.py financials --filters 'CERT:628' --fields CERT,REPDTE,ASSET,DEP --sort-by REPDTE --limit 8
  python fdic_demo.py failures --sort-by FAILDATE --sort-order DESC --limit 10
  python fdic_demo.py summary --filters 'YEAR:2024' --fields STNAME,YEAR,NETINC,ASSET
  python fdic_demo.py largest-banks --top 20 --state NY
  python fdic_demo.py bank-lookup --name "Wells Fargo"
  python fdic_demo.py bank-financials --cert 628 --quarters 12 --preset income
  python fdic_demo.py recent-failures --top 15
  python fdic_demo.py failures-by-year
  python fdic_demo.py bulk-export --endpoint institutions --filters 'ACTIVE:1 AND STALP:CA' --format csv
""")
    sub = parser.add_subparsers(dest="command")

    for ep in ["institutions", "locations", "financials", "summary", "failures", "history", "sod", "demographics"]:
        p = sub.add_parser(ep, help=ENDPOINT_DESCRIPTIONS.get(ep, ""))
        p.add_argument("--filters", default="")
        p.add_argument("--fields", default="")
        p.add_argument("--sort-by", default="")
        p.add_argument("--sort-order", default="DESC")
        p.add_argument("--limit", type=int, default=25)
        p.add_argument("--offset", type=int, default=0)
        if ep in ("institutions", "history"):
            p.add_argument("--search", default="")
        if ep in ("financials", "summary", "failures", "history", "sod"):
            p.add_argument("--agg-by", default="")
            p.add_argument("--agg-term-fields", default="")
            p.add_argument("--agg-sum-fields", default="")
            p.add_argument("--agg-limit", type=int, default=10)
        if ep == "failures":
            p.add_argument("--total-fields", default="")
            p.add_argument("--subtotal-by", default="")
        p.add_argument("--json", action="store_true", help="Output raw JSON")
        p.add_argument("--export", choices=["json", "csv"], default="")

    p = sub.add_parser("largest-banks", help="Top banks by assets")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--state", default="")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("bank-lookup", help="Fuzzy name search")
    p.add_argument("--name", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("bank-financials", help="Quarterly financial time series")
    p.add_argument("--cert", required=True)
    p.add_argument("--quarters", type=int, default=20)
    p.add_argument("--preset", default="default", choices=list(FINANCIAL_FIELDS.keys()))
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("recent-failures", help="Recent bank failures")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("failures-by-year", help="Failure aggregates by year")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("state-summary", help="State banking summary for a year")
    p.add_argument("--year", default="2024")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("branches", help="Branch locations for a bank")
    p.add_argument("--cert", required=True)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("bank-history", help="Structure change history")
    p.add_argument("--cert", required=True)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("deposit-rankings", help="SOD deposit rankings")
    p.add_argument("--year", default="2024")
    p.add_argument("--state", default="")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("community-banks", help="Community banks by state")
    p.add_argument("--state", default="NY")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("bulk-export", help="Paginated bulk export")
    p.add_argument("--endpoint", required=True, choices=["institutions", "locations", "financials", "summary", "failures", "history", "sod"])
    p.add_argument("--filters", default="")
    p.add_argument("--fields", default="")
    p.add_argument("--max-records", type=int, default=10000)
    p.add_argument("--format", choices=["json", "csv"], default="csv")

    # Treasurer recipes
    p = sub.add_parser("deposit-mix", help="Granular deposit composition for a bank")
    p.add_argument("--cert", required=True)
    p.add_argument("--quarters", type=int, default=20)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("uninsured-screen", help="Screen for uninsured deposit concentration")
    p.add_argument("--min-assets", type=int, default=1000000)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("system-deposits", help="System-wide deposit trends")
    p.add_argument("--years", type=int, default=20)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("funding-costs", help="Funding cost comparison across banks")
    p.add_argument("--certs", default="628,3510,7213,3511,33124")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("geo-deposits", help="Geographic deposit market share")
    p.add_argument("--year", default="2023")
    p.add_argument("--state", required=True)
    p.add_argument("--json", action="store_true")

    # Macro analyst recipes
    p = sub.add_parser("system-health", help="System health history 1934-present")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("failure-waves", help="Failure count + assets by year")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("credit-cycle", help="Cross-bank credit cycle indicators")
    p.add_argument("--min-assets", type=int, default=10000000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("nim-regime", help="NIM across top banks")
    p.add_argument("--top", type=int, default=50)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("capital-distribution", help="Capital ratio distribution")
    p.add_argument("--min-assets", type=int, default=1000000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    # Balance sheet economist recipes
    p = sub.add_parser("cre-screen", help="CRE concentration screen")
    p.add_argument("--min-assets", type=int, default=1000000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("loan-growth", help="Loan growth decomposition time series")
    p.add_argument("--cert", required=True)
    p.add_argument("--quarters", type=int, default=20)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("reserve-adequacy", help="Reserve adequacy screen")
    p.add_argument("--min-assets", type=int, default=10000000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("securities-portfolio", help="Securities composition")
    p.add_argument("--cert", default="")
    p.add_argument("--quarters", type=int, default=20)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("peer-comparison", help="Multi-bank comparison on any preset")
    p.add_argument("--certs", required=True, help="Comma-separated CERT numbers")
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--preset", default="default", choices=list(FINANCIAL_FIELDS.keys()))
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("past-due-detail", help="Past-due and non-accrual detail")
    p.add_argument("--cert", required=True)
    p.add_argument("--quarters", type=int, default=12)
    p.add_argument("--json", action="store_true")

    # Rate risk / capital / credit
    p = sub.add_parser("htm-stress", help="HTM securities unrealized loss screen")
    p.add_argument("--min-assets", type=int, default=10000000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("afs-stress", help="AFS securities unrealized loss screen")
    p.add_argument("--min-assets", type=int, default=10000000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("securities-fair-value", help="Securities fair value time series")
    p.add_argument("--cert", required=True)
    p.add_argument("--quarters", type=int, default=20)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("interest-rate-risk", help="Repricing gap analysis (loans, deposits, securities)")
    p.add_argument("--cert", required=True)
    p.add_argument("--quarters", type=int, default=8)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("cblr-screen", help="Banks using Community Bank Leverage Ratio")
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("npf-screen", help="Non-performing asset ratio screen")
    p.add_argument("--min-assets", type=int, default=1000000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("charge-off-waterfall", help="NCO waterfall for a bank by loan type")
    p.add_argument("--cert", required=True)
    p.add_argument("--quarters", type=int, default=8)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("efficiency-distribution", help="Efficiency ratio distribution")
    p.add_argument("--min-assets", type=int, default=1000000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("foreign-exposure", help="Banks with foreign office assets")
    p.add_argument("--min-foreign", type=int, default=100000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("asset-size-distribution", help="Bank count by asset size bucket")
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    # Holding company / structure / demographics
    p = sub.add_parser("holding-company", help="HC lookup for a CERT + bank siblings")
    p.add_argument("--cert", required=True)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("holding-company-roster", help="All banks under a holding company")
    p.add_argument("--hcr", required=True, help="HC name (NAMEHCR) or RSSD ID")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("new-banks", help="Newly chartered institutions")
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("de-novo", help="De novo banks (not recharters)")
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("minority-banks", help="Minority Depository Institutions")
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("structure-changes", help="Aggregated structure events by CHANGECODE")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("mergers-by-year", help="M&A aggregates by year")
    p.add_argument("--start-year", default="2000")
    p.add_argument("--end-year", default="2025")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("fed-district-banks", help="Banks by Federal Reserve district")
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    # Specialty
    p = sub.add_parser("specialty-breakdown", help="Specialty group (SPECGRP) breakdown")
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("ag-banks", help="Agricultural banks (SPECGRP=2)")
    p.add_argument("--min-assets", type=int, default=100000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("credit-card-banks", help="Credit card banks (SPECGRP=3)")
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("trust-banks", help="Banks with significant trust activity")
    p.add_argument("--min-ifiduc", type=int, default=10000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("mortgage-originators", help="Banks with material MSR")
    p.add_argument("--min-msr", type=int, default=10000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("ppp-exposure", help="PPP loan balance exposure")
    p.add_argument("--min-ppp", type=int, default=1000)
    p.add_argument("--repdte", default="20251231")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("bank-snapshot", help="Comprehensive multi-section profile for a bank")
    p.add_argument("--cert", required=True)
    p.add_argument("--repdte", default="", help="YYYYMMDD, empty for latest")
    p.add_argument("--json", action="store_true")

    sub.add_parser("field-catalog", help="Show field presets for all endpoints")

    return parser


def _ni_output(resp, args, prefix):
    """Handle non-interactive output: print table or JSON, optionally export."""
    if not resp:
        return
    if getattr(args, "json", False):
        print(json.dumps(resp, indent=2, default=str))
        return
    rows, total = _extract_rows(resp)
    meta = resp.get("meta", {})
    print(f"Total: {meta.get('total', total):,} | Returned: {len(rows)}")
    if rows:
        _print_table(rows)
    export_fmt = getattr(args, "export", "")
    if export_fmt and rows:
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = f"{prefix}_{ts}.{export_fmt}"
        if export_fmt == "json":
            with open(fname, "w") as f:
                json.dump(rows, f, indent=2, default=str)
        else:
            headers = list(rows[0].keys())
            with open(fname, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
        print(f"Exported to {fname}")


def run_noninteractive(args):
    cmd = args.command

    endpoints = ["institutions", "locations", "financials", "summary", "failures", "history", "sod", "demographics"]
    if cmd in endpoints:
        params = {}
        if args.filters:
            params["filters"] = args.filters
        if args.fields:
            params["fields"] = args.fields
        elif cmd in FIELD_CATALOGS and "default" in FIELD_CATALOGS[cmd]:
            params["fields"] = FIELD_CATALOGS[cmd]["default"]
        if args.sort_by:
            params["sort_by"] = args.sort_by
        params["sort_order"] = args.sort_order
        params["limit"] = args.limit
        if args.offset:
            params["offset"] = args.offset
        if hasattr(args, "search") and args.search:
            params["search"] = args.search
        if hasattr(args, "agg_by") and args.agg_by:
            params["agg_by"] = args.agg_by
            if args.agg_term_fields:
                params["agg_term_fields"] = args.agg_term_fields
            if args.agg_sum_fields:
                params["agg_sum_fields"] = args.agg_sum_fields
            params["agg_limit"] = args.agg_limit
        if hasattr(args, "total_fields") and args.total_fields:
            params["total_fields"] = args.total_fields
        if hasattr(args, "subtotal_by") and args.subtotal_by:
            params["subtotal_by"] = args.subtotal_by
        resp = _get(cmd, params)
        _ni_output(resp, args, cmd)

    elif cmd == "largest-banks":
        filt = "ACTIVE:1"
        if args.state:
            filt += f' AND STALP:"{args.state.upper()}"'
        resp = _get("institutions", {
            "filters": filt,
            "fields": "CERT,NAME,STALP,CITY,ASSET,DEP,NETINC,ROE,ROA,OFFICES",
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": args.top,
        })
        _ni_output(resp, args, "largest_banks")

    elif cmd == "bank-lookup":
        resp = _get("institutions", {
            "search": f"NAME:{args.name}",
            "fields": "CERT,NAME,STALP,CITY,ACTIVE,ASSET,DEP,BKCLASS,DATEUPDT",
            "limit": args.limit,
        })
        _ni_output(resp, args, "bank_lookup")

    elif cmd == "bank-financials":
        fields = FINANCIAL_FIELDS.get(args.preset, FINANCIAL_FIELDS["default"])
        resp = _get("financials", {
            "filters": f"CERT:{args.cert}",
            "fields": fields,
            "sort_by": "REPDTE",
            "sort_order": "DESC",
            "limit": args.quarters,
        })
        _ni_output(resp, args, f"financials_{args.cert}")

    elif cmd == "recent-failures":
        resp = _get("failures", {
            "fields": FAILURE_FIELDS["default"],
            "sort_by": "FAILDATE",
            "sort_order": "DESC",
            "limit": args.top,
        })
        _ni_output(resp, args, "recent_failures")

    elif cmd == "failures-by-year":
        resp = _get("failures", {
            "fields": "NAME,CERT,FAILDATE,QBFASSET,COST",
            "sort_by": "FAILDATE",
            "sort_order": "DESC",
            "limit": 1,
            "agg_by": "FAILYR",
            "agg_sum_fields": "QBFASSET,COST",
            "agg_limit": 50,
        })
        if getattr(args, "json", False):
            print(json.dumps(resp, indent=2, default=str))
        else:
            if resp:
                meta = resp.get("meta", {})
                print(f"Total failures: {meta.get('total', 'N/A'):,}")
                print(json.dumps(resp, indent=2, default=str)[:3000])

    elif cmd == "state-summary":
        resp = _get("summary", {
            "filters": f"YEAR:{args.year}",
            "fields": "STNAME,YEAR,INTINC,NETINC,ASSET,DEP",
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": 60,
        })
        _ni_output(resp, args, f"state_summary_{args.year}")

    elif cmd == "branches":
        resp = _get("locations", {
            "filters": f"CERT:{args.cert}",
            "fields": LOCATION_FIELDS["full"],
            "sort_by": "STALP",
            "sort_order": "ASC",
            "limit": 10000,
        })
        _ni_output(resp, args, f"branches_{args.cert}")

    elif cmd == "bank-history":
        resp = _get("history", {
            "filters": f"CERT:{args.cert}",
            "fields": HISTORY_FIELDS["default"],
            "sort_by": "PROCDATE",
            "sort_order": "DESC",
            "limit": 100,
        })
        _ni_output(resp, args, f"history_{args.cert}")

    elif cmd == "deposit-rankings":
        filt = f"YEAR:{args.year}"
        if args.state:
            filt += f' AND STALPBR:"{args.state.upper()}"'
        resp = _get("sod", {
            "filters": filt,
            "fields": SOD_FIELDS["default"],
            "sort_by": "DEPSUMBR",
            "sort_order": "DESC",
            "limit": 25,
        })
        _ni_output(resp, args, f"deposits_{args.year}")

    elif cmd == "community-banks":
        resp = _get("institutions", {
            "filters": f'ACTIVE:1 AND CB:1 AND STALP:"{args.state.upper()}"',
            "fields": "CERT,NAME,CITY,STALP,ASSET,DEP,NETINC,ROA,ROE,OFFICES",
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": 50,
        })
        _ni_output(resp, args, f"community_banks_{args.state}")

    elif cmd == "bulk-export":
        params = {}
        if args.filters:
            params["filters"] = args.filters
        if args.fields:
            params["fields"] = args.fields
        elif args.endpoint in FIELD_CATALOGS and "default" in FIELD_CATALOGS[args.endpoint]:
            params["fields"] = FIELD_CATALOGS[args.endpoint]["default"]
        max_rec = args.max_records if args.max_records > 0 else None
        all_rows = list(_get_all(args.endpoint, params, max_records=max_rec))
        if not all_rows:
            print("No records found.")
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = f"{args.endpoint}_export_{ts}.{args.format}"
        if args.format == "json":
            with open(fname, "w") as f:
                json.dump(all_rows, f, indent=2, default=str)
        else:
            headers = list(all_rows[0].keys())
            with open(fname, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
                w.writeheader()
                w.writerows(all_rows)
        print(f"Exported {len(all_rows)} records to {fname}")

    # Treasurer
    elif cmd == "deposit-mix":
        resp = _get("financials", {
            "filters": f"CERT:{args.cert}",
            "fields": "CERT,REPDTE,DEP,DEPDOM,DEPFOR,DDT,NTRSMMDA,NTRTMLG,NTRSOTH,DEPUNA,BRO,EDEPDOM",
            "sort_by": "REPDTE", "sort_order": "DESC", "limit": args.quarters,
        })
        _ni_output(resp, args, f"deposit_mix_{args.cert}")

    elif cmd == "uninsured-screen":
        resp = _get("financials", {
            "filters": f"REPDTE:20251231 AND ASSET:[{args.min_assets} TO *]",
            "fields": "CERT,REPDTE,ASSET,DEP,DEPUNA,BRO,EQTOT,IDT1CER",
            "sort_by": "ASSET", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, "uninsured_screen")

    elif cmd == "system-deposits":
        resp = _get("summary", {
            "filters": 'STNAME:"United States"',
            "fields": "STNAME,YEAR,ASSET,DEP,INTINC,EINTEXP,NIM,NETINC,ELNATR",
            "sort_by": "YEAR", "sort_order": "DESC", "limit": args.years * 2,
        })
        _ni_output(resp, args, "system_deposits")

    elif cmd == "funding-costs":
        cert_filter = " OR ".join(f"CERT:{c.strip()}" for c in args.certs.split(","))
        resp = _get("financials", {
            "filters": f"REPDTE:20251231 AND ({cert_filter})",
            "fields": "CERT,REPDTE,ASSET,DEP,DEPDOM,EDEPDOM,INTINC,EINTEXP,NIMY,BRO,DEPUNA",
            "sort_by": "ASSET", "sort_order": "DESC", "limit": 20,
        })
        _ni_output(resp, args, "funding_costs")

    elif cmd == "geo-deposits":
        resp = _get("sod", {
            "filters": f'YEAR:{args.year} AND STALPBR:"{args.state.upper()}"',
            "fields": "CERT,NAMEFULL,YEAR,STALPBR,CITYBR,DEPSUMBR,ASSET",
            "sort_by": "DEPSUMBR", "sort_order": "DESC", "limit": 50,
            "agg_by": "CERT", "agg_sum_fields": "DEPSUMBR", "agg_limit": 25,
        })
        _ni_output(resp, args, f"geo_deposits_{args.state}")

    # Macro analyst
    elif cmd == "system-health":
        resp = _get("summary", {
            "filters": 'STNAME:"United States"',
            "fields": "STNAME,YEAR,CB_SI,ASSET,DEP,INTINC,EINTEXP,NIM,NETINC,ELNATR",
            "sort_by": "YEAR", "sort_order": "DESC", "limit": 200,
        })
        _ni_output(resp, args, "system_health")

    elif cmd == "failure-waves":
        resp = _get("failures", {
            "fields": "NAME,CERT,FAILDATE,QBFASSET,QBFDEP,COST",
            "sort_by": "FAILDATE", "sort_order": "DESC", "limit": 1,
            "agg_by": "FAILYR", "agg_sum_fields": "QBFASSET,QBFDEP,COST", "agg_limit": 100,
        })
        if getattr(args, "json", False):
            print(json.dumps(resp, indent=2, default=str))
        elif resp:
            print(f"Total failures: {resp.get('meta',{}).get('total','N/A'):,}")
            print(json.dumps(resp, indent=2, default=str)[:5000])

    elif cmd == "credit-cycle":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND ASSET:[{args.min_assets} TO *]",
            "fields": "CERT,REPDTE,ASSET,NCLNLS,NCLNLSR,NTLNLSR,ELNATR,LNATRES,P3ASSET,P9ASSET,NALNLS,LNLSNTV",
            "sort_by": "ASSET", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"credit_cycle_{args.repdte}")

    elif cmd == "nim-regime":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte}",
            "fields": "CERT,REPDTE,ASSET,DEP,NIMY,INTINC,EINTEXP,EDEPDOM,ROA,ROE",
            "sort_by": "ASSET", "sort_order": "DESC", "limit": args.top,
        })
        _ni_output(resp, args, f"nim_regime_{args.repdte}")

    elif cmd == "capital-distribution":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND ASSET:[{args.min_assets} TO *]",
            "fields": "CERT,REPDTE,ASSET,EQTOT,IDT1CER,RBCRWAJ,RBC1AAJ,EQCDIV,RBCT1J",
            "sort_by": "IDT1CER", "sort_order": "ASC", "limit": 100,
        })
        _ni_output(resp, args, f"capital_dist_{args.repdte}")

    # Balance sheet economist
    elif cmd == "cre-screen":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND ASSET:[{args.min_assets} TO *]",
            "fields": "CERT,REPDTE,ASSET,LNRE,LNRECONS,LNRENRES,LNREMULT,LNRERES,LNREAG,EQTOT,IDT1CER,NCLNLSR",
            "sort_by": "ASSET", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"cre_screen_{args.repdte}")

    elif cmd == "loan-growth":
        resp = _get("financials", {
            "filters": f"CERT:{args.cert}",
            "fields": "CERT,REPDTE,LNLSNET,LNRE,LNRECONS,LNRENRES,LNREMULT,LNRERES,LNCI,LNCRCD,LNCONOTH,LNREAG",
            "sort_by": "REPDTE", "sort_order": "DESC", "limit": args.quarters,
        })
        _ni_output(resp, args, f"loan_growth_{args.cert}")

    elif cmd == "reserve-adequacy":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND ASSET:[{args.min_assets} TO *]",
            "fields": "CERT,REPDTE,ASSET,LNATRES,LNLSNTV,NCLNLS,NCLNLSR,P9ASSET,NALNLS,ELNATR",
            "sort_by": "ASSET", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"reserve_adequacy_{args.repdte}")

    elif cmd == "securities-portfolio":
        if args.cert:
            filt = f"CERT:{args.cert}"
            sort_by, limit = "REPDTE", args.quarters
        else:
            filt = "REPDTE:20251231"
            sort_by, limit = "ASSET", 50
        resp = _get("financials", {
            "filters": filt,
            "fields": "CERT,REPDTE,ASSET,SC,SCUST,SCUSO,SCMUNI,SCMTGBK,SCABS,DEP,EQTOT",
            "sort_by": sort_by, "sort_order": "DESC", "limit": limit,
        })
        _ni_output(resp, args, "securities_portfolio")

    elif cmd == "peer-comparison":
        fields = FINANCIAL_FIELDS.get(args.preset, FINANCIAL_FIELDS["default"])
        cert_filter = " OR ".join(f"CERT:{c.strip()}" for c in args.certs.split(","))
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND ({cert_filter})",
            "fields": fields,
            "sort_by": "ASSET", "sort_order": "DESC", "limit": 20,
        })
        _ni_output(resp, args, f"peer_comparison_{args.repdte}")

    elif cmd == "past-due-detail":
        resp = _get("financials", {
            "filters": f"CERT:{args.cert}",
            "fields": "CERT,REPDTE,ASSET,P3ASSET,P9ASSET,NALNLS,P3RE,P9RE,P3CI,P9CI,NCLNLS,LNATRES",
            "sort_by": "REPDTE", "sort_order": "DESC", "limit": args.quarters,
        })
        _ni_output(resp, args, f"past_due_{args.cert}")

    # Rate risk / securities stress
    elif cmd == "htm-stress":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND ASSET:[{args.min_assets} TO *]",
            "fields": "CERT,REPDTE,ASSET,EQTOT,SC,SCHA,SCHF,SCAA,SCAF,SCMV,SCHTMRES,IDT1CER",
            "sort_by": "SCHA", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"htm_stress_{args.repdte}")

    elif cmd == "afs-stress":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND ASSET:[{args.min_assets} TO *]",
            "fields": "CERT,REPDTE,ASSET,EQTOT,SC,SCAA,SCAF,SCHA,SCHF,SCMV,EQCCOMPI,IDT1CER",
            "sort_by": "SCAA", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"afs_stress_{args.repdte}")

    elif cmd == "securities-fair-value":
        resp = _get("financials", {
            "filters": f"CERT:{args.cert}",
            "fields": FINANCIAL_FIELDS["unrealized_securities"],
            "sort_by": "REPDTE", "sort_order": "DESC", "limit": args.quarters,
        })
        _ni_output(resp, args, f"securities_fv_{args.cert}")

    elif cmd == "interest-rate-risk":
        resp = _get("financials", {
            "filters": f"CERT:{args.cert}",
            "fields": FINANCIAL_FIELDS["interest_rate_risk"],
            "sort_by": "REPDTE", "sort_order": "DESC", "limit": args.quarters,
        })
        _ni_output(resp, args, f"interest_rate_risk_{args.cert}")

    elif cmd == "cblr-screen":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND CBLRIND:1",
            "fields": "CERT,REPDTE,ASSET,AVASSETJ,EQTOT,CBLRIND,IDT1CER,RBC1AAJ,CB,BKCLASS,ROA",
            "sort_by": "ASSET", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"cblr_screen_{args.repdte}")

    elif cmd == "npf-screen":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND ASSET:[{args.min_assets} TO *]",
            "fields": "CERT,REPDTE,ASSET,NALNLS,P9ASSET,P9LNLS,ORE,NPERF,NPERFV,LNATRES,LNRESNCR,NCLNLS,NCLNLSR",
            "sort_by": "NPERF", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"npf_screen_{args.repdte}")

    elif cmd == "charge-off-waterfall":
        resp = _get("financials", {
            "filters": f"CERT:{args.cert}",
            "fields": "CERT,REPDTE,NTLNLS,NTLNLSR,NTRE,NTREAG,NTRECONS,NTREMULT,NTRENRES,NTRERES,NTRELOC,NTCI,NTCON,NTCRCD,NTAG,NTAUTO,NTLS,NTOTHER,NTLNLSQ,NTLNLSQR",
            "sort_by": "REPDTE", "sort_order": "DESC", "limit": args.quarters,
        })
        _ni_output(resp, args, f"charge_off_waterfall_{args.cert}")

    elif cmd == "efficiency-distribution":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND ASSET:[{args.min_assets} TO *]",
            "fields": "CERT,REPDTE,ASSET,EEFFR,EEFFQR,NONIX,NONII,NIM,ESAL,NUMEMP,ROA",
            "sort_by": "EEFFR", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"efficiency_dist_{args.repdte}")

    elif cmd == "foreign-exposure":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND ASSETFOR:[{args.min_foreign} TO *]",
            "fields": "CERT,REPDTE,ASSET,ASSETFOR,LIABFOR,DEPFOR,DEPIFOR,LNCIFOR,LNREFOR,ILNFOR,EDEPFOR",
            "sort_by": "ASSETFOR", "sort_order": "DESC", "limit": 50,
        })
        _ni_output(resp, args, f"foreign_exposure_{args.repdte}")

    elif cmd == "asset-size-distribution":
        buckets = [
            ("<$25M", "SZ25:1"),
            ("$25M-$50M", "SZ25T50:1"),
            ("$50M-$100M", "SZ50T100:1"),
            ("$100M-$1B", "SZ100T1B:1"),
            ("$1B-$10B", "SZ1BT10B:1"),
            ("$10B+", "SZ10BP:1"),
            ("$250B+", "SZ250BP:1"),
        ]
        results = []
        for label, filt in buckets:
            resp = _get("financials", {
                "filters": f"REPDTE:{args.repdte} AND {filt}",
                "fields": "CERT,ASSET",
                "limit": 1,
            })
            if resp:
                total_ct = resp.get("meta", {}).get("total", 0)
                results.append({"size_bucket": label, "bank_count": total_ct})
        if getattr(args, "json", False):
            print(json.dumps({"repdte": args.repdte, "distribution": results}, indent=2))
        else:
            print(f"\n  Asset size distribution for REPDTE={args.repdte}")
            _print_table(results)

    # Holding company / structure
    elif cmd == "holding-company":
        resp = _get("institutions", {
            "filters": f"CERT:{args.cert}",
            "fields": "CERT,NAME,STALP,NAMEHCR,RSSDHCR,STALPHCR,CITYHCR,PARCERT,CERTCONS",
            "limit": 1,
        })
        rows, _ = _extract_rows(resp)
        if not rows:
            if getattr(args, "json", False):
                print(json.dumps({"error": f"no institution found for CERT {args.cert}"}))
            else:
                print(f"No institution found for CERT {args.cert}")
            return
        rssd_hcr = rows[0].get("RSSDHCR")
        name_hcr = rows[0].get("NAMEHCR") or ""
        siblings_resp = None
        if rssd_hcr:
            siblings_resp = _get("institutions", {
                "filters": f'RSSDHCR:{rssd_hcr} AND ACTIVE:1',
                "fields": "CERT,NAME,STALP,CITY,ASSET,DEP,NETINC,BKCLASS,NAMEHCR",
                "sort_by": "ASSET", "sort_order": "DESC", "limit": 50,
            })
        if getattr(args, "json", False):
            out = {"lookup": rows[0], "siblings": siblings_resp or {}}
            print(json.dumps(out, indent=2, default=str))
        else:
            print(f"\nBank: {rows[0].get('NAME')} (CERT {args.cert})")
            print(f"Holding company: {name_hcr} (RSSD {rssd_hcr})\n")
            if siblings_resp:
                sib_rows, _ = _extract_rows(siblings_resp)
                print(f"Bank subsidiaries under HC RSSD {rssd_hcr}:")
                _print_table(sib_rows)

    elif cmd == "holding-company-roster":
        if args.hcr.isdigit():
            filt = f"RSSDHCR:{args.hcr}"
        else:
            filt = f'NAMEHCR:"{args.hcr.upper()}"'
        filt += " AND ACTIVE:1"
        resp = _get("institutions", {
            "filters": filt,
            "fields": "CERT,NAME,STALP,CITY,ASSET,DEP,NETINC,BKCLASS,NAMEHCR,RSSDHCR",
            "sort_by": "ASSET", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"hc_roster_{args.hcr}")

    elif cmd == "new-banks":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND NEWINST:1",
            "fields": "CERT,REPDTE,NAME,STALP,ASSET,DEP,NEWINST,DENOVO,BKCLASS",
            "sort_by": "ASSET", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"new_banks_{args.repdte}")

    elif cmd == "de-novo":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND DENOVO:1",
            "fields": "CERT,REPDTE,NAME,STALP,ASSET,DEP,DENOVO,NEWINST,BKCLASS",
            "sort_by": "ASSET", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"de_novo_{args.repdte}")

    elif cmd == "minority-banks":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND MINORITY:1",
            "fields": "CERT,REPDTE,NAME,STALP,ASSET,DEP,NETINC,ROA,ROE,MINORITY,MNRTYCDE,CB",
            "sort_by": "ASSET", "sort_order": "DESC", "limit": 200,
        })
        _ni_output(resp, args, f"minority_banks_{args.repdte}")

    elif cmd == "structure-changes":
        resp = _get("history", {
            "filters": f'PROCDATE:["{args.start}" TO "{args.end}"]',
            "fields": "INSTNAME,CERT,CHANGECODE,PROCDATE",
            "agg_by": "CHANGECODE", "agg_limit": 50,
            "sort_by": "PROCDATE", "sort_order": "DESC", "limit": 1,
        })
        if getattr(args, "json", False):
            print(json.dumps(resp, indent=2, default=str))
        elif resp:
            meta = resp.get("meta", {})
            print(f"Total structure events in range: {meta.get('total', 'N/A'):,}")
            print(json.dumps(resp, indent=2, default=str)[:5000])

    elif cmd == "mergers-by-year":
        resp = _get("history", {
            "filters": f'PROCDATE:["{args.start_year}-01-01" TO "{args.end_year}-12-31"] AND CHANGECODE:[110 TO 399]',
            "fields": "INSTNAME,CERT,CHANGECODE,PROCDATE",
            "agg_by": "PROCDATE", "agg_limit": 500,
            "sort_by": "PROCDATE", "sort_order": "DESC", "limit": 1,
        })
        if getattr(args, "json", False):
            print(json.dumps(resp, indent=2, default=str))
        elif resp:
            meta = resp.get("meta", {})
            print(f"Total M&A events: {meta.get('total', 'N/A'):,}")
            print(json.dumps(resp, indent=2, default=str)[:5000])

    elif cmd == "fed-district-banks":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte}",
            "fields": "CERT,REPDTE,ASSET,FED,FEDDESC",
            "agg_by": "FED", "agg_sum_fields": "ASSET",
            "agg_limit": 15, "sort_by": "ASSET", "sort_order": "DESC", "limit": 1,
        })
        if getattr(args, "json", False):
            print(json.dumps(resp, indent=2, default=str))
        elif resp:
            print(json.dumps(resp, indent=2, default=str)[:5000])

    # Specialty
    elif cmd == "specialty-breakdown":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte}",
            "fields": "CERT,REPDTE,ASSET,SPECGRP,SPECGRPDESC",
            "agg_by": "SPECGRP", "agg_sum_fields": "ASSET",
            "agg_limit": 15, "sort_by": "ASSET", "sort_order": "DESC", "limit": 1,
        })
        if getattr(args, "json", False):
            print(json.dumps(resp, indent=2, default=str))
        elif resp:
            print(json.dumps(resp, indent=2, default=str)[:5000])

    elif cmd == "ag-banks":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND SPECGRP:2 AND ASSET:[{args.min_assets} TO *]",
            "fields": "CERT,REPDTE,ASSET,LNAG,LNREAG,LNLSNET,EQTOT,IDT1CER,NTAG,NTAGR,P9AG,NAAG,ROA,SPECGRPDESC",
            "sort_by": "LNAG", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"ag_banks_{args.repdte}")

    elif cmd == "credit-card-banks":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND SPECGRP:3",
            "fields": "CERT,REPDTE,ASSET,LNCRCD,LNCRCDRP,LNCON,LNLSNET,EQTOT,NTCRCD,NTCRCDR,P9CRCD,NACRCD,ROA,SPECGRPDESC",
            "sort_by": "LNCRCD", "sort_order": "DESC", "limit": 50,
        })
        _ni_output(resp, args, f"credit_card_banks_{args.repdte}")

    elif cmd == "trust-banks":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND IFIDUC:[{args.min_ifiduc} TO *]",
            "fields": "CERT,REPDTE,ASSET,TFRA,NFAA,IFIDUC,TNI,TETOT,TRUST,TRUSTPWR",
            "sort_by": "TFRA", "sort_order": "DESC", "limit": 50,
        })
        _ni_output(resp, args, f"trust_banks_{args.repdte}")

    elif cmd == "mortgage-originators":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND INTANMSR:[{args.min_msr} TO *]",
            "fields": "CERT,REPDTE,ASSET,INTANMSR,INTANMSRR,LNSERV,LNLSSALE,LNREPP,MTGLS,LNRERES",
            "sort_by": "INTANMSR", "sort_order": "DESC", "limit": 50,
        })
        _ni_output(resp, args, f"mortgage_originators_{args.repdte}")

    elif cmd == "ppp-exposure":
        resp = _get("financials", {
            "filters": f"REPDTE:{args.repdte} AND PPPLNBAL:[{args.min_ppp} TO *]",
            "fields": "CERT,REPDTE,ASSET,PPPLNBAL,PPPLNNUM,PPPLNPLG,PPPLF1LS,PPPLFOV1,AVPPPPLG,MMLFBAL",
            "sort_by": "PPPLNBAL", "sort_order": "DESC", "limit": 100,
        })
        _ni_output(resp, args, f"ppp_exposure_{args.repdte}")

    elif cmd == "bank-snapshot":
        repdte = args.repdte
        if not repdte:
            latest = _get("financials", {
                "filters": f"CERT:{args.cert}",
                "fields": "REPDTE",
                "sort_by": "REPDTE", "sort_order": "DESC", "limit": 1,
            })
            rows, _ = _extract_rows(latest)
            if not rows:
                print(f"No financials found for CERT {args.cert}")
                return
            repdte = str(rows[0].get("REPDTE"))

        sections = [
            ("institution_profile", FINANCIAL_FIELDS["institution_profile"]),
            ("balance_sheet", FINANCIAL_FIELDS["balance_sheet"]),
            ("income", FINANCIAL_FIELDS["income"]),
            ("deposits_detail", FINANCIAL_FIELDS["deposits_detail"]),
            ("loans", FINANCIAL_FIELDS["loans"]),
            ("credit_quality", FINANCIAL_FIELDS["credit_quality"]),
            ("capital_basel", FINANCIAL_FIELDS["capital_basel"]),
            ("cre", FINANCIAL_FIELDS["cre"]),
            ("unrealized_securities", FINANCIAL_FIELDS["unrealized_securities"]),
            ("derivatives", FINANCIAL_FIELDS["derivatives"]),
            ("ratios", FINANCIAL_FIELDS["ratios"]),
        ]

        snapshot = {"cert": args.cert, "repdte": repdte, "sections": {}}
        for key, fields in sections:
            resp = _get("financials", {
                "filters": f"CERT:{args.cert} AND REPDTE:{repdte}",
                "fields": fields, "limit": 1,
            })
            rows, _ = _extract_rows(resp)
            snapshot["sections"][key] = rows[0] if rows else {}

        if getattr(args, "json", False):
            print(json.dumps(snapshot, indent=2, default=str))
        else:
            print(f"\n=== Bank Snapshot: CERT {args.cert}, REPDTE {repdte} ===\n")
            for key, _ in sections:
                print(f"\n--- {key} ---")
                row = snapshot["sections"].get(key)
                if row:
                    _print_table([row])

    elif cmd == "field-catalog":
        for ep, cat in FIELD_CATALOGS.items():
            print(f"\n/{ep}:")
            for name, fields in cat.items():
                print(f"  {name:15s} -> {fields}")

    else:
        print(f"Unknown command: {cmd}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command:
        run_noninteractive(args)
    else:
        print("\n  FDIC BankFind Suite API Explorer")
        print("  ================================")
        print(f"  Base URL: {BASE}")
        print(f"  Docs:     https://api.fdic.gov/banks/docs/")
        print(f"  No API key required - all endpoints are public.")
        print(f"  All filters use Elasticsearch query syntax. Field names are UPPERCASE.")
        interactive_loop()


if __name__ == "__main__":
    main()

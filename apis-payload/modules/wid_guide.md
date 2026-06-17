# World Inequality Database (WID.world)

Sandbox name: `wid_client`
Base URL: `https://rfap9nitz6.execute-api.eu-west-1.amazonaws.com/prod/`
Auth: `x-api-key` header (base64-encoded). Optional `WID_API_KEY` env override (hex).
Transport: Bucket C — plain `requests` (no GS proxy).
Ontology: this module is the SSOT for WID code grammar, dimension tables, concept taxonomy, and universe-traversal patterns. The client is thin HTTP + chunking only.

## Triggers

**Primary** — Income and wealth inequality within and across countries: top 1% / top 10% / bottom 50% shares, Gini coefficients, thresholds, averages, wealth-to-income ratios, fiscal vs pre-tax vs post-tax income concepts, long-run distributional national accounts (DINA), regional/subnational inequality (US states), carbon inequality footprints, PPP/MER exchange rates and deflators.

**Not for** — High-frequency market data (FRED), US bank microdata (FDIC), household surveys without top-tail correction (World Bank / OECD survey-only portals), Canadian official stats (StatCan), cross-border banking (BIS). WID is annual (sometimes multi-decade history), inequality-focused, and uses fiscal+survey+NA combinations.

## Code grammar

Every series is a **four-part code** joined for the API:

```
{sixlet}_{percentile}_{age}_{pop}
```

Example: `sptinc_p99p100_999_i` = share of pre-tax national income (`s`+`ptinc`) for the top 1% (`p99p100`), all ages (`999`), individuals (`i`).

The **sixlet** = series-type letter (1) + concept code (5). The output `variable` column concatenates sixlet+age+pop (e.g. `sptinc999i`); `percentile` stays separate.

| Part | Example | Meaning |
|------|---------|---------|
| sixlet | `sptinc` | `s` (share) + `ptinc` (pre-tax national income) |
| percentile | `p99p100` | top 1% of distribution |
| age | `999` | all ages (992 = adults 20+) |
| pop | `i` | individuals (`j` = equal-split adults, `t` = tax units) |

**Units:** shares / Gini / female share are **fractions of 1** (0.19 = 19%). Monetary series are local currency at last year's prices for countries; regional aggregates use `XX-MER` or `XX-PPP` suffix areas.

## Series types (first letter of sixlet)

| Code | Meaning | Unit |
|------|---------|------|
| `a` | average | local currency, last year's prices |
| `b` | inverted Pareto-Lorenz coefficient | unitless |
| `f` | female population share | fraction 0–1 |
| `g` | Gini coefficient | 0–1 |
| `i` | index | unitless |
| `n` | population | people |
| `s` | share | fraction 0–1 |
| `t` | threshold | local currency |
| `m` | total | local currency |
| `p` | proportion of women | fraction 0–1 |
| `w` | wealth-to-income or labor/capital share | fraction of national income |
| `y` | wealth-to-GDP ratio | fraction of GDP |
| `r` | top 10 / bottom 50 ratio | unitless |
| `x` | exchange rate (market or PPP) | LCU per foreign currency |
| `e` | total emissions | tons CO2e |
| `k` | per capita emissions | tons CO2e |
| `l` | average group emissions | tons CO2e per capita |

## Population units (`pop`)

| Code | Description |
|------|-------------|
| `i` | individuals |
| `j` | equal-split adults (income/wealth split equally among spouses) |
| `m` | male |
| `f` | female |
| `t` | tax unit (household) |
| `e` | employed |

## Age codes

| Code | Description |
|------|-------------|
| `999` | all ages |
| `992` | adults (20+) |
| `996` | working age (20–64) |
| `991` | below 20 |
| `997` | 65+ |
| `156` | 15–64 |
| `014` | 0–14 |

Additional 5- and 10-year bands (`201`–`951`, `202`–`902`, etc.) exist — see concept table and https://wid.world/codes-dictionary/.

## Percentile grammar

Form: `pXX` or `pXXpYY`. Key groups: `p0p50` (bottom 50%), `p90p100` (top 10%), `p99p100` (top 1%), `p0p100` (whole distribution / non-distributional aggregates).

**Ranking caveat:** for income subcomponents, `p99p100` may rank on total income OR subcomponent only — check metadata.

## Headline macro concepts (fast path)

| Concept | Code | Typical sixlets | Question |
|---------|------|-----------------|----------|
| Pre-tax national income | `ptinc` | `sptinc`, `aptinc`, `tptinc`, `gptinc` | Top shares, Gini |
| Fiscal income | `fiinc` | `sfiinc`, `afiinc` | Post-fiscal inequality |
| Post-tax disposable | `diinc` | `sdiinc` | After tax/transfer |
| Net personal wealth | `hweal` | `shweal`, `ahweal` | Wealth inequality |
| National income | `nninc` | `anninc`, `mnninc` | Macro per capita |
| Gross national income | `gninc` | `agninc`, `mgninc` | NI level / per capita |
| Labour / capital share | `lsgdp` / `csgdp` | `ylsgdp`, `ycsgdp` | Factor income shares of GDP |
| Price index | `inyixx` | `iinyixx` | Reference year (=1) |
| USD PPP FX | `lcusp` | `xlcusp` | PPP conversion (LCU→PPP USD) |
| USD market FX | `lcusx` | `xlcusx` | Market exchange rate (LCU per USD) |
| Real exchange rate | `rerus` | `xrerus` | Real FX vs USD |
| Carbon footprint | `pfghg` | `lpfghg`, `kpfghg` | Emissions inequality |

## Universe traversal patterns

Cannot use `indicators=all` AND `areas=all` together. Pick a discovery axis:

| Intent | Discovery | Size hint |
|--------|-----------|-----------|
| All series for US | `list_available("US", "all")` | ~300 KB |
| Top-share globally | `list_available("all", "sptinc")` + filter | ~5 MB |
| Small multi-country | `list_available(["US","FR","DE"], "gptinc")` | small |

```python
avail = wid_client.list_available(["US", "FR"], "sptinc")
rows = wid_client.download_wid(
    indicators=["sptinc"], areas=["US", "FR"],
    perc=["p99p100"], ages=["999"], pop=["i"], metadata=True,
)
df = wid_client.series_to_dataframe(rows)
code = wid_client.build_variable("sptinc", "p99p100", "999", "i")
rows = wid_client.get_data("US", code)
```

Regional aggregates: `NA`, `SA`, `AF`, plus `XN-PPP`, `XR-MER`, `OA-MER` suffix areas. Discovery is authoritative.

## Schemas

`list_available` → `country`, `variable`, `percentile`, `age`, `pop`, `data_code`.

`download_wid` / `get_data` → `country`, `variable`, `percentile`, `year`, `value` (+ `unit`, `quality`, `imputation` when present).

With `metadata=True` → adds `countryname`, `shortname`, `shortdes`, `technicaldes`, `source`, `method`.

## Format quirks

- Shares are fractions 0–1.
- Year filter is client-side (`years` kwarg on `download_wid`).
- `countries=all` discovery: 10–20s per indicator.
- Full database: https://wid.world/data/ bulk download only.

## Domain semantics

- `ptinc` = pre-tax national income (primary inequality concept).
- `j` = equal-split adults (WID website default for households).
- `iinyixx999i` = 1 in the reference year.
- Regional amounts: `XX-PPP` or `XX-MER` suffix on area code.

---

## Macro & finance concepts (live, beyond the published dictionary)

WID's published codes dictionary lists 428 concepts (the table below); the
**live API exposes ~480** — `list_available(country, "all")` is the
**authoritative** enumeration of what is retrievable, and these macro/finance
concepts (queryable today but absent from the published dictionary) are the
highest-value of the extras. Same four-part grammar — pick a series-type
letter and assemble `{sixlet}_{percentile}_{age}_{pop}` (most are
non-distributional, so use `p0p100`).

| Concept | Typical sixlet(s) | Description |
|---------|-------------------|-------------|
| `lsgdp` | `ylsgdp` | Labour share of GDP (% of GDP) |
| `csgdp` | `ycsgdp` | Capital share of GDP (% of GDP) |
| `lsgni` / `csgni` | `wlsgni` / `wcsgni` | Labour / capital share of gross national income (% of NNI) |
| `lsnni` / `csnni` | `wlsnni` / `wcsnni` | Labour / capital share of net national income (% of NNI) |
| `gninc` | `agninc`, `mgninc` | Gross national income (average per adult / total) |
| `lcusp` | `xlcusp` | USD PPP conversion factor (LCU → PPP USD) |
| `lcusx` | `xlcusx` | USD market exchange rate (LCU per USD) |
| `lceup` / `lcyup` | `xlceup` / `xlcyup` | EUR / CNY PPP conversion factor |
| `rerus` / `rereu` / `reryu` | `xrerus` / `xrereu` / `xreryu` | Real exchange rate, LCU vs USD / EUR / CNY |
| `nwnat` / `pwnat` | `mnwnat` / `mpwnat` | National / private natural capital (market value) |
| `nwfin` / `nwdeb` | `mnwfin` / `mnwdeb` | National financial assets / liabilities |
| `popul` / `popem` | `npopul` / `npopem` | Population / employed population (number of individuals) |
| `nyixx` | `inyixx` | National income deflator (price index) |
| `quali` | `iquali` | Data-quality index (survey + tax availability) |

For anything else not in either list, discover with
`list_available(country, "all")` and read each variable's meaning from
`get_metadata(country, code)` (the `shortdes` / `shorttype` fields).

## Concept codes (428 five-letter codes — WID published dictionary)

| Code | Description |
|------|-------------|
| `cainc` | (=) post-tax disposable income |
| `ccmhn` | (+) CFC of mixed income of household sector |
| `ccmho` | (+) consumption of fixed capital attributable to mixed income |
| `ccshn` | (+) CFC of operating surplus of household sector |
| `ccsho` | (+) consumption of fixed capital attributable to operating surplus |
| `ceuco` | (+) compensation of employees of the corporate sector |
| `ceugo` | (+) compensation of employees of the government |
| `ceuhn` | (+) compensation of employees of household sector |
| `cfcco` | (+) CFC income of corporations |
| `cfcfc` | (+) CFC of financial corporations |
| `cfcgo` | (+) CFC of the general government |
| `cfchn` | (+) CFC of households and NPISH |
| `cfcho` | (+) CFC of households |
| `cfcnf` | (+) CFC of non-financial corporations |
| `cfcnp` | (+) CFC of NPISH |
| `cfghg` | (+) Personal carbon footprint (consumption only) |
| `citgr` | (+) corporate income tax |
| `colgo` | (+) collective consumption expenditure |
| `comhn` | (+) compensation of employees |
| `comho` | (+) compensation of employees |
| `comnp` | (+) compensation of employees |
| `comnx` | (+) net foreign labor income |
| `compx` | (+) compensation of employees paid to the rest of the world |
| `comrx` | (+) compensation of employees received from the rest of the world |
| `confc` | (-) consumption of fixed capital |
| `congo` | (-) final consumption expenditures |
| `conhn` | (-) private expenditures of households and NPISH |
| `conho` | (-) private expenditures of households |
| `connp` | (-) private expenditures of NPISH |
| `cwagr` | (+) agricultural land |
| `cwbol` | (+) bonds and loans |
| `cwboo` | (=) book value of corporations |
| `cwbus` | (+) corporate business and other non-financial assets |
| `cwcud` | (+) currency and deposits |
| `cwdeb` | (-) corporate debt (non-equity liability) |
| `cwdeq` | (=) market value of corporations (equity liability) |
| `cwdwe` | (+) dwellings |
| `cweqi` | (+) equities and fund shares |
| `cwfie` | (=) financial assets except for currency and deposits |
| `cwfin` | (+) financial assets |
| `cwfiw` | (+) currency, deposits, bonds, and loans |
| `cwhou` | (+) corporate housing assets |
| `cwlan` | (+) land underlying dwellings |
| `cwnfa` | (+) corporate non-financial assets |
| `cwodk` | (+) other domestic capital |
| `cwpen` | (+) pension funds and life insurance |
| `cwres` | (+) residual corporate wealth |
| `defge` | (+) defense |
| `defgo` | (+) defense |
| `diinc` | (=) post-tax national income |
| `ecoge` | (+) economic affairs |
| `ecogo` | (+) economic affairs |
| `edpge` | (+) education: Primary |
| `edsge` | (+) education: Secondary |
| `edtge` | (+) education: Tertiary |
| `eduge` | (+) education |
| `edugo` | (+) education |
| `envge` | (+) environment protection |
| `envgo` | (+) environment protection |
| `expgo` | (=) total public spending (excl. interest payment) |
| `fainc` | (=) factor national income |
| `fdinx` | (+) net foreign direct investment income |
| `fdipx` | (+) foreign direct investment income |
| `fdirx` | (+) foreign direct investment income |
| `fdixa` | (+) Foreign direct investments assets |
| `fdixd` | (-) Foreign direct investments liabilities |
| `fdixn` | (+) Net foreign direct investment |
| `ficap` | (+) fiscal capital income |
| `fidiv` | (+) dividends |
| `fiinc` | (=) fiscal income |
| `fiint` | (+) interests |
| `fikgi` | (+) capital gains |
| `filin` | (+) fiscal labor income |
| `fimik` | (+) capital component of mixed-income |
| `fimil` | (+) labor component of mixed-income |
| `fimix` | (=) mixed-income |
| `finpx` | (-) foreign income paid to the rest of the world |
| `finrx` | (+) foreign income received from the rest of the world |
| `firen` | (+) rents |
| `fiwag` | (+) wage and pensions |
| `fkanx` | (=) Capital Account |
| `fkapx` | (-) Capital transfers paid to the rest of the world |
| `fkarx` | (+) Capital transfers received from the rest of the world |
| `fkpin` | (+) net capital income |
| `flcin` | (+) net foreign labor and capital income |
| `flcip` | (+) labor and capital income paid to the rest of the world |
| `flcir` | (+) labor and capital income from the rest of the world |
| `flinc` | (=) labor factor income |
| `fosub` | (+) other subsidies on production |
| `fotax` | (+) other taxes on production |
| `fpsub` | (+) subsidies on products |
| `fptax` | (+) taxes on products |
| `fsubx` | (+) subsidies on prod. received from the rest of the world |
| `ftaxx` | (+) taxes on prod. paid to the rest of the world |
| `gdpro` | (+) gross domestic product |
| `gfcar` | (+) Government CO2 footprint |
| `gfghg` | (+) Government carbon footprint |
| `gfgho` | (+) Government footprint of other gases |
| `gicar` | (+) Government imported CO2 emissions |
| `gighg` | (+) Government imported emissions |
| `gigho` | (+) Government imported emissions of other gases |
| `gmxhn` | (+) gross mixed income of household sector |
| `gmxho` | (+) gross mixed income |
| `gpsge` | (+) general public services (excl. interest payment) |
| `gpsgo` | (+) general public services |
| `gsmhn` | (+) gross operating surplus and mixed income |
| `gsmho` | (+) gross operating surplus and mixed income |
| `gsrco` | (+) gross operating surplus of the corporate sector |
| `gsrfc` | (+) gross operating surplus |
| `gsrgo` | (+) gross operating surplus of the government |
| `gsrhn` | (+) gross operating surplus of household sector |
| `gsrho` | (+) gross operating surplus |
| `gsrnf` | (+) gross operating surplus |
| `gsrnp` | (+) gross operating surplus and mixed income |
| `gvaco` | (+) gross value added of the corporate sector |
| `gvago` | (+) gross value added of the government |
| `gvahn` | (+) gross value added of household sector |
| `gvato` | (+) gross domestic product at factor-price |
| `gwagr` | (+) agricultural land |
| `gwbol` | (+) bonds and loans |
| `gwbus` | (+) government business and other non-financial assets |
| `gwcud` | (+) currency and deposits |
| `gwdeb` | (-) liabilities |
| `gwdec` | (=) consolidated government debt |
| `gwdwe` | (+) dwellings |
| `gweal` | (=) net wealth of the general government |
| `gweqi` | (+) equities and fund shares |
| `gwfie` | (=) financial assets except for currency and deposits |
| `gwfin` | (+) financial assets |
| `gwfiw` | (+) currency, deposits, bonds, and loans |
| `gwhou` | (+) government housing assets |
| `gwlan` | (+) land underlying dwellings |
| `gwnfa` | (+) government non-financial assets |
| `gwodk` | (+) other domestic capital |
| `gwpen` | (+) pension funds and life insurance |
| `heage` | (+) health |
| `heago` | (+) health |
| `hfcar` | (+) Household indirect CO2 footprint |
| `hfghd` | (+) Household direct emissions |
| `hfghg` | (+) Household carbon footprint |
| `hfghn` | (+) Household indirect carbon footprint |
| `hfgho` | (+) Household indirect footprint of other gases |
| `hicar` | (+) Household imported CO2 emissions |
| `highg` | (+) Household imported carbon emissions |
| `higho` | (+) Household imported emissions of other gases |
| `houge` | (+) housing and community amenities |
| `hougo` | (+) housing and community amenities |
| `hwagr` | (+) agricultural land |
| `hwbol` | (+) bonds and loans |
| `hwbus` | (+) household business and other non-financial assets |
| `hwcud` | (+) currency and deposits |
| `hwdeb` | (-) liabilities |
| `hwdwe` | (+) dwellings |
| `hweal` | (=) household net wealth |
| `hweqi` | (+) equities and fund shares |
| `hwfie` | (=) financial assets except for currency and deposits |
| `hwfin` | (+) financial assets |
| `hwfiw` | (+) currency, deposits, bonds, and loans |
| `hwhou` | (+) household housing assets |
| `hwlan` | (+) land underlying dwellings |
| `hwnfa` | (+) household non-financial assets |
| `hwodk` | (+) other domestic capital |
| `hwpen` | (+) pension funds and life insurance |
| `ifcar` | (+) Investment CO2 footprint |
| `ifghg` | (+) Investment carbon footprint |
| `ifgho` | (+) Investment footprint of other gases |
| `iicar` | (+) Investment imported CO2 emissions |
| `iighg` | (+) Investment imported carbon emissions |
| `iigho` | (+) Investment imported emissions of other gases |
| `index` | no unit |
| `indgo` | (+) individual consumption expenditures |
| `inpgo` | (-) interest paid by the government |
| `intgr` | (+) indirect taxes |
| `iwagr` | (+) agricultural land |
| `iwbol` | (+) bonds and loans |
| `iwbus` | (+) non-profit institutions’ business and other non-financial assets |
| `iwcud` | (+) currency and deposits |
| `iwdeb` | (-) liabilities |
| `iwdwe` | (+) dwellings |
| `iweal` | (=) non-profit institutions’ net wealth |
| `iweqi` | (+) equities and fund shares |
| `iwfie` | (=) financial assets except for currency and deposits |
| `iwfin` | (+) financial assets |
| `iwfiw` | (+) currency, deposits, bonds, and loans |
| `iwhou` | (+) non-profit institutions’ housing assets |
| `iwlan` | (+) land underlying dwellings |
| `iwnfa` | (+) non-profit institutions’ non-financial assets |
| `iwodk` | (+) other domestic capital |
| `iwpen` | (+) pension funds and life insurance |
| `ncanx` | (=) Current Account = pinnx + comnx + tbnnx + taxnx + scinx |
| `ndpro` | (+) net domestic product |
| `necar` | (+) National exported CO2 emissions |
| `neghg` | (=) National exported carbon emissions |
| `negho` | (+) National exported emissions of other gases |
| `nfcar` | (+) National CO2 footprint |
| `nfghg` | (=) National carbon footprint |
| `nfgho` | (+) National footprint of other gases |
| `nicar` | (+) National imported CO2 emissions |
| `nighg` | (=) National imported carbon emissions |
| `nigho` | (+) National imported emissions of other gases |
| `nmxhn` | (+) net mixed income of household sector |
| `nmxho` | (+) net mixed income of households |
| `nncar` | (+) National net imports of CO2 emissions |
| `nnfin` | (+) foreign income |
| `nnghg` | (=) National net imports of carbon emissions |
| `nngho` | (+) National net imports of other gases |
| `nninc` | (=) net national income |
| `nsmhn` | (+) net operating surplus and mixed income |
| `nsmho` | (+) net operating surplus and mixed income |
| `nsrco` | (+) net operating surplus of the corporate sector |
| `nsrfc` | (+) net operating surplus |
| `nsrgo` | (+) Net operating surplus of the government (=0) |
| `nsrhn` | (+) net operating surplus of the households and NPISH |
| `nsrho` | (+) net operating surplus |
| `nsrnf` | (+) net operating surplus |
| `nsrnp` | (+) net operating surplus |
| `ntcar` | (+) National territorial CO2 emissions |
| `ntcna` | (+) Territorial emissions of the national productive sector and other emissions not attributed to households (CO2) |
| `ntghg` | (=) National territorial carbon emissions |
| `ntgho` | (+) National territorial emissions of other gases |
| `ntgna` | (+) Territorial emissions of the national productive sector and other emissions not attributed to households |
| `ntona` | (+) Territorial emissions of the national productive sector and other emissions not attributed to households (Other gases) |
| `ntrgr` | (+) non-tax revenue |
| `nwagr` | (+) agricultural land |
| `nwboo` | (=) book-value national wealth |
| `nwbus` | (+) national business and other non-financial assets |
| `nwdka` | (=) domestic capital |
| `nwdwe` | (+) dwellings |
| `nweal` | (=) net market-value national wealth |
| `nwgxa` | (+) gross foreign assets |
| `nwgxd` | (-) gross foreign liabilities |
| `nwhou` | (+) national housing assets |
| `nwlan` | (+) land underlying dwellings |
| `nwnfa` | (+) national non-financial assets |
| `nwnxa` | (=) Net foreign assets |
| `nwodk` | (+) other domestic capital |
| `ofcar` | (+) NGO CO2 footprint |
| `ofghg` | (+) NGO carbon footprint |
| `ofgho` | (+) NGO footprint of other gases |
| `oicar` | (+) NGO imported CO2 emissions |
| `oighg` | (+) NGO imported carbon emissions |
| `oigho` | (+) NGO imported emissions of other gases |
| `optxn` | (+) other subsidies less taxes on production |
| `ospgo` | (+) other subsidies on production |
| `othgo` | (+) other government spending |
| `otpgp` | (+) other taxes on production |
| `ottgr` | (+) other taxes |
| `pfcar` | (=) Personal CO2 footprint |
| `pfghg` | (=) Personal carbon footprint |
| `pinnx` | (+) net foreign capital income |
| `pinpx` | (+) property income paid to the rest of the world |
| `pinrx` | (+) property income received from the rest of the world |
| `pitgr` | (+) personal income tax |
| `pkkin` | (+) pretax capital income |
| `pllin` | 992 |
| `polge` | (+) public order and safety |
| `polgo` | (+) public order and safety |
| `prgco` | (=) gross primary income of corporations |
| `prgfc` | (=) gross primary income of financial corporations |
| `prggo` | (=) gross primary income of the general government |
| `prghn` | (=) gross primary income of households and NPISH |
| `prgho` | (=) gross primary income of households |
| `prgnf` | (=) gross primary income of non-financial corporations |
| `prgnp` | (=) gross primary income of NPISH |
| `prico` | (+) net primary income of corporations |
| `prifc` | (+) net primary income of financial corporations |
| `prigo` | (+) net primary income of the general government |
| `prihn` | (+) net primary income of households and non-profits |
| `priho` | (+) net primary income of households |
| `prinf` | (+) net primary income of non-financial corporations |
| `prinp` | (+) net primary income of non-profits |
| `prpco` | (+) property income of corporations |
| `prpfc` | (+) property income (net) |
| `prpgo` | (+) property income of the government |
| `prphn` | (+) property income of households and NPISH |
| `prpho` | (+) property income (net) |
| `prpnf` | (+) property income (net) |
| `prpnp` | (+) property income (net) |
| `prtxn` | (+) subsidies less taxes on products |
| `psugo` | (=) primary surplus of the government |
| `ptdnx` | (+) net debt income |
| `ptdpx` | (+) debt income |
| `ptdrx` | (+) debt income |
| `ptdxa` | (+) Portfolio debt assets |
| `ptdxd` | (+) Portfolio debt liabilities |
| `ptenx` | (+) net equity income |
| `ptepx` | (+) equity income |
| `pterx` | (+) equity income |
| `ptexa` | (+) Portfolio equity assets |
| `ptexd` | (+) Portfolio equity liabilities |
| `ptfnx` | (+) net portfolio income |
| `ptfpx` | (+) portfolio and other income |
| `ptfrn` | (+) net reinvested earnings on foreign portfolio investment |
| `ptfrp` | (+) reinvested earnings on foreign portfolio investment |
| `ptfrr` | (+) reinvested earnings on foreign portfolio investment |
| `ptfrx` | (+) portfolio and other income |
| `ptfxa` | (+) Portfolio assets |
| `ptfxd` | (-) Portfolio liabilities |
| `ptfxn` | (+) Net foreign portfolio |
| `ptinc` | (=) pre-tax national income |
| `ptkin` | (+) pretax capital income |
| `ptlin` | (+) pretax labor income |
| `ptrrx` | (+) reserves income |
| `ptrxa` | (+) Foreign reserve exchange assets |
| `ptxgo` | (+) taxes on products and production |
| `pwagr` | (+) agricultural land |
| `pwbol` | (+) bonds and loans |
| `pwbus` | (+) private business and other non-financial assets |
| `pwcud` | (+) currency and deposits |
| `pwdeb` | (-) liabilities |
| `pwdwe` | (+) dwellings |
| `pweal` | (=) private net wealth |
| `pweqi` | (+) equities and fund shares |
| `pwfie` | (=) financial assets except for currency and deposits |
| `pwfin` | (+) financial assets |
| `pwfiw` | (+) currency, deposits, bonds, and loans |
| `pwhou` | (+) private housing assets |
| `pwlan` | (+) land underlying dwellings |
| `pwnfa` | (+) private non-financial assets |
| `pwodk` | (+) other domestic capital |
| `pwoff` | (+) offshore wealth |
| `pwpen` | (+) pension funds and life insurance |
| `pwtgr` | (+) property and wealth taxes |
| `recge` | (+) recreation, culture and religion |
| `recgo` | (+) recreation, culture and religion |
| `retgo` | (=) total public revenue (excl. non-tax revenue) |
| `revgo` | (=) total public revenue |
| `sacge` | (+) social protection: social assistance in cash |
| `sagco` | (+) gross savings/secondary income of corporations |
| `saggo` | (+) gross savings of the general government |
| `saghn` | (+) gross savings of households and NPISH |
| `sagho` | (+) gross savings of households |
| `sagnp` | (+) gross savings of NPISH |
| `sakge` | (+) social protection: social assistance in kind |
| `savco` | (+) net savings/secondary income of corporations |
| `savgo` | (+) net savings of the general government |
| `savhn` | (+) net savings of households and NPISH |
| `savho` | (+) net savings of households |
| `savig` | (=) gross savings of the total economy |
| `savin` | (=) net savings of the total economy |
| `savnp` | (+) net savings of NPISH |
| `scgnx` | (+) Net public foreign transfers |
| `scgpx` | (-) Public foreign transfers paid to the rest of the world |
| `scgrx` | (+) Public foreign transfers received from the rest of the world |
| `scinx` | (+) Net foreign transfers |
| `scipx` | (-) Foreign transfers paid to the rest of the world |
| `scirx` | (+) Foreign transfers received from the rest of the world |
| `scogr` | (+) social contributions |
| `sconx` | (+) Net other foreign transfers |
| `scopx` | (-) Other foreign transfers paid to the rest of the world |
| `scorx` | (+) Other foreign transfers received from the rest of the world |
| `scrnx` | (+) Net remittances |
| `scrpx` | (-) Remittances paid to the rest of the world |
| `scrrx` | (+) Remittances received from the rest of the world |
| `secco` | (+) net secondary income of corporations |
| `secfc` | (+) net secondary income of financial corporations |
| `secgo` | (+) net secondary income of the general government |
| `sechn` | (+) net secondary income of households and non-profits |
| `secho` | (+) net secondary income of households |
| `secnf` | (+) net secondary income of non-financial corporations |
| `secnp` | (+) net secondary income of non-profits |
| `segco` | (=) gross secondary income/gross saving of corporations |
| `segfc` | (+) gross savings of financial corporations |
| `seggo` | (=) gross secondary income of the general government |
| `seghn` | (=) gross secondary income of households and NPISH |
| `segho` | (=) gross secondary income of households |
| `segnf` | (+) gross savings of non-financial corporations |
| `segnp` | (=) gross secondary income of NPISH |
| `share` | income |
| `sopge` | (+) social protection |
| `sopgo` | (+) social protection |
| `spige` | (+) social protection: social insurance |
| `spigo` | (-) subsidies on production and imports |
| `sprgo` | (+) subsidies on products |
| `ssbco` | (+) social benefits from private employer social insurance |
| `ssbfc` | (-) social benefits from private employer social insurance |
| `ssbgo` | (+) social benefits paid by the government |
| `ssbhn` | (=) social benefits received by households and NPISH |
| `ssbho` | (+) social benefits other than social transfers in kind |
| `ssbnf` | (-) social benefits from private employer social insurance |
| `ssbnp` | (+) social benefits other than social transfers in kind |
| `sscco` | (+) social contributions to private employer social insurance |
| `sscfc` | (+) social contributions to private employer social insurance |
| `sscgo` | (+) social contributions received by the government |
| `sschn` | (=) social contributions paid by households and NPISH |
| `sscho` | (+) social contributions |
| `sscnf` | (+) social contributions to private employer social insurance |
| `sscnp` | (+) social contributions |
| `ssugo` | (=) secondary surplus of the government |
| `taxco` | (+) corporate tax |
| `taxfc` | (-) corporate tax |
| `taxgo` | (=) direct taxes received by the government |
| `taxhn` | (-) direct taxes |
| `taxho` | (-) direct taxes |
| `taxnf` | (-) corporate tax |
| `taxnp` | (-) direct taxes |
| `taxnx` | (+) subsidies less taxes on production and imports |
| `tbmpx` | (-) Imports of goods and services |
| `tbnnx` | (+) Trade balance (exports-imports) |
| `tbxrx` | (+) Exports of goods and services |
| `tgmcx` | (-) Imports of primary commodities |
| `tgmmx` | (-) Imports of manufacturing goods |
| `tgmpx` | (-) Imports of goods |
| `tgncx` | (+) Trade balance of primary commodities (exports-imports) |
| `tgnmx` | (+) Trade balance of manufacturing goods (exports-imports) |
| `tgnnx` | (+) Trade balance of goods (exports-imports) |
| `tgxcx` | (+) Exports of primary commodities |
| `tgxmx` | (+) Exports of manufacturing goods |
| `tgxrx` | (+) Exports of goods |
| `tiwgo` | (+) direct taxes on income and wealth |
| `tiwhn` | (+) taxes on income and wealth paid by households |
| `tiwho` | (+) personal taxes on income and wealth |
| `tiwnp` | (+) personal taxes on income and wealth |
| `total` | local currency unit, last year’s prices |
| `tpigo` | (+) taxes on production and imports |
| `tprgo` | (+) taxes on products |
| `tsmpx` | (-) Imports of services |
| `tsnnx` | (+) Trade balance of services (exports-imports) |
| `tsonx` | (+) Trade balance of other services (exports-imports) |
| `tsopx` | (-) Imports of other services |
| `tsorx` | (+) Exports of other services |
| `tstnx` | (+) Trade balance of transport services (exports-imports) |
| `tstpx` | (-) Imports of transport services |
| `tstrx` | (+) Exports of transport services |
| `tsvnx` | (+) Trade balance of travel services (exports-imports) |
| `tsvpx` | (-) Imports of travel services |
| `tsvrx` | (+) Exports of travel services |
| `tsxrx` | (+) Exports of services |

## Area codes (282 dictionary base)

| Code | Name |
|------|------|
| `AD` | Andorra |
| `AE` | United Arab Emirates |
| `AF` | Afghanistan |
| `AG` | Antigua and Barbuda |
| `AI` | Anguilla |
| `AL` | Albania |
| `AM` | Armenia |
| `AO` | Angola |
| `AR` | Argentina |
| `AT` | Austria |
| `AU` | Australia |
| `AW` | Aruba |
| `AZ` | Azerbaijan |
| `BA` | Bosnia and Herzegovina |
| `BB` | Barbados |
| `BD` | Bangladesh |
| `BE` | Belgium |
| `BF` | Burkina Faso |
| `BG` | Bulgaria |
| `BH` | Bahrain |
| `BI` | Burundi |
| `BJ` | Benin |
| `BM` | Bermuda |
| `BN` | Brunei Darussalam |
| `BO` | Bolivia |
| `BQ` | Bonaire |
| `BR` | Brazil |
| `BS` | Bahamas |
| `BT` | Bhutan |
| `BW` | Botswana |
| `BY` | Belarus |
| `BZ` | Belize |
| `CA` | Canada |
| `CD` | DR Congo |
| `CF` | Central African Republic |
| `CG` | Congo |
| `CH` | Switzerland |
| `CI` | Cote d’Ivoire |
| `CL` | Chile |
| `CM` | Cameroon |
| `CN` | China |
| `CN-RU` | Rural China |
| `CN-UR` | Urban China |
| `CO` | Colombia |
| `CR` | Costa Rica |
| `CS` | Czechoslovakia |
| `CU` | Cuba |
| `CV` | Cabo Verde |
| `CW` | Curacao |
| `CY` | Cyprus |
| `CZ` | Czechia |
| `DD` | German Democratic Republic |
| `DE` | Germany |
| `DE-BD` | Baden |
| `DE-BY` | Bavaria |
| `DE-HB` | Bremen |
| `DE-HE` | Hesse |
| `DE-HH` | Hamburg |
| `DE-PR` | Prussia |
| `DE-SN` | Saxony |
| `DE-WU` | Wurttemberg |
| `DJ` | Djibouti |
| `DK` | Denmark |
| `DM` | Dominica |
| `DO` | Dominican Republic |
| `DZ` | Algeria |
| `EC` | Ecuador |
| `EE` | Estonia |
| `EG` | Egypt |
| `ER` | Eritrea |
| `ES` | Spain |
| `ET` | Ethiopia |
| `FI` | Finland |
| `FJ` | Fiji |
| `FM` | Micronesia |
| `FR` | France |
| `GA` | Gabon |
| `GB` | United Kingdom |
| `GD` | Grenada |
| `GE` | Georgia |
| `GG` | Guernsey |
| `GH` | Ghana |
| `GI` | Gibraltar |
| `GL` | Greenland |
| `GM` | Gambia |
| `GN` | Guinea |
| `GQ` | Equatorial Guinea |
| `GR` | Greece |
| `GT` | Guatemala |
| `GW` | Guinea-Bissau |
| `GY` | Guyana |
| `HK` | Hong Kong |
| `HN` | Honduras |
| `HR` | Croatia |
| `HT` | Haiti |
| `HU` | Hungary |
| `ID` | Indonesia |
| `IE` | Ireland |
| `IL` | Israel |
| `IM` | Isle of Man |
| `IN` | India |
| `IQ` | Iraq |
| `IR` | Iran |
| `IS` | Iceland |
| `IT` | Italy |
| `JE` | Jersey |
| `JM` | Jamaica |
| `JO` | Jordan |
| `JP` | Japan |
| `KE` | Kenya |
| `KG` | Kyrgyzstan |
| `KH` | Cambodia |
| `KI` | Kiribati |
| `KM` | Comoros |
| `KN` | Saint Kitts and Nevis |
| `KP` | North Korea |
| `KR` | South Korea |
| `KS` | Kosovo |
| `KW` | Kuwait |
| `KY` | Cayman Islands |
| `KZ` | Kazakhstan |
| `LA` | Lao PDR |
| `LB` | Lebanon |
| `LC` | Saint Lucia |
| `LI` | Liechtenstein |
| `LK` | Sri Lanka |
| `LR` | Liberia |
| `LS` | Lesotho |
| `LT` | Lithuania |
| `LU` | Luxembourg |
| `LV` | Latvia |
| `LY` | Libya |
| `MA` | Morocco |
| `MC` | Monaco |
| `MD` | Moldova |
| `ME` | Montenegro |
| `MG` | Madagascar |
| `MH` | Marshall Islands |
| `MK` | North Macedonia |
| `ML` | Mali |
| `MM` | Myanmar |
| `MN` | Mongolia |
| `MO` | Macao |
| `MR` | Mauritania |
| `MS` | Montserrat |
| `MT` | Malta |
| `MU` | Mauritius |
| `MV` | Maldives |
| `MW` | Malawi |
| `MX` | Mexico |
| `MY` | Malaysia |
| `MZ` | Mozambique |
| `NA` | Namibia |
| `NC` | New Caledonia |
| `NE` | Niger |
| `NG` | Nigeria |
| `NI` | Nicaragua |
| `NL` | Netherlands |
| `NO` | Norway |
| `NP` | Nepal |
| `NR` | Nauru |
| `NZ` | New Zealand |
| `OM` | Oman |
| `PA` | Panama |
| `PE` | Peru |
| `PF` | French Polynesia |
| `PG` | Papua New Guinea |
| `PH` | Philippines |
| `PK` | Pakistan |
| `PL` | Poland |
| `PR` | Puerto Rico |
| `PS` | Palestine |
| `PT` | Portugal |
| `PW` | Palau |
| `PY` | Paraguay |
| `QA` | Qatar |
| `RO` | Romania |
| `RS` | Serbia |
| `RU` | Russia |
| `RW` | Rwanda |
| `SA` | Saudi Arabia |
| `SB` | Solomon Islands |
| `SC` | Seychelles |
| `SD` | Sudan |
| `SE` | Sweden |
| `SG` | Singapore |
| `SI` | Slovenia |
| `SK` | Slovakia |
| `SL` | Sierra Leone |
| `SM` | San Marino |
| `SN` | Senegal |
| `SO` | Somalia |
| `SR` | Suriname |
| `SS` | South Sudan |
| `ST` | Sao Tome and Principe |
| `SU` | USSR |
| `SV` | El Salvador |
| `SX` | Sint Maarten (Dutch part) |
| `SY` | Syria |
| `SZ` | Eswatini |
| `TC` | Turks and Caicos Islands |
| `TD` | Chad |
| `TG` | Togo |
| `TH` | Thailand |
| `TJ` | Tajikistan |
| `TL` | Timor-Leste |
| `TM` | Turkmenistan |
| `TN` | Tunisia |
| `TO` | Tonga |
| `TR` | Turkiye |
| `TT` | Trinidad and Tobago |
| `TV` | Tuvalu |
| `TW` | Taiwan |
| `TZ` | Tanzania |
| `UA` | Ukraine |
| `UG` | Uganda |
| `US` | USA |
| `US-AK` | Alaska |
| `US-AL` | Alabama |
| `US-AR` | Arkansas |
| `US-AZ` | Arizona |
| `US-CA` | California |
| `US-CO` | Colorado |
| `US-CT` | Connecticut |
| `US-DC` | District of Columbia |
| `US-DE` | Delaware |
| `US-FL` | Florida |
| `US-GA` | Georgia |
| `US-HI` | Hawaii |
| `US-IA` | Iowa |
| `US-ID` | Idaho |
| `US-IL` | Illinois |
| `US-IN` | Indiana |
| `US-KS` | Kansas |
| `US-KY` | Kentucky |
| `US-LA` | Louisiana |
| `US-MA` | Massachusetts |
| `US-MD` | Maryland |
| `US-ME` | Maine |
| `US-MI` | Michigan |
| `US-MN` | Minnesota |
| `US-MO` | Missouri |
| `US-MS` | Mississippi |
| `US-MT` | Montana |
| `US-NC` | North Carolina |
| `US-ND` | North Dakota |
| `US-NE` | Nebraska |
| `US-NH` | New Hampshire |
| `US-NJ` | New Jersey |
| `US-NM` | New Mexico |
| `US-NV` | Nevada |
| `US-NY` | New York |
| `US-OH` | Ohio |
| `US-OK` | Oklahoma |
| `US-OR` | Oregon |
| `US-PA` | Pennsylvania |
| `US-RI` | Rhode Island |
| `US-SC` | South Carolina |
| `US-SD` | South Dakota |
| `US-TN` | Tennessee |
| `US-TX` | Texas |
| `US-UT` | Utah |
| `US-VA` | Virginia |
| `US-VT` | Vermont |
| `US-WA` | Washington |
| `US-WI` | Wisconsin |
| `US-WV` | West Virginia |
| `US-WY` | Wyoming |
| `UY` | Uruguay |
| `UZ` | Uzbekistan |
| `VC` | Saint Vincent and the Grenadines |
| `VE` | Venezuela |
| `VG` | Virgin Islands, British |
| `VN` | Viet Nam |
| `VU` | Vanuatu |
| `WS` | Samoa |
| `YE` | Yemen |
| `YU` | Yugoslavia |
| `ZA` | South Africa |
| `ZM` | Zambia |
| `ZW` | Zimbabwe |
| `ZZ` | Zanzibar |

## Regional aggregate suffixes

API discovery also returns `XX-MER` and `XX-PPP` suffixed areas (e.g. `XN-PPP`, `XR-MER`, `OA-MER`). Use `list_available` to confirm availability for a given indicator.

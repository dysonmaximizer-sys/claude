# Business+ tenant — validated knowledge (recon 2026-07-22)

Read-only probe findings (`engine/probe-bizplus-tenant.py`). This file
is the Business+ counterpart of CLAUDE.md's "Validated tenant
knowledge" — nothing from the FSE tenant applies here unless re-proven.

## Users (rule 10)

- **LDYSON exists here too and is WORSE:** DisplayName "Lewis Dyson"
  (FSE at least masked it as Barb Smith). Never leave owner defaults;
  Lewis should rename this account's display + first/last in this
  tenant's Administrator, or record with another login.
- Clean demo identities: **MASTER = "Michelle Boone"** (interim rule-10
  owner, key `VXNlcglNQVNURVI=` — same key string as FSE's MASTER),
  Amanda Brown (ABROWN), Douglas Ceron (DCERON), David Canter (DMTC),
  Jane Smith (JSMITH), John Doe (MAX). A real team exists for
  assignment variety in sales stories.
- No Business+ persona defined in the persona library yet (Adam/Ingrid
  are FA/insurance). Owner persona TBD with Lewis; audience is VP
  Sales / SMB.

## Book shape

204 entries: 100 Companies + 103 Contacts + 1 Individual. B2B shape
(companies with contacts), looks like standard Maximizer sample data.
No households. Demo-plausible volume (rule-1 guard passed).

## Schema (what exists that FSE lacks)

84 roots including: **Lead**, **Quota\*** (QuotaRevenue/Activity/
Milestone), **SalesCoaching\***, **Campaign**, **Case** (customer
service), **Territory**, **Workflow\***, SalesProcess/SalesStage.
Sales-pipeline edition through and through.

## Fields

- Only 128 AbEntry fields (FSE: 630). ONE UDF folder: "Sales" (7
  fields — enumerate before use). NO Segmentation, NO Birthdate UDF,
  NO KYC/insurance anything. Do not reference FSE UDFs here.
- **Sales processes: EMPTY list.** Opportunity mandatory fields unknown
  — probe a create before seeding opportunities (FSE's
  Leader/SalesTeam-mandatory pattern may not hold).

## Interactions

Types offered: Phone Call 60001, **Email 60002**, SMS 60005, Chat
60006, Video Call 1. NOTE: FSE *blocks creating* email interactions;
this tenant *lists* the type but create-acceptance is UNTESTED. Probe
before designing stories around fabricated emails; if 60002 creates
here, that unlocks richer B2B trails than FSE allows.

## Conventions

Env: `bizplus.env` at repo root. Manifests: `manifests/bizplus/`.
Stories: `stories/bizplus/`. Never cross-source env files (CLAUDE.md
Auth & environments).

## Write-probe results (2026-07-22, after recon)

- **Opportunity create WORKS** with the minimal shape: AbEntryKey +
  Objective + Status + ForecastRevenue + CloseDate ("YYYY-MM-DD") +
  Leader. No process/stage needed at create.
- **Opportunity DELETE: Access Denied** (-30002) for this PAT. Creates
  are PERMANENT until Lewis grants Opportunity-delete in Administrator.
  Cleanup fallback: rename + Status 4. Never create probe opportunities
  here again without a repurposing plan.
- **Stages/processes are per-deal INSTANCES** (147 deals = 147 distinct
  CurrentSalesStage keys; FieldOptions empty; SalesProcess/SalesStage
  object reads fail). Deals are created stage-less; stages assigned in
  the UI. Never write CurrentSalesStage/SalesProcessKey (rule 4).
- **Email interactions BLOCKED on create** (-10002), same as FSE,
  despite 60002 appearing in the type list. Calls (60001) work.
- **Audit notes: none observed** after 30 creates + 1 update (sweep
  found 0). Tenant may not auto-log like FSE does; keep sweeping anyway.
- **Zombie pipeline:** 61 sample opportunities from 2022-2023 sit OPEN.
  Filter captures to 2026 dates, or run a one-time hygiene pass
  (permanent - needs Lewis's explicit go).
- Task create accepts AssignedTo; Note uses ParentKey; both delete fine.

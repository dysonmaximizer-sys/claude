# Maximizer field schema for demo data

Source of truth: Lewis's Address Book export (77 records) plus the field-mapping
screenshots from Maximizer's import wizard (July 2026). The import wizard maps
CSV columns to fields by name, so column headers do not have to match exactly —
but keeping them identical to the export makes mapping automatic.

## Output columns (default, in order)

Company, First Name, Last Name, Address Line 1, Address Line 2, City / Town,
State / County / Province, Website, Account Manager, Email Address, Department,
Division, Phone 1, Mr/Ms, Position, Country, Creation Date, Creator,
Email opt-in type, IDentification, Last Modified Date, Lead Status, Modified By,
Sales Lead, Territory, Territory Status, Zip / Postal Code, Entry Type,
Next KYC Review, Last KYC Review, Days Since Last KYC Review, Birthdate

## Field rules

**IDentification** — Maximizer's Address Book entry key. A Household or
Company and all its member Contacts SHARE the same ID — that is how the flat
export expresses membership (e.g. Cameron Family + Lou, Nancy, Paula, and
Roberto Cameron are five rows with one ID). So a record is uniquely identified
by ID + name, not ID alone. Never invent, edit, or reuse an ID; a wrong ID
detaches a contact from its household or corrupts another record. New
throwaway records get an empty ID. To add a contact to an existing household,
give the new row that household's ID — but confirm with a test import first.

**Entry Type** — Contact, Household, or Company. Households and Companies are
parent records; Contacts link to them via the shared ID above.

**Formula fields — never write values:**
- Days Since Last KYC Review (and every other "Days Since Last X Review")
- Current Age, Insurance Age
Maximizer computes these. Write the inputs (Birthdate, Last/Next review dates)
and leave these blank.

**System fields — include but expect the import to ignore:**
Creation Date, Creator, Modified By, Last Modified Date. Maximizer typically
stamps these itself.

**Dates** — YYYY-MM-DD, confirmed by Lewis (July 2026) as the format his
import expects. Set in cast.json meta.date_format if it ever changes.

**Fabricated filler data** — the cast's missing basic fields were filled with
deterministic fake data: emails on the reserved `@mail.test` domain, 555
phone numbers, fictional street addresses, contacts inheriting their
household/company address. When adding new records, follow the same
conventions so nothing in the demo database can route to a real person.
Picklist-style fields (Territory, Lead Status, Email opt-in type, Department,
Mr/Ms) were left blank deliberately — fill only with values confirmed to
exist in Lewis's Address Book configuration.

## User-defined fields available in this Address Book (from import wizard)

Not in the default output, but can be added to `meta.output_columns` in
cast.json when a story needs them. Ask Lewis for current valid picklist values
before inventing any.

- **System:** Customer Interests, Lead source, Lead status, Partner Interests
- **WM_Client Info:** Client Type, Business Number, LTA, Rating, Source,
  Account Types, Client Since, GIC Expiry Date, Important Note, Objectives,
  Primary/Secondary Advisor (+ Codes), Profession, Record Type - Mandatory,
  Segmentation, Status, RRSP Contribution Room, RRSP Deduction Limit,
  TFSA Contribution Room, TFSA Deduction Limit, Trading Authorization Via
- **WM_Client Info → Review Schedule:** Next/Last pairs for Banking
  Relationship, Financial Plan, Estate Planning, Insurance Needs, KYC,
  Progress, Risk Management, Tax Planning (all "Days Since" versions are
  formulas — skip)
- **WM_KYC etc.:** KYC last updated, Investment Time Frame, Investment
  Knowledge, Loan fields, Corporation Details (Corporate Role, % Shareholder,
  Anniversary Date, Annual Meeting Date, Incorporated Since, Corporation Name),
  Driver License, Industry, Name of Pet, Next Quarterly review, No. of
  Employees, plus grouped folders (Risk, Income, Compliance, etc.)
- **WME_Group Benefits - Members:** Name of Spouse, Child 1–3

## Canadian-realism guardrails

This database plays a Canadian financial advisory practice. Keep it believable:
provinces as two-letter codes (ON, BC, AB...), Canadian postal code format
(A1A 1A1) for Canadian addresses, plausible Canadian city/province pairs,
(XXX) XXX-XXXX phones. A US household or two is fine (the export has them).
Milestone ages that matter in Canadian financial advice: 65 (retirement,
insurance renewals, OAS), 71 (RRSP must convert to RRIF by end of that year),
18 (RESP/beneficiary transitions).

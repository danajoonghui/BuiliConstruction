# BUILI demo persona evidence

These assets form one coherent, synthetic demonstration account. They are not
loose UI placeholders.

- User: **Jordan Cho**, Project Manager at **Northstar Builders**
- Project: **Cooper Residence Renovation**
- Reporter: **Mike Alvarez**, Foreman
- Issue: **BUI-1042**, garage GFCI receptacle installed at 12 inches AFF where
  E1.1 Note 3 requires a minimum of 18 inches AFF

The primary routed action is a field correction/punch item because the source
requirement is clear. A clarification RFI is secondary and should only be used
if a reviewer finds a conflicting source or needs designer confirmation.

`persona.json` is the machine-readable seed manifest. The backend seed command
copies the files into configured object storage and creates their database
relationships. Production environments must keep demo seeding disabled.

The persona includes a coordinated A1.1 architectural, E1.1 electrical, and
M1.1 mechanical drawing set.  All sheets use the same calibrated metric
coordinate system, but contain discipline-specific symbols, notes, fixtures,
and PlanGraph objects.  `drawing-set.json` binds those sheets to the generated
GLB review model and three spatial issue pins.

`scripts/generate_production_demo_report.py` regenerates the complete report
portfolio from the original BUILI production templates:

- issue evidence package (PDF and DOCX)
- punch item (PDF and DOCX)
- RFI draft and issued RFI (PDF and DOCX)
- change event evidence record (PDF and DOCX)
- daily field report (PDF and DOCX)

Each report family has its own operational field schema, blocks issuance when
required data is missing, removes repeated narrative sections, and retains the
same source index, evidence register, activity chronology, and review control
between editable and PDF output.

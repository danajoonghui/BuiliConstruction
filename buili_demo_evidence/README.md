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

`BUI-1042-issue-package.pdf` and `BUI-1042-issue-package.docx` are regenerated
from the same original BUILI production template with
`scripts/generate_production_demo_report.py`; the editable and issued views
therefore retain the same source index and review control.

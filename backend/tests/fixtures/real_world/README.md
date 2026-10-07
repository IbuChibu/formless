# Real-world PDF fixtures

These official public forms are compatibility fixtures. They are intentionally
kept separate from `sample_form.pdf`, which remains the small deterministic
fixture used by the core unit tests. The I-9 also has focused automated
compatibility coverage.

Use dummy values only. The source URLs can publish newer revisions in place, so
do not replace a fixture without reviewing its structure and updating its hash.

## Fixtures

| File | Official source | Verified structure | SHA-256 |
| --- | --- | --- | --- |
| `irs_w9_2024.pdf` | [IRS Form W-9](https://www.irs.gov/pub/irs-pdf/fw9.pdf) | 6 pages; hybrid XFA and AcroForm; 27 fields | `2d420cbb4123dcf1fb82595b2359cfbb5d81f00b9df9d359fcc7af361d093f53` |
| `sba_startup_costs_2023.pdf` | [SBA Startup Costs Worksheet](https://legacy.sba.gov/sites/default/files/2023-07/Startup%20Costs%20Worksheet.pdf) | 1 page; AcroForm; 98 text fields; calculation actions | `f8ad349069ec0c5c712ed182c7c42b6b57c90fce3bbb4ce2c61d73effea032bd` |
| `state_ds11_2025.pdf` | [State Department Form DS-11](https://eforms.state.gov/Forms/ds11_pdf.PDF) | 6 pages; AcroForm; 86 fields including non-standard checkbox states | `6b30860f0b54cba9df1a54d4eb007dc93a6c785b5253516604530b1c1898e2f6` |
| `uscis_i9_2025.pdf` | [USCIS Form I-9](https://www.uscis.gov/sites/default/files/document/forms/i-9.pdf) | 4 pages; AcroForm; 133 fields including text, checkboxes, and dropdowns | `780f348c34df694bb0b4dbbfaf9f22b99b9757b80d16a37ba89aadf069597281` |

The files and structures above were verified on 7 October 2026.

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class PdfFieldProfile:
    order: int
    label: str
    question: str
    section: str
    help_text: Optional[str] = None
    choice_labels: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PdfFormProfile:
    form_id: str
    form_version: str
    title: str
    fields: dict[str, PdfFieldProfile]


def _field(
    label: str,
    question: str,
    section: str,
    *,
    help_text: Optional[str] = None,
    choice_labels: tuple[tuple[str, str], ...] = (),
) -> PdfFieldProfile:
    return PdfFieldProfile(
        order=-1,
        label=label,
        question=question,
        section=section,
        help_text=help_text,
        choice_labels=choice_labels,
    )


_DS11_FIELD_DEFINITIONS = (
    (
        "Selection",
        _field(
            "Documents requested",
            "Select document(s) for which you are submitting fees",
            "Document selection",
            help_text=(
                "The U.S. Passport Card is not valid for international air "
                "travel."
            ),
            choice_labels=(
                ("Book", "U.S. Passport Book"),
                ("Card", "U.S. Passport Card"),
                ("Both", "Both"),
            ),
        ),
    ),
    (
        "Regular or Large Book",
        _field(
            "Passport book size",
            "Select a regular or large passport book",
            "Document selection",
            help_text=(
                "The large book is for frequent international travelers who "
                "need more visa pages."
            ),
            choice_labels=(
                ("Regular", "Regular Book (Standard)"),
                ("Large", "Large Book (Non-Standard)"),
            ),
        ),
    ),
    (
        "Applicant Last Name",
        _field("1. Name - Last", "1. Name - Last", "1. Name"),
    ),
    (
        "Applicant First Name",
        _field("1. Name - First", "1. Name - First", "1. Name"),
    ),
    (
        "Applicant Middle Name",
        _field("1. Name - Middle", "1. Name - Middle", "1. Name"),
    ),
    (
        "Applicant DOB M",
        _field(
            "2. Date of Birth - Month",
            "2. Date of Birth - Month (MM)",
            "2. Date of Birth",
        ),
    ),
    (
        "Applicant DOB D",
        _field(
            "2. Date of Birth - Day",
            "2. Date of Birth - Day (DD)",
            "2. Date of Birth",
        ),
    ),
    (
        "Applicant DOB Y",
        _field(
            "2. Date of Birth - Year",
            "2. Date of Birth - Year (YYYY)",
            "2. Date of Birth",
        ),
    ),
    ("Gender", _field("3. Sex", "3. Sex", "3. Sex")),
    (
        "Applicant Place of Birth",
        _field(
            "4. Place of Birth",
            "4. Place of Birth (City and State in the U.S., or City and "
            "Country as presently known)",
            "4. Place of Birth",
        ),
    ),
    (
        "Applicant SSN 1",
        _field(
            "5. Social Security Number - First 3 digits",
            "5. Social Security Number - First 3 digits",
            "5. Social Security Number",
        ),
    ),
    (
        "Applicant SSN 2",
        _field(
            "5. Social Security Number - Middle 2 digits",
            "5. Social Security Number - Middle 2 digits",
            "5. Social Security Number",
        ),
    ),
    (
        "Applicant SSN 3",
        _field(
            "5. Social Security Number - Last 4 digits",
            "5. Social Security Number - Last 4 digits",
            "5. Social Security Number",
        ),
    ),
    (
        "Alien Number",
        _field(
            "6. USCIS Registration A-Number",
            "6. USCIS Registration A-Number (if applicable)",
            "6. USCIS Registration A-Number",
        ),
    ),
    (
        "Applicant Email",
        _field("7. Email", "7. Email", "7. Email"),
    ),
    (
        "Applicant Address Street",
        _field(
            "8. Mailing Address Line 1",
            "8. Mailing Address Line 1 - Street, RFD number, P.O. Box, or URB",
            "8. Mailing Address",
            help_text="Also include Apartment, Suite, etc.",
        ),
    ),
    (
        "Address Line 2",
        _field(
            "8. Mailing Address Line 2",
            "8. Mailing Address Line 2",
            "8. Mailing Address",
            help_text=(
                "If the applicant is a child, write In Care Of the parent."
            ),
        ),
    ),
    (
        "Applicant Address City",
        _field(
            "8. Mailing Address - City",
            "8. Mailing Address - City",
            "8. Mailing Address",
        ),
    ),
    (
        "Applicant Address State",
        _field(
            "8. Mailing Address - State",
            "8. Mailing Address - State",
            "8. Mailing Address",
        ),
    ),
    (
        "Applicant Address Zip Code",
        _field(
            "8. Mailing Address - Zip Code",
            "8. Mailing Address - Zip Code",
            "8. Mailing Address",
        ),
    ),
    (
        "Applicant Address Country",
        _field(
            "8. Mailing Address - Country",
            "8. Mailing Address - Country (if outside the United States)",
            "8. Mailing Address",
        ),
    ),
    (
        "Applicant Phone 1",
        _field(
            "9. Primary Contact Phone Number - First part",
            "9. Primary Contact Phone Number - First part",
            "9. Primary Contact Phone Number",
        ),
    ),
    (
        "Applicant Phone 2",
        _field(
            "9. Primary Contact Phone Number - Second part",
            "9. Primary Contact Phone Number - Second part",
            "9. Primary Contact Phone Number",
        ),
    ),
    (
        "Applicant Phone 3",
        _field(
            "9. Primary Contact Phone Number - Final part",
            "9. Primary Contact Phone Number - Final part",
            "9. Primary Contact Phone Number",
        ),
    ),
    (
        "List all other name you have used",
        _field(
            "9A. Other name used",
            "9A. Other name used",
            "9. Other Names Used",
            help_text=(
                "Examples include birth name, maiden name, previous marriage, "
                "or legal name change."
            ),
        ),
    ),
    (
        "List all other names you have used",
        _field(
            "9B. Other name used",
            "9B. Other name used",
            "9. Other Names Used",
        ),
    ),
    (
        "Name of Applicant 2",
        _field(
            "Applicant Name",
            "Name of Applicant (Last, First, and Middle)",
            "Applicant identification",
        ),
    ),
    (
        "Applicant DOB 2",
        _field(
            "Applicant Date of Birth",
            "Applicant Date of Birth (MM/DD/YYYY)",
            "Applicant identification",
        ),
    ),
    (
        "Parent 1 FM Name",
        _field(
            "10. Parent 1 - First and Middle Name",
            "10. Parent 1 - First and Middle Name at Parent's Birth",
            "10. Parental Information",
        ),
    ),
    (
        "Parent 1 Last Name",
        _field(
            "10. Parent 1 - Last Name",
            "10. Parent 1 - Last Name at Parent's Birth",
            "10. Parental Information",
        ),
    ),
    (
        "Parent 1 DOB",
        _field(
            "10. Parent 1 - Date of Birth",
            "10. Parent 1 - Date of Birth (MM/DD/YYYY)",
            "10. Parental Information",
        ),
    ),
    (
        "Parent 1 Place of Birth",
        _field(
            "10. Parent 1 - Place of Birth",
            "10. Parent 1 - Place of Birth",
            "10. Parental Information",
        ),
    ),
    (
        "Parent 1 Gender",
        _field(
            "10. Parent 1 - Sex",
            "10. Parent 1 - Sex",
            "10. Parental Information",
        ),
    ),
    (
        "Parent 1 US Citizen",
        _field(
            "10. Parent 1 - U.S. Citizen",
            "10. Is Parent 1 a U.S. citizen?",
            "10. Parental Information",
        ),
    ),
    (
        "Parent 2 FM Name",
        _field(
            "10. Parent 2 - First and Middle Name",
            "10. Parent 2 - First and Middle Name at Parent's Birth",
            "10. Parental Information",
        ),
    ),
    (
        "Parent 2 Last Name",
        _field(
            "10. Parent 2 - Last Name",
            "10. Parent 2 - Last Name at Parent's Birth",
            "10. Parental Information",
        ),
    ),
    (
        "Parent 2 DOB",
        _field(
            "10. Parent 2 - Date of Birth",
            "10. Parent 2 - Date of Birth (MM/DD/YYYY)",
            "10. Parental Information",
        ),
    ),
    (
        "Parent 2 Place of Birth",
        _field(
            "10. Parent 2 - Place of Birth",
            "10. Parent 2 - Place of Birth",
            "10. Parental Information",
        ),
    ),
    (
        "Parent 2 Gender",
        _field(
            "10. Parent 2 - Sex",
            "10. Parent 2 - Sex",
            "10. Parental Information",
        ),
    ),
    (
        "Parent 2 US Citizen",
        _field(
            "10. Parent 2 - U.S. Citizen",
            "10. Is Parent 2 a U.S. citizen?",
            "10. Parental Information",
        ),
    ),
    (
        "Ever Married",
        _field(
            "11. Ever Married",
            "11. Have you ever been married?",
            "11. Marriage Information",
        ),
    ),
    (
        "Full Name of Current Spouse or Most Recent Spouse (Last, first, Middle)",
        _field(
            "11. Current or Most Recent Spouse - Full Name",
            "11. Full Name of Current Spouse or Most Recent Spouse (Last, "
            "First, and Middle)",
            "11. Marriage Information",
        ),
    ),
    (
        "Current Spouse Date of Birth",
        _field(
            "11. Current or Most Recent Spouse - Date of Birth",
            "11. Current or Most Recent Spouse - Date of Birth (MM/DD/YYYY)",
            "11. Marriage Information",
        ),
    ),
    (
        "Current Spouse Place of Birth",
        _field(
            "11. Current or Most Recent Spouse - Place of Birth",
            "11. Current or Most Recent Spouse - Place of Birth",
            "11. Marriage Information",
        ),
    ),
    (
        "Spouse US Citizen",
        _field(
            "11. Current or Most Recent Spouse - U.S. Citizen",
            "11. Is the current or most recent spouse a U.S. citizen?",
            "11. Marriage Information",
        ),
    ),
    (
        "Date of Marriage (mm/dd/yyyy)",
        _field(
            "11. Date of Marriage",
            "11. Date of Marriage (MM/DD/YYYY)",
            "11. Marriage Information",
        ),
    ),
    (
        "Divorced",
        _field(
            "11. Ever Widowed or Divorced",
            "11. Have you ever been widowed or divorced?",
            "11. Marriage Information",
        ),
    ),
    (
        "Widow/Divorce Date (mm/dd/yyyy)",
        _field(
            "11. Widow or Divorce Date",
            "11. Widow or Divorce Date (MM/DD/YYYY)",
            "11. Marriage Information",
        ),
    ),
    (
        "Applicant Additional Contact Phone Numbers",
        _field(
            "12. Additional Contact Phone Number",
            "12. Additional Contact Phone Number",
            "12. Additional Contact Phone Number",
        ),
    ),
    (
        "Additional #",
        _field(
            "12. Additional Phone Type",
            "12. Additional Contact Phone Number Type",
            "12. Additional Contact Phone Number",
        ),
    ),
    (
        "Occupation",
        _field(
            "13. Occupation",
            "13. Occupation (if age 16 or older)",
            "13. Occupation",
        ),
    ),
    (
        "Employer or School",
        _field(
            "14. Employer or School",
            "14. Employer or School (if applicable)",
            "14. Employer or School",
        ),
    ),
    ("Height", _field("15. Height", "15. Height", "15. Height")),
    (
        "Hair Color",
        _field("16. Hair Color", "16. Hair Color", "16. Hair Color"),
    ),
    (
        "Eye Color",
        _field("17. Eye Color", "17. Eye Color", "17. Eye Color"),
    ),
    (
        "Travel Departure Date",
        _field(
            "18. Travel Plans - Departure Date",
            "18. Travel Plans - Departure Date (MM/DD/YYYY)",
            "18. Travel Plans",
        ),
    ),
    (
        "Travel Return Date",
        _field(
            "18. Travel Plans - Return Date",
            "18. Travel Plans - Return Date (MM/DD/YYYY)",
            "18. Travel Plans",
        ),
    ),
    (
        "Countries to be visited",
        _field(
            "18. Travel Plans - Countries to be Visited",
            "18. Travel Plans - Countries to be Visited",
            "18. Travel Plans",
        ),
    ),
    (
        "Permanent Address Street",
        _field(
            "19. Permanent Address - Street, RFD Number, or URB",
            "19. Permanent Address - Street, RFD Number, or URB",
            "19. Permanent Address",
            help_text=(
                "Complete if a P.O. Box is listed under Mailing Address or if "
                "the residence differs from Mailing Address. Do not list a "
                "P.O. Box."
            ),
        ),
    ),
    (
        "Permanent Address Apartment/Unit",
        _field(
            "19. Permanent Address - Apartment or Unit",
            "19. Permanent Address - Apartment or Unit",
            "19. Permanent Address",
        ),
    ),
    (
        "Permanent Address City",
        _field(
            "19. Permanent Address - City",
            "19. Permanent Address - City",
            "19. Permanent Address",
        ),
    ),
    (
        "Permanent Address State",
        _field(
            "19. Permanent Address - State",
            "19. Permanent Address - State",
            "19. Permanent Address",
        ),
    ),
    (
        "Permanent Address Zip Code",
        _field(
            "19. Permanent Address - Zip Code",
            "19. Permanent Address - Zip Code",
            "19. Permanent Address",
        ),
    ),
    (
        "Emergency Contact Name",
        _field(
            "20. Emergency Contact - Name",
            "20. Emergency Contact - Name",
            "20. Emergency Contact",
            help_text=(
                "Provide a person not traveling with you who can be contacted "
                "in the event of an emergency."
            ),
        ),
    ),
    (
        "Emergency Contact Address",
        _field(
            "20. Emergency Contact - Address",
            "20. Emergency Contact - Address, Street, RFD Number, or P.O. Box",
            "20. Emergency Contact",
        ),
    ),
    (
        "Emergency Contact Apartment/Unit",
        _field(
            "20. Emergency Contact - Apartment or Unit",
            "20. Emergency Contact - Apartment or Unit",
            "20. Emergency Contact",
        ),
    ),
    (
        "Emergency Contact City",
        _field(
            "20. Emergency Contact - City",
            "20. Emergency Contact - City",
            "20. Emergency Contact",
        ),
    ),
    (
        "Emergency Contact State",
        _field(
            "20. Emergency Contact - State",
            "20. Emergency Contact - State",
            "20. Emergency Contact",
        ),
    ),
    (
        "Emergency Contact Zip Code",
        _field(
            "20. Emergency Contact - Zip Code",
            "20. Emergency Contact - Zip Code",
            "20. Emergency Contact",
        ),
    ),
    (
        "Emergency Contact Phone",
        _field(
            "20. Emergency Contact - Phone Number",
            "20. Emergency Contact - Phone Number",
            "20. Emergency Contact",
        ),
    ),
    (
        "Relationship to Applicant",
        _field(
            "20. Emergency Contact - Relationship",
            "20. Emergency Contact - Relationship to Applicant",
            "20. Emergency Contact",
        ),
    ),
    (
        "Ever Applied or Issued",
        _field(
            "21. Previous U.S. Passport",
            "21. Have you ever applied for or been issued a U.S. Passport "
            "Book or Passport Card?",
            "21. Previous U.S. Passport",
        ),
    ),
    (
        "Your name as printed on your most recent U.S. passport book and/or passport card",
        _field(
            "21. Name on Most Recent Passport Book",
            "21. Name printed on your most recent passport book",
            "21. Previous U.S. Passport",
        ),
    ),
    (
        "Book Status Submitting",
        _field(
            "21. Passport Book Status - Submitting with Application",
            "21. Most Recent Passport Book - Submitting with Application",
            "21. Previous U.S. Passport",
        ),
    ),
    (
        "Book Status Stolen",
        _field(
            "21. Passport Book Status - Stolen",
            "21. Most Recent Passport Book - Stolen",
            "21. Previous U.S. Passport",
        ),
    ),
    (
        "Book Status Lost",
        _field(
            "21. Passport Book Status - Lost",
            "21. Most Recent Passport Book - Lost",
            "21. Previous U.S. Passport",
        ),
    ),
    (
        "Book Status Possession",
        _field(
            "21. Passport Book Status - In My Possession",
            "21. Most Recent Passport Book - In My Possession (if expired)",
            "21. Previous U.S. Passport",
        ),
    ),
    (
        "Name as printed on your most recent passport card",
        _field(
            "21. Name on Most Recent Passport Card",
            "21. Name printed on your most recent passport card",
            "21. Previous U.S. Passport",
        ),
    ),
    (
        "Card Status Submitting",
        _field(
            "21. Passport Card Status - Submitting with Application",
            "21. Most Recent Passport Card - Submitting with Application",
            "21. Previous U.S. Passport",
        ),
    ),
    (
        "Card Status Stolen",
        _field(
            "21. Passport Card Status - Stolen",
            "21. Most Recent Passport Card - Stolen",
            "21. Previous U.S. Passport",
        ),
    ),
    (
        "Card Status Lost",
        _field(
            "21. Passport Card Status - Lost",
            "21. Most Recent Passport Card - Lost",
            "21. Previous U.S. Passport",
        ),
    ),
    (
        "Card Status Possession",
        _field(
            "21. Passport Card Status - In My Possession",
            "21. Most Recent Passport Card - In My Possession (if expired)",
            "21. Previous U.S. Passport",
        ),
    ),
    (
        "Circumstances of lost/stolen book/card",
        _field(
            "21. Lost or Stolen Passport Details",
            "21. Circumstances of a Lost or Stolen Passport Book or Card",
            "21. Previous U.S. Passport",
            help_text=(
                "If your most recent passport book or card was lost or "
                "stolen, explain the loss or theft in detail in this field."
            ),
        ),
    ),
    (
        "Clear",
        _field(
            "Clear Form",
            "Clear Form action",
            "Form actions",
        ),
    ),
)


def _ordered_fields(
    definitions: tuple[tuple[str, PdfFieldProfile], ...],
) -> dict[str, PdfFieldProfile]:
    return {
        field_id: replace(field, order=order)
        for order, (field_id, field) in enumerate(definitions)
    }


_DS11_2025_PROFILE = PdfFormProfile(
    form_id="state-ds11",
    form_version="04-2025",
    title="Application for a U.S. Passport",
    fields=_ordered_fields(_DS11_FIELD_DEFINITIONS),
)

_PDF_FORM_PROFILES = {
    (profile.form_id, profile.form_version): profile
    for profile in (_DS11_2025_PROFILE,)
}


def get_pdf_form_profile(
    form_id: str,
    form_version: str,
) -> Optional[PdfFormProfile]:
    return _PDF_FORM_PROFILES.get((form_id, form_version))


def profiled_choice_field_ids() -> frozenset[str]:
    return frozenset(
        field_id
        for profile in _PDF_FORM_PROFILES.values()
        for field_id, field in profile.fields.items()
        if field.choice_labels
    )

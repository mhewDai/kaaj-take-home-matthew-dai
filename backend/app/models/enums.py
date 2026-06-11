"""Controlled vocabularies shared by applications and policies.

Normalising industries / equipment / credit flags into enums is what makes
exclusion lists comparable across lenders: a policy says "exclude RESTAURANTS"
and an application says "industry = RESTAURANTS" and the engine can match them
without fuzzy string logic.

These lists are intentionally editable — adding a value here + re-seeding is the
"add a new industry we can match on" workflow. ``OTHER`` is always available as a
safe fallback so the form never blocks an unusual applicant.
"""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """str-backed enum so values serialize as plain strings in JSON / DB."""

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.value


class Industry(StrEnum):
    # --- General commercial ---
    ARBOR_LANDSCAPING = "arbor_landscaping"
    AUTOMOTIVE_REPAIR = "automotive_repair"
    CONSTRUCTION = "construction"
    COMMERCIAL_CLEANING = "commercial_cleaning"
    MANUFACTURING = "manufacturing"
    MACHINE_TOOLS = "machine_tools"
    WOODWORKING = "woodworking"
    WASTE_MANAGEMENT = "waste_management"
    FARMING_AGRICULTURE = "farming_agriculture"
    MEDICAL_DENTAL_VET = "medical_dental_vet"
    PROFESSIONAL_SERVICES = "professional_services"
    RETAIL = "retail"
    WHOLESALE = "wholesale"
    HEALTHCARE = "healthcare"
    # --- Transportation ---
    TRUCKING_LONG_HAUL = "trucking_long_haul"   # OTR / over-the-road
    TRUCKING_LOCAL = "trucking_local"
    LOGGING = "logging"
    # --- Frequently excluded / restricted ---
    RESTAURANTS = "restaurants"
    CAR_WASH = "car_wash"
    BEAUTY_TANNING_SALON = "beauty_tanning_salon"
    NAIL_SALON = "nail_salon"
    TATTOO_PIERCING = "tattoo_piercing"
    AESTHETIC = "aesthetic"
    GAMING_GAMBLING = "gaming_gambling"
    CANNABIS = "cannabis"
    ADULT_ENTERTAINMENT = "adult_entertainment"
    OIL_GAS_PETROLEUM = "oil_gas_petroleum"
    HAZMAT = "hazmat"
    WEAPONS_FIREARMS = "weapons_firearms"
    MSB = "money_services_business"
    REAL_ESTATE = "real_estate"
    CHURCH_NONPROFIT = "church_nonprofit"
    OTHER = "other"


# Industries we treat as "trucking" for non-trucking-only / trucking-program logic.
TRUCKING_INDUSTRIES = frozenset(
    {Industry.TRUCKING_LONG_HAUL, Industry.TRUCKING_LOCAL, Industry.LOGGING}
)


class EquipmentType(StrEnum):
    # --- Trucks / transportation ---
    CLASS_8_TRUCK = "class_8_truck"
    CLASS_8_TRAILER = "class_8_trailer"
    DUMP_TRUCK = "dump_truck"
    MEDIUM_DUTY_TRUCK = "medium_duty_truck"
    LIGHT_DUTY_TRUCK = "light_duty_truck"
    VOCATIONAL_TRUCK = "vocational_truck"
    REEFER_TRAILER = "reefer_trailer"
    # --- Heavy / industrial ---
    CONSTRUCTION_EQUIPMENT = "construction_equipment"
    INDUSTRIAL_MACHINERY = "industrial_machinery"
    MACHINE_TOOLS = "machine_tools"
    MATERIAL_HANDLING = "material_handling"
    FORKLIFT = "forklift"
    FARM_EQUIPMENT = "farm_equipment"
    LAWN_TURF = "lawn_turf"
    LOGGING_EQUIPMENT = "logging_equipment"
    WOODWORKING = "woodworking_equipment"
    # --- Light / soft collateral ---
    AUTOMOTIVE_REPAIR_EQUIPMENT = "automotive_repair_equipment"
    MEDICAL_EQUIPMENT = "medical_equipment"
    RESTAURANT_EQUIPMENT = "restaurant_equipment"
    JANITORIAL_EQUIPMENT = "janitorial_equipment"
    OFFICE_EQUIPMENT = "office_equipment"
    COPIER = "copier"
    AUDIO_VISUAL = "audio_visual"
    FURNITURE = "furniture"
    SIGNAGE = "signage"
    KIOSK = "kiosk"
    ATM = "atm"
    AIRCRAFT_BOAT = "aircraft_boat"
    ELECTRIC_VEHICLE = "electric_vehicle"
    TANNING_BED = "tanning_bed"
    OTHER = "other"


SOFT_COLLATERAL_EQUIPMENT = frozenset(
    {
        EquipmentType.OFFICE_EQUIPMENT,
        EquipmentType.COPIER,
        EquipmentType.AUDIO_VISUAL,
        EquipmentType.FURNITURE,
        EquipmentType.SIGNAGE,
        EquipmentType.KIOSK,
    }
)


class EquipmentCondition(StrEnum):
    NEW = "new"
    USED = "used"


class CreditRating(StrEnum):
    """Coarse A-E credit grade used by some lenders (Falcon)."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvalStatus(StrEnum):
    """Outcome of a single criterion evaluation."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"              # soft / preference miss, never blocks
    NOT_APPLICABLE = "not_applicable"  # prerequisite gate not met
    INSUFFICIENT_DATA = "insufficient_data"


class RuleSeverity(StrEnum):
    """How a rule participates in the matching decision."""

    KNOCKOUT = "knockout"          # lender-wide hard stop
    QUALIFICATION = "qualification"  # program gate; fail => program rejected
    PREREQUISITE = "prerequisite"  # program applicability gate
    PREFERENCE = "preference"      # soft signal; affects score/warnings only


class RuleScope(StrEnum):
    LENDER = "lender"
    PROGRAM = "program"

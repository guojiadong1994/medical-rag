from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class Sex(StrEnum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class PatientCreate(BaseModel):
    patient_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    birth_date: date | None = None
    sex: Sex = Sex.UNKNOWN


class PatientRead(PatientCreate):
    pass

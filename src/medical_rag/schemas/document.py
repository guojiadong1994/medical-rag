from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class DocumentType(StrEnum):
    OUTPATIENT = "outpatient"
    PHYSICAL_EXAM = "physical_exam"
    LABORATORY = "laboratory"
    OCT_REPORT = "oct_report"
    UBM_REPORT = "ubm_report"
    MRI_REPORT = "mri_report"
    DISCHARGE_SUMMARY = "discharge_summary"
    OTHER = "other"


class DocumentRecord(BaseModel):
    document_id: str
    patient_id: str
    document_type: DocumentType
    event_time: datetime | None = None
    source_uri: str

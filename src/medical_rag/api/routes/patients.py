from fastapi import APIRouter, Depends, HTTPException, status

from medical_rag.auth.service import require_access_token
from medical_rag.patients.repository import get_patient, list_patients

router = APIRouter(
    prefix="/api/v1/patients",
    tags=["patients"],
    dependencies=[Depends(require_access_token)],
)


@router.get("")
async def patients() -> list[dict]:
    return list_patients()


@router.get("/{patient_id}")
async def patient_detail(patient_id: str) -> dict:
    patient = get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者不存在")
    return patient

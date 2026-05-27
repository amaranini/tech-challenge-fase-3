"""Pacote de tools usados pelo assistente (acesso a prontuário, etc)."""

from assistant.tools.patient_records import PatientRecord, get_patient_by_id

__all__ = ["PatientRecord", "get_patient_by_id"]

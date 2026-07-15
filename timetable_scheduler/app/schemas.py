from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime

class ResourceSchema(BaseModel):
    name: str
    min_hours: float
    max_hours: float

class DepartmentSchema(BaseModel):
    name: str
    min_hours: float
    max_hours: float

class MappingSchema(BaseModel):
    resource_name: str
    dept_name: str
    is_feasible: bool
    min_days: int
    max_days: int

class AbsenceSchema(BaseModel):
    resource_name: str
    date: date
    reason: Optional[str] = None

class ExcelValidationErrorResponse(BaseModel):
    sheet: str
    row: str
    column: str
    message: str

class ErrorResponse(BaseModel):
    detail: str
    validation_errors: Optional[List[ExcelValidationErrorResponse]] = None

class AssignmentResponse(BaseModel):
    resource_name: str
    dept_name: str
    date: date
    hours: float

class ViolationResponse(BaseModel):
    violation_type: str
    resource_name: Optional[str] = None
    dept_name: Optional[str] = None
    description: str

class AlternativeResponse(BaseModel):
    assignments: List[AssignmentResponse]
    violations: List[ViolationResponse]
    violation_score: int

class ScheduleRunResponse(BaseModel):
    id: int
    created_at: datetime
    status: str
    alternatives: List[AlternativeResponse]

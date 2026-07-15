import io
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os

from .database import engine, Base, get_db
from .models import GeneralSetting, Resource, Department, ResourceDeptMapping, Absence, ScheduleRun, ScheduleAssignment, ScheduleViolation
from .excel_handler import generate_template, parse_and_validate_excel, ExcelValidationError
from .solver import solve_schedule
from .schemas import ErrorResponse

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Timetable Scheduler API", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root route serves index.html
@app.get("/")
def read_root():
    static_file_path = os.path.join("static", "index.html")
    if os.path.exists(static_file_path):
        return FileResponse(static_file_path)
    raise HTTPException(status_code=404, detail="Frontend index.html not found.")

@app.get("/api/template/download")
def download_excel_template():
    """Generates and downloads the empty Excel input template."""
    try:
        buffer = generate_template()
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=timetable_template.xlsx"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate template: {str(e)}")

@app.post("/api/schedule/upload", status_code=status.HTTP_201_CREATED)
def upload_and_solve_schedule(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Receives an Excel sheet, validates it, stores inputs, solves the schedule,
    persists output assignments/violations, and returns the result.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload a valid Excel workbook (.xlsx)."
        )
        
    try:
        file_bytes = file.file.read()
        parsed_data = parse_and_validate_excel(file_bytes)
    except ExcelValidationError as e:
        # Return 400 with structured validation errors list
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Excel sheet validation failed.",
                "validation_errors": e.errors
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during parsing: {str(e)}"
        )
        
    # Validation succeeded, persist the inputs in database (clear old configuration first)
    try:
        db.query(GeneralSetting).delete()
        db.query(Resource).delete()
        db.query(Department).delete()
        db.query(ResourceDeptMapping).delete()
        db.query(Absence).delete()
        
        # 1. Add settings
        setting = GeneralSetting(
            start_date=parsed_data["start_date"],
            end_date=parsed_data["end_date"],
            default_shift_hours=parsed_data["default_shift_hours"]
        )
        db.add(setting)
        
        # 2. Add resources
        for r in parsed_data["resources"]:
            db.add(Resource(name=r["name"], min_hours=r["min_hours"], max_hours=r["max_hours"]))
            
        # 3. Add departments
        for d in parsed_data["departments"]:
            db.add(Department(name=d["name"], min_hours=d["min_hours"], max_hours=d["max_hours"]))
            
        # 4. Add mappings
        for m in parsed_data["mappings"]:
            db.add(ResourceDeptMapping(
                resource_name=m["resource_name"],
                dept_name=m["dept_name"],
                is_feasible=m["is_feasible"],
                min_days=m["min_days"],
                max_days=m["max_days"]
            ))
            
        # 5. Add absences
        for a in parsed_data["absences"]:
            db.add(Absence(
                resource_name=a["resource_name"],
                date=a["date"],
                reason=a["reason"]
            ))
            
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database failed to persist configuration: {str(e)}"
        )
        
    # Trigger Solver
    try:
        solve_result = solve_schedule(parsed_data, max_alternatives=3)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization engine error: {str(e)}"
        )
        
    if solve_result["status"] == "INFEASIBLE":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The schedule is completely infeasible and solver could not generate a relaxed layout."
        )
        
    # Save the run and results to database
    try:
        run = ScheduleRun(
            status=solve_result["status"],
            total_alternatives=len(solve_result["alternatives"])
        )
        db.add(run)
        db.flush() # Populate run.id
        
        # Save alternate assignments and violations
        for alt_idx, alt in enumerate(solve_result["alternatives"]):
            for assign in alt["assignments"]:
                db.add(ScheduleAssignment(
                    run_id=run.id,
                    alternate_index=alt_idx,
                    resource_name=assign["resource_name"],
                    dept_name=assign["dept_name"],
                    date=assign["date"],
                    hours=assign["hours"]
                ))
            for viol in alt["violations"]:
                db.add(ScheduleViolation(
                    run_id=run.id,
                    alternate_index=alt_idx,
                    violation_type=viol["violation_type"],
                    resource_name=viol["resource_name"],
                    dept_name=viol["dept_name"],
                    description=viol["description"],
                    severity="WARNING"
                ))
        db.commit()
        
        # Format API Response to client
        formatted_alternatives = []
        for alt_idx, alt in enumerate(solve_result["alternatives"]):
            formatted_alternatives.append({
                "assignments": [
                    {
                        "resource_name": a["resource_name"],
                        "dept_name": a["dept_name"],
                        "date": a["date"],
                        "hours": a["hours"]
                    } for a in alt["assignments"]
                ],
                "violations": [
                    {
                        "violation_type": v["violation_type"],
                        "resource_name": v["resource_name"],
                        "dept_name": v["dept_name"],
                        "description": v["description"]
                    } for v in alt["violations"]
                ],
                "violation_score": alt["violation_score"]
            })
            
        return {
            "id": run.id,
            "created_at": run.created_at,
            "status": run.status,
            "alternatives": formatted_alternatives
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database failed to persist schedule results: {str(e)}"
        )

# Mount static directory for CSS, JS, Fonts
app.mount("/static", StaticFiles(directory="static"), name="static")

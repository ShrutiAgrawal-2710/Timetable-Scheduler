from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
import datetime
from .database import Base

class GeneralSetting(Base):
    __tablename__ = "general_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    default_shift_hours = Column(Float, default=8.0)

class Resource(Base):
    __tablename__ = "resources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    min_hours = Column(Float, default=0.0)
    max_hours = Column(Float, default=240.0)

class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    min_hours = Column(Float, default=0.0)
    max_hours = Column(Float, default=240.0)

class ResourceDeptMapping(Base):
    __tablename__ = "resource_dept_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    resource_name = Column(String, nullable=False)
    dept_name = Column(String, nullable=False)
    is_feasible = Column(Boolean, default=True)
    min_days = Column(Integer, default=0)
    max_days = Column(Integer, default=31)

class Absence(Base):
    __tablename__ = "absences"
    
    id = Column(Integer, primary_key=True, index=True)
    resource_name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    reason = Column(String, nullable=True)

class ScheduleRun(Base):
    __tablename__ = "schedule_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, nullable=False)  # SUCCESS, FEASIBLE_WITH_VIOLATIONS, INFEASIBLE
    total_alternatives = Column(Integer, default=0)
    
    assignments = relationship("ScheduleAssignment", back_populates="run", cascade="all, delete-orphan")
    violations = relationship("ScheduleViolation", back_populates="run", cascade="all, delete-orphan")

class ScheduleAssignment(Base):
    __tablename__ = "schedule_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("schedule_runs.id"), nullable=False)
    alternate_index = Column(Integer, default=0, nullable=False)  # 0, 1, 2 for alternatives
    resource_name = Column(String, nullable=False)
    dept_name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    hours = Column(Float, default=8.0)
    
    run = relationship("ScheduleRun", back_populates="assignments")

class ScheduleViolation(Base):
    __tablename__ = "schedule_violations"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("schedule_runs.id"), nullable=False)
    alternate_index = Column(Integer, default=0, nullable=False)
    violation_type = Column(String, nullable=False)  # e.g., MIN_HOURS, MAX_HOURS, MIN_DAYS, MAX_DAYS
    resource_name = Column(String, nullable=True)
    dept_name = Column(String, nullable=True)
    description = Column(String, nullable=False)
    severity = Column(String, default="WARNING")  # WARNING, ERROR
    
    run = relationship("ScheduleRun", back_populates="violations")

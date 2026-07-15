from typing import Dict, List, Any, Tuple
from datetime import timedelta, date
from ortools.sat.python import cp_model

def get_dates_in_horizon(start_date: date, end_date: date) -> List[date]:
    """Helper to get list of dates between start and end date inclusive."""
    dates = []
    curr = start_date
    while curr <= end_date:
        dates.append(curr)
        curr += timedelta(days=1)
    return dates

def solve_schedule(input_data: Dict[str, Any], max_alternatives: int = 3) -> Dict[str, Any]:
    """
    Formulates and solves the timetable scheduling model using OR-Tools CP-SAT.
    Handles soft constraints with slack variables and returns alternate solutions.
    """
    start_date = input_data["start_date"]
    end_date = input_data["end_date"]
    default_shift_hours = input_data["default_shift_hours"]
    resources = input_data["resources"]
    departments = input_data["departments"]
    mappings = input_data["mappings"]
    absences = input_data["absences"]
    
    dates = get_dates_in_horizon(start_date, end_date)
    num_days = len(dates)
    
    if num_days == 0:
        return {"status": "INFEASIBLE", "alternatives": [], "errors": ["Planning horizon is empty."]}

    # Map name lists and structures for quick lookup
    resource_names = [r["name"] for r in resources]
    dept_names = [d["name"] for d in departments]
    
    # Store bounds
    res_bounds = {r["name"]: (r["min_hours"], r["max_hours"]) for r in resources}
    dept_bounds = {d["name"]: (d["min_hours"], d["max_hours"]) for d in departments}
    
    # Feasibility, min/max days mapping
    # Default mapping: Not feasible unless specified?
    # The prompt says: "Probable mapping defines the feasibility or mapping required."
    # If a mapping is in the excel, we use its feasibility. If not in the excel, is it feasible?
    # To be safe, we assume if NO mapping is defined at all for a resource-dept, it is NOT feasible,
    # OR we assume if there is no mapping row, it defaults to Not Feasible, unless the user specifies otherwise.
    # Let's check: "Probable mapping for a resource and department... defines the feasibility or mapping required."
    # We will assume if a resource-dept pair is not listed in mappings, it is not feasible (is_feasible = False).
    # This matches common enterprise setups where you must explicitly map doctor capabilities.
    map_lookup = {}
    for m in mappings:
        map_lookup[(m["resource_name"], m["dept_name"])] = {
            "is_feasible": m["is_feasible"],
            "min_days": m["min_days"],
            "max_days": m["max_days"]
        }
        
    # Absences lookup: (resource_name, date) -> True
    abs_lookup = {}
    for a in absences:
        abs_lookup[(a["resource_name"], a["date"])] = True
        
    # Default weekends to absent unless overridden (or already handled by default in template generation)
    # The prompt says: "Select Saturday and Sunday as 'Absent' by default. The users can change as required."
    # The user specifies their absences in the excel sheet. 
    # If they are absent on weekends, they will be in the Absences sheet.
    
    # Scale float hours to integers for CP-SAT (SCALE = 10)
    SCALE = 10
    scaled_shift_hours = int(default_shift_hours * SCALE)
    
    # We will accumulate alternative solutions
    alternatives = []
    
    # Track the no-goods constraints across sequential solves
    exclude_constraints = []
    
    # We first find the optimal objective value (minimal violations)
    first_run_optimal_val = None
    
    for alt_idx in range(max_alternatives):
        model = cp_model.CpModel()
        
        # 1. Decision variables: x[r, d, t] = 1 if resource r is assigned to department d on date t
        x = {}
        for r in resource_names:
            for d in dept_names:
                # Only create variable if it's feasible
                mapping = map_lookup.get((r, d))
                is_feasible = mapping["is_feasible"] if mapping else False
                
                for t in dates:
                    if is_feasible and not abs_lookup.get((r, t), False):
                        x[(r, d, t)] = model.NewBoolVar(f"x_{r}_{d}_{t}")
                    else:
                        # Force 0 (implicitly or explicitly)
                        pass
        
        # 2. Hard Constraints
        # Resource double-booking: A resource can be assigned to at most 1 department per day
        for r in resource_names:
            for t in dates:
                active_vars = [x[(r, d, t)] for d in dept_names if (r, d, t) in x]
                if active_vars:
                    model.Add(sum(active_vars) <= 1)
                    
        # 3. Soft Constraints & Slack Variables
        slack_variables = []
        slack_weights = []
        
        # A. Resource Hours Constraints
        for r in resource_names:
            min_h, max_h = res_bounds[r]
            scaled_min_h = int(min_h * SCALE)
            scaled_max_h = int(max_h * SCALE)
            
            # Sum of scheduled hours for resource r
            r_vars = [x[(r, d, t)] for d in dept_names for t in dates if (r, d, t) in x]
            if not r_vars:
                # If resource has no possible variables, their hours are 0.
                if scaled_min_h > 0:
                    # Inevitable violation
                    slack_val = model.NewIntVar(0, scaled_min_h, f"slack_min_hours_res_{r}")
                    model.Add(slack_val == scaled_min_h)
                    slack_variables.append(slack_val)
                    slack_weights.append(100) # Weight for hours violation
                continue
                
            total_hours = sum(r_vars) * scaled_shift_hours
            
            # Min Hours Slack
            slack_min = model.NewIntVar(0, scaled_min_h, f"slack_min_hours_res_{r}")
            model.Add(total_hours >= scaled_min_h - slack_min)
            slack_variables.append(slack_min)
            slack_weights.append(100)
            
            # Max Hours Slack
            max_possible_scaled_hours = len(dates) * scaled_shift_hours
            slack_max = model.NewIntVar(0, max(0, max_possible_scaled_hours - scaled_max_h), f"slack_max_hours_res_{r}")
            model.Add(total_hours <= scaled_max_h + slack_max)
            slack_variables.append(slack_max)
            slack_weights.append(100)

        # B. Department Hours Constraints
        for d in dept_names:
            min_h, max_h = dept_bounds[d]
            scaled_min_h = int(min_h * SCALE)
            scaled_max_h = int(max_h * SCALE)
            
            d_vars = [x[(r, d, t)] for r in resource_names for t in dates if (r, d, t) in x]
            if not d_vars:
                if scaled_min_h > 0:
                    slack_val = model.NewIntVar(0, scaled_min_h, f"slack_min_hours_dept_{d}")
                    model.Add(slack_val == scaled_min_h)
                    slack_variables.append(slack_val)
                    slack_weights.append(100)
                continue
                
            total_hours = sum(d_vars) * scaled_shift_hours
            
            # Min Hours Slack
            slack_min = model.NewIntVar(0, scaled_min_h, f"slack_min_hours_dept_{d}")
            model.Add(total_hours >= scaled_min_h - slack_min)
            slack_variables.append(slack_min)
            slack_weights.append(100)
            
            # Max Hours Slack
            max_possible_scaled_hours = len(resource_names) * len(dates) * scaled_shift_hours
            slack_max = model.NewIntVar(0, max(0, max_possible_scaled_hours - scaled_max_h), f"slack_max_hours_dept_{d}")
            model.Add(total_hours <= scaled_max_h + slack_max)
            slack_variables.append(slack_max)
            slack_weights.append(100)

        # C. Mapping Day Limits (Min/Max Days in Department)
        for (r, d), mapping in map_lookup.items():
            if not mapping["is_feasible"]:
                continue
            min_d = mapping["min_days"]
            max_d = mapping["max_days"]
            
            rd_vars = [x[(r, d, t)] for t in dates if (r, d, t) in x]
            if not rd_vars:
                if min_d > 0:
                    slack_val = model.NewIntVar(0, min_d, f"slack_min_days_{r}_{d}")
                    model.Add(slack_val == min_d)
                    slack_variables.append(slack_val)
                    slack_weights.append(500) # Higher weight for day counts
                continue
                
            total_days = sum(rd_vars)
            
            # Min Days Slack
            slack_min = model.NewIntVar(0, min_d, f"slack_min_days_{r}_{d}")
            model.Add(total_days >= min_d - slack_min)
            slack_variables.append(slack_min)
            slack_weights.append(500)
            
            # Max Days Slack
            slack_max = model.NewIntVar(0, len(dates), f"slack_max_days_{r}_{d}")
            model.Add(total_days <= max_d + slack_max)
            slack_variables.append(slack_max)
            slack_weights.append(500)

        # 4. Objective: Minimize weighted sum of slacks
        objective_terms = []
        for var, weight in zip(slack_variables, slack_weights):
            objective_terms.append(var * weight)
            
        model.Minimize(sum(objective_terms))
        
        # 5. Apply No-Goods exclusion constraints from previous iterations
        for excl in exclude_constraints:
            # excl is a tuple of (active_vars, inactive_vars)
            # We enforce that they cannot all match:
            # sum(1 - x) + sum(x) >= 1
            terms = []
            for var_key in excl["active"]:
                if var_key in x:
                    terms.append(1 - x[var_key])
            for var_key in excl["inactive"]:
                if var_key in x:
                    terms.append(x[var_key])
            model.Add(sum(terms) >= 1)
            
        # 6. Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10.0 # Bounded execution
        
        # If this is an alternative run, we also bound the objective to the optimal first run value
        if first_run_optimal_val is not None:
            model.Add(sum(objective_terms) <= first_run_optimal_val)
            
        status = solver.Solve(model)
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            obj_val = int(solver.ObjectiveValue())
            if first_run_optimal_val is None:
                first_run_optimal_val = obj_val
                
            # Extract Assignments
            assigned = []
            active_keys = []
            inactive_keys = []
            
            for (r, d, t), var in x.items():
                if solver.Value(var) == 1:
                    assigned.append({
                        "resource_name": r,
                        "dept_name": d,
                        "date": t,
                        "hours": default_shift_hours
                    })
                    active_keys.append((r, d, t))
                else:
                    inactive_keys.append((r, d, t))
                    
            # Extract Violations (Slacks > 0)
            violations = []
            
            # Re-compute violations to report unscaled numbers
            # Resource Hours Violations
            for r in resource_names:
                min_h, max_h = res_bounds[r]
                r_vars = [x[(r, d, t)] for d in dept_names for t in dates if (r, d, t) in x]
                actual_h = sum(solver.Value(var) for var in r_vars) * default_shift_hours
                if actual_h < min_h:
                    violations.append({
                        "violation_type": "MIN_HOURS",
                        "resource_name": r,
                        "dept_name": None,
                        "description": f"Resource {r} scheduled for {actual_h} hours, which is below min hours {min_h}."
                    })
                elif actual_h > max_h:
                    violations.append({
                        "violation_type": "MAX_HOURS",
                        "resource_name": r,
                        "dept_name": None,
                        "description": f"Resource {r} scheduled for {actual_h} hours, which is above max hours {max_h}."
                    })
                    
            # Department Hours Violations
            for d in dept_names:
                min_h, max_h = dept_bounds[d]
                d_vars = [x[(r, d, t)] for r in resource_names for t in dates if (r, d, t) in x]
                actual_h = sum(solver.Value(var) for var in d_vars) * default_shift_hours
                if actual_h < min_h:
                    violations.append({
                        "violation_type": "MIN_HOURS",
                        "resource_name": None,
                        "dept_name": d,
                        "description": f"Department {d} received {actual_h} hours, which is below required min hours {min_h}."
                    })
                elif actual_h > max_h:
                    violations.append({
                        "violation_type": "MAX_HOURS",
                        "resource_name": None,
                        "dept_name": d,
                        "description": f"Department {d} received {actual_h} hours, which is above required max hours {max_h}."
                    })
                    
            # Mapping Day Limits Violations
            for (r, d), mapping in map_lookup.items():
                if not mapping["is_feasible"]:
                    continue
                min_d = mapping["min_days"]
                max_d = mapping["max_days"]
                rd_vars = [x[(r, d, t)] for t in dates if (r, d, t) in x]
                actual_d = sum(solver.Value(var) for var in rd_vars)
                if actual_d < min_d:
                    violations.append({
                        "violation_type": "MIN_DAYS",
                        "resource_name": r,
                        "dept_name": d,
                        "description": f"Resource {r} scheduled for {actual_d} days in {d}, which is below min days {min_d}."
                    })
                elif actual_d > max_d:
                    violations.append({
                        "violation_type": "MAX_DAYS",
                        "resource_name": r,
                        "dept_name": d,
                        "description": f"Resource {r} scheduled for {actual_d} days in {d}, which is above max days {max_d}."
                    })
                    
            alternatives.append({
                "assignments": assigned,
                "violations": violations,
                "violation_score": obj_val
            })
            
            # Add to exclusion list for next loop
            exclude_constraints.append({
                "active": active_keys,
                "inactive": inactive_keys
            })
        else:
            # No more alternatives found
            break
            
    if not alternatives:
        return {
            "status": "INFEASIBLE",
            "alternatives": [],
            "errors": ["No feasible schedule could be generated, even with violations."]
        }
        
    best_score = alternatives[0]["violation_score"]
    status_str = "SUCCESS" if best_score == 0 else "FEASIBLE_WITH_VIOLATIONS"
    
    return {
        "status": status_str,
        "alternatives": alternatives,
        "errors": []
    }

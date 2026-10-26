"""NCTB-style result computation.

Pass rules implemented
- Each subject: total% >= pass mark (default 33) AND every component threshold met
  (CQ / written(CQ+Short) / MCQ / practical, depending on the subject structure).
- Bangla 101+102 and English 107+108 are graded as ONE combined unit (200 marks):
  combined total and combined component totals must pass.
- A custom pass mark (e.g. 40) scales every component threshold by pass/33.
- 4th (optional) subject: only GP above 2.00 is added; failing it never fails the student.
- Any compulsory unit with F => GPA 0.00, status "Failed".
"""
from decimal import Decimal
from math import ceil

from ..models import ClassSubject, Mark, SchoolConfig, Student

COMBINED_PAIRS = {"101": "102", "107": "108"}
SECOND_PAPERS = set(COMBINED_PAIRS.values())
NCTB_PASS = 33
COMPONENTS = ("cq", "short", "mcq", "practical", "continuous_assessment", "viva", "assignment")


def _f(v):
    return float(v or 0)


def _scaled(threshold, pass_pct):
    if not threshold:
        return 0
    if pass_pct == NCTB_PASS:
        return threshold
    return ceil(threshold * pass_pct / NCTB_PASS)


def grade_for_percent(pct, scale, pass_pct):
    """Return (grade, gp) for a percentage under the given pass mark."""
    if pct < pass_pct:
        return "F", 0.0
    for row in sorted(scale, key=lambda r: -r["min"]):
        if pct >= row["min"]:
            if row["grade"] == "F":  # pass mark set below the D boundary
                lowest_pass = sorted([r for r in scale if r["grade"] != "F"], key=lambda r: r["min"])[0]
                return lowest_pass["grade"], lowest_pass["gp"]
            return row["grade"], row["gp"]
    return "F", 0.0


def grade_for_gpa(gpa, scale):
    if gpa <= 0:
        return "F"
    for row in sorted(scale, key=lambda r: -r["gp"]):
        if gpa >= row["gp"] and row["grade"] != "F":
            return row["grade"]
    return "F"


def _subject_row(subject, mark, pass_pct, exam=None):
    """Marks and per-component pass flags for one subject."""
    absent = bool(mark and mark.absent)
    vals = {c: (0.0 if (mark is None or absent) else _f(getattr(mark, c))) for c in COMPONENTS}
    custom = ((exam.component_distribution or {}).get(subject.code, {}) if exam else {})
    return {
        "subject": subject, "entered": mark is not None, "absent": absent, **vals,
        "total": sum(vals.values()), "max": custom.get("total", subject.total_marks),
        "distribution": {"cq": custom.get("cq", subject.cq_max), "short": custom.get("short", subject.short_max),
                         "mcq": custom.get("mcq", subject.mcq_max), "practical": custom.get("practical", subject.practical_max),
                         "continuous_assessment": custom.get("continuous_assessment", 0), "viva": custom.get("viva", 0),
                         "assignment": custom.get("assignment", 0), "total": custom.get("total", subject.total_marks)},
    }


def _components_pass(rows, pass_pct, exam=None):
    """rows = 1 subject row or 2 (combined). Thresholds are summed across the rows."""
    cq = sum(_f(r["cq"]) for r in rows)
    short = sum(_f(r["short"]) for r in rows)
    mcq = sum(_f(r["mcq"]) for r in rows)
    prac = sum(_f(r["practical"]) for r in rows)
    ok = True
    def t(attr):
        total = 0
        for r in rows:
            custom = ((exam.component_distribution or {}).get(r["subject"].code, {}) if exam else {})
            total += _scaled(custom.get(attr, getattr(r["subject"], attr)), pass_pct)
        return total
    if t("cq_pass") and cq < t("cq_pass"):
        ok = False
    if t("written_pass") and (cq + short) < t("written_pass"):
        ok = False
    if t("mcq_pass") and mcq < t("mcq_pass"):
        ok = False
    if t("practical_pass") and prac < t("practical_pass"):
        ok = False
    return ok


def applicable_class_subjects(student):
    qs = ClassSubject.objects.filter(school_class=student.school_class, is_enabled=True).select_related("subject")
    out = []
    for cs in qs:
        if cs.group_id and cs.group_id != student.group_id:
            continue
        if cs.subject.religion and cs.subject.religion != student.religion:
            continue
        if cs.is_optional and student.fourth_subject_id != cs.subject_id:
            continue
        out.append(cs)
    return out


def compute_result(student, exam, config=None, marks_by_subject=None):
    config = config or SchoolConfig.get()
    scale = exam.grading_scale or config.grading_scale
    pass_pct = exam.pass_mark or config.default_pass_mark
    if marks_by_subject is None:
        marks_by_subject = {m.subject_id: m for m in Mark.objects.filter(student=student, exam=exam)}

    class_subjects = sorted(applicable_class_subjects(student), key=lambda cs: cs.subject.code)
    rows = {}
    for cs in class_subjects:
        r = _subject_row(cs.subject, marks_by_subject.get(cs.subject_id), pass_pct, exam)
        r["is_fourth"] = cs.is_optional
        rows[cs.subject.code] = r

    # grading units (combined papers become one unit)
    units = []
    for code, r in rows.items():
        if code in SECOND_PAPERS:
            continue
        pair = COMBINED_PAIRS.get(code)
        members = [r] + ([rows[pair]] if pair in rows else [])
        total = sum(m["total"] for m in members)
        mx = sum(m["max"] for m in members)
        pct = total / mx * 100 if mx else 0
        grade, gp = grade_for_percent(pct, scale, pass_pct)
        comps_ok = _components_pass(members, pass_pct, exam) if exam.require_component_pass else True
        absent = any(m["absent"] for m in members)
        passed = (pct >= pass_pct) and comps_ok and not absent
        if not passed:
            grade, gp = "F", 0.0
        units.append({"members": members, "total": total, "max": mx, "percent": round(pct, 2),
                      "grade": grade, "gp": gp, "passed": passed, "is_fourth": r["is_fourth"]})

    compulsory = [u for u in units if not u["is_fourth"]]
    fourth = [u for u in units if u["is_fourth"]]
    failed_subjects = [u["members"][0]["subject"].code for u in compulsory if not u["passed"]]
    incomplete = any(not m["entered"] for u in units for m in u["members"] if not u["is_fourth"])

    if incomplete:
        status = "Incomplete"
    elif failed_subjects:
        status = "Failed"
    else:
        status = "Passed"

    gpa = 0.0
    if compulsory and status == "Passed":
        bonus = sum(max(u["gp"] - 2.0, 0) for u in fourth)
        gpa = min(round((sum(u["gp"] for u in compulsory) + bonus) / len(compulsory), 2), 5.0)
    if status == "Incomplete":
        gpa = 0.0

    # flatten to per-subject output rows
    out_rows = []
    for u in units:
        combined = len(u["members"]) > 1
        for m in u["members"]:
            s = m["subject"]
            out_rows.append({
                "subject": s.name, "subject_bn": s.name_bn, "code": s.code,
                "is_fourth": u["is_fourth"],
                "cq": m["cq"], "short": m["short"], "mcq": m["mcq"], "practical": m["practical"],
                "continuous_assessment": m.get("continuous_assessment", 0), "viva": m.get("viva", 0), "assignment": m.get("assignment", 0),
                "total": m["total"], "max": m["max"],
                "absent": m["absent"], "entered": m["entered"],
                "combined": combined,
                "unit_total": u["total"], "unit_max": u["max"], "unit_percent": u["percent"],
                "grade": u["grade"], "gp": u["gp"], "passed": u["passed"],
                "distribution": m["distribution"],
            })

    grand_total = sum(r["total"] for r in out_rows)
    full_marks = sum(r["max"] for r in out_rows if not r["is_fourth"])
    return {
        "student": {"id": student.id, "student_id": student.student_id, "name": student.name,
                    "roll": student.roll, "class": student.school_class.name,
                    "section": student.section.name if student.section else None,
                    "group": student.group.name if student.group else None,
                    "father_name": student.father_name, "mother_name": student.mother_name,
                    "dob": student.dob.isoformat() if student.dob else None,
                    "registration_no": student.registration_no},
        "exam": {"id": exam.id, "name": exam.name, "academic_year": exam.academic_year,
                 "pass_mark": pass_pct},
        "subjects": out_rows,
        "grand_total": grand_total,
        "full_marks": full_marks,
        "gpa": gpa,
        "grade": grade_for_gpa(gpa, scale) if status == "Passed" else "F",
        "status": status,
        "failed_subjects": failed_subjects,
        "grading_scale": [
            {"range": f'{r["min"]}-{r["max"]}', "grade": r["grade"], "gp": r["gp"]} for r in scale
        ],
    }


def compute_exam_results(exam, section=None):
    """All students of the exam's class with merit position."""
    config = SchoolConfig.get()
    students = Student.objects.filter(school_class=exam.school_class, is_active=True) \
        .select_related("school_class", "section", "group")
    if section:
        students = students.filter(section_id=section)
    all_marks = {}
    for m in Mark.objects.filter(exam=exam, student__in=students):
        all_marks.setdefault(m.student_id, {})[m.subject_id] = m
    results = [compute_result(s, exam, config, all_marks.get(s.id, {})) for s in students]
    ranked = sorted(
        results,
        key=lambda r: (r["status"] != "Passed", -r["gpa"], -r["grand_total"], r["student"]["roll"] or 10**6),
    )
    for i, r in enumerate(ranked, 1):
        r["merit_position"] = i if r["status"] == "Passed" else None
    return ranked

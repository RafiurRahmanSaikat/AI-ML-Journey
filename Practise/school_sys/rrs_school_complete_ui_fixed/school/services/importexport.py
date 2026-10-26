import csv
import io
import json
from datetime import date, datetime

from django.db import transaction
from openpyxl import Workbook, load_workbook
from django.http import HttpResponse

from ..models import Exam, Group, Mark, Section, SchoolClass, Student, Subject

STUDENT_COLUMNS = ["student_id", "name", "gender", "dob", "religion", "father_name", "mother_name",
                   "mobile", "address", "class", "section", "group", "roll", "registration_no"]
MARK_COLUMNS = ["student_id", "subject_code", "cq", "short", "mcq", "practical", "continuous_assessment", "viva", "assignment", "absent"]


def read_rows(uploaded):
    """Return list of dicts from a CSV or XLSX upload."""
    name = uploaded.name.lower()
    if name.endswith(".json"):
        payload = json.loads(uploaded.read().decode("utf-8-sig"))
        if isinstance(payload, dict):
            payload = payload.get("results", payload.get("data", [payload]))
        if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
            raise ValueError("JSON upload must be an array of objects (or {results: [...]})")
        return [{str(k).strip().lower(): v for k, v in row.items()} for row in payload]
    if name.endswith((".xlsx", ".xlsm")):
        wb = load_workbook(uploaded, read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        headers = [str(h).strip().lower() if h is not None else "" for h in next(it)]
        return [dict(zip(headers, r)) for r in it if any(c not in (None, "") for c in r)]
    text = uploaded.read().decode("utf-8-sig")
    return [{(k or "").strip().lower(): v for k, v in row.items()} for row in csv.DictReader(io.StringIO(text))]


def write_response(columns, rows, file_type, filename):
    if file_type == "json":
        payload = json.dumps([dict(zip(columns, row)) for row in rows], ensure_ascii=False, indent=2)
        resp = HttpResponse(payload, content_type="application/json; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{filename}.json"'
        return resp
    if file_type == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.append(columns)
        for r in rows:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        resp = HttpResponse(buf.getvalue(),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
        return resp
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    resp.write("\ufeff")
    w = csv.writer(resp)
    w.writerow(columns)
    w.writerows(rows)
    return resp


def _date(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Bad date '{v}' (use YYYY-MM-DD)")


def _num(v):
    return 0 if v in (None, "") else float(v)


def _bool(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y", "absent")


def export_students(qs, file_type):
    rows = [[s.student_id, s.name, s.gender, s.dob.isoformat() if s.dob else "", s.religion, s.father_name,
             s.mother_name, s.mobile, s.address, s.school_class.name, s.section.name if s.section else "",
             s.group.name if s.group else "", s.roll or "", s.registration_no] for s in qs]
    return write_response(STUDENT_COLUMNS, rows, file_type, "students")


@transaction.atomic
def import_students(rows):
    created = updated = 0
    errors = []
    for i, r in enumerate(rows, start=2):
        try:
            # Accept both the API template and the uploaded school register headers.
            aliases = {"id": "student_id", "roll no": "roll", "father name": "father_name",
                       "mother name": "mother_name", "date of birth": "dob", "phone": "mobile",
                       "class name": "class", "class_name": "class", "section name": "section",
                       "student name": "name"}
            r = {aliases.get(str(k).strip().lower(), str(k).strip().lower()): v for k, v in r.items() if k is not None}
            class_value = str(r.get("class", "")).strip()
            class_aliases = {"six": "Six", "sixth": "Six", "6": "Six", "seven": "Seven", "7": "Seven",
                             "eight": "Eight", "8": "Eight", "nine": "Nine", "9": "Nine", "ten": "Ten", "10": "Ten"}
            cls_name = class_aliases.get(class_value.lower(), class_value)
            cls = SchoolClass.objects.get(name__iexact=cls_name)
            section = None
            if r.get("section"):
                section, _ = Section.objects.get_or_create(school_class=cls, name=str(r["section"]).strip())
            group = Group.objects.get(name__iexact=str(r["group"]).strip()) if r.get("group") else None
            data = dict(
                name=str(r["name"]).strip(), gender=(str(r.get("gender") or "F").strip()[:1].upper()),
                dob=_date(r.get("dob")), religion=str(r.get("religion") or "Islam").strip(),
                father_name=r.get("father_name") or "", mother_name=r.get("mother_name") or "",
                mobile=str(r.get("mobile") or "").replace('="', '').replace('"', ''), address=r.get("address") or "",
                school_class=cls, section=section, group=group,
                roll=int(r["roll"]) if r.get("roll") not in (None, "") else None,
            )
            sid = str(r.get("student_id") or "").strip()
            obj = Student.objects.filter(student_id=sid).first() if sid else None
            if not obj:
                obj = Student.objects.filter(name__iexact=data["name"], school_class=cls, section=section).first()
            if obj:
                for k, v in data.items():
                    setattr(obj, k, v)
                obj.save()
                updated += 1
            else:
                Student.objects.create(**data)
                created += 1
        except Exception as e:  # report row-level errors without aborting the whole file
            errors.append({"row": i, "error": str(e)})
    return {"created": created, "updated": updated, "errors": errors}


def export_marks(qs, file_type):
    rows = [[m.student.student_id, m.subject.code, float(m.cq), float(m.short), float(m.mcq),
             float(m.practical), float(m.continuous_assessment), float(m.viva), float(m.assignment),
             "yes" if m.absent else ""] for m in qs.select_related("student", "subject")]
    return write_response(MARK_COLUMNS, rows, file_type, "marks")


@transaction.atomic
def import_marks(rows, exam):
    saved = 0
    errors = []
    for i, r in enumerate(rows, start=2):
        try:
            student = Student.objects.get(student_id=str(r["student_id"]).strip())
            subject = Subject.objects.get(code=str(r["subject_code"]).strip())
            vals = {c: _num(r.get(c)) for c in ("cq", "short", "mcq", "practical", "continuous_assessment", "viva", "assignment")}
            custom = (exam.component_distribution or {}).get(subject.code, {})
            for c, v in vals.items():
                max_field = f"{c}_max"
                maximum = custom.get(c, getattr(subject, max_field, 0))
                if maximum and v > maximum:
                    raise ValueError(f"{c}={v} exceeds max {maximum} for {subject.code}")
            Mark.objects.update_or_create(student=student, exam=exam, subject=subject,
                                          defaults={**vals, "absent": _bool(r.get("absent"))})
            saved += 1
        except Exception as e:
            errors.append({"row": i, "error": str(e)})
    return {"saved": saved, "errors": errors}

import csv
from pathlib import Path

from django.core.management import BaseCommand, call_command
from django.db import transaction

from school.models import Exam, Group, Mark, SchoolClass, SchoolConfig, Section, Student, Subject
from school.services.importexport import import_students, read_rows

BASE = Path(__file__).resolve().parents[3]
SUBJECT_MAP = {
    "eng1": ("107", "cq"), "eng2": ("108", "cq"),
    "math": ("109", "cq"), "sci": ("138", "cq"),
    "phy": ("136", "cq"), "chem": ("137", "cq"),
}


def clean(v):
    s = str(v or "").strip()
    if s.startswith('="') and s.endswith('"'):
        s = s[2:-1]
    return s


class Command(BaseCommand):
    help = "Seed the school, import the supplied student CSV and wide-format marks CSV, and create 2025/2026 exam history."

    def add_arguments(self, parser):
        parser.add_argument("--students", default=str(BASE / "data/students-list-2026-all-class-all-section.csv"))
        parser.add_argument("--marks", default=str(BASE / "data/marks.csv"))
        parser.add_argument("--skip-history", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        call_command("seed_data", verbosity=0)
        student_path, marks_path = Path(opts["students"]), Path(opts["marks"])
        if student_path.exists():
            with student_path.open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            result = import_students([{str(k).strip().lower(): v for k, v in row.items() if k is not None} for row in rows])
            self.stdout.write(f"Student CSV: created={result['created']}, updated={result['updated']}, errors={len(result['errors'])}")
            for err in result["errors"][:20]:
                self.stderr.write(f"Student row {err['row']}: {err['error']}")
        else:
            self.stderr.write(f"Student CSV not found: {student_path}")

        if not opts["skip_history"]:
            call_command("seed_academic_history", verbosity=0)

        if marks_path.exists():
            self.import_wide_marks(marks_path)
        else:
            self.stderr.write(f"Marks CSV not found: {marks_path}")
        self.stdout.write(self.style.SUCCESS("School CSV import finished."))

    def import_wide_marks(self, path):
        cls = SchoolClass.objects.get(level=10)
        exam, _ = Exam.objects.get_or_create(
            school_class=cls, name="Half-Yearly", academic_year="2026",
            defaults={"exam_type": Exam.Type.HALF_YEARLY, "pass_mark": 33, "require_component_pass": True},
        )
        science = Group.objects.get_or_create(name="Science")[0]
        # This source has subject totals in addition to component columns. Keep component values as supplied;
        # English papers use the source's single CQ score as a 100-mark component.
        distribution = dict(exam.component_distribution or {})
        for code in ("107", "108"):
            distribution[code] = {**distribution.get(code, {}), "cq": 100, "total": 100}
        exam.component_distribution = distribution
        exam.save(update_fields=["component_distribution"])
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            headers = [clean(h) for h in next(reader)]
            rows = list(reader)
        saved, unmatched, errors = 0, 0, []
        for line, raw in enumerate(rows, start=2):
            # CSV has several malformed rows with trailing empty cells; normalize rather than dropping them.
            raw = (raw + [""] * len(headers))[:len(headers)]
            row = {headers[i]: clean(raw[i]) for i in range(len(headers))}
            name, roll = row.get("Name", "").strip(), row.get("Roll", "").strip()
            if not name:
                continue
            student = Student.objects.filter(school_class=cls, name__iexact=name).first()
            if not student and roll:
                student = Student.objects.filter(school_class=cls, roll=int(roll)).first()
            if not student:
                unmatched += 1
                continue
            if not student.group_id:
                student.group = science
                student.save(update_fields=["group"])
            for prefix, (code, component) in SUBJECT_MAP.items():
                value = row.get(f"{prefix.title()}_CQ")
                # Header capitalization differs for Eng1/Eng2 and abbreviations; resolve case-insensitively.
                lower = {k.lower(): v for k, v in row.items()}
                value = lower.get(f"{prefix}_cq")
                if value in (None, ""):
                    continue
                try:
                    score = float(value)
                    subject = Subject.objects.get(code=code)
                    defaults = {"cq": score, "short": 0, "mcq": 0, "practical": 0,
                                "continuous_assessment": 0, "viva": 0, "assignment": 0, "absent": False}
                    # If the source has component marks, preserve them; totals are informational and not duplicated.
                    mcq_key = f"{prefix}_mcq"
                    prac_key = f"{prefix}_prac"
                    if lower.get(mcq_key) not in (None, ""):
                        defaults["mcq"] = float(lower[mcq_key])
                    if lower.get(prac_key) not in (None, ""):
                        defaults["practical"] = float(lower[prac_key])
                    Mark.objects.update_or_create(student=student, exam=exam, subject=subject, defaults=defaults)
                    saved += 1
                except (ValueError, Subject.DoesNotExist) as exc:
                    errors.append({"row": line, "subject": prefix, "error": str(exc)})
        self.stdout.write(f"Marks CSV: imported/updated subject rows={saved}, unmatched students={unmatched}, errors={len(errors)}")
        for err in errors[:20]:
            self.stderr.write(str(err))

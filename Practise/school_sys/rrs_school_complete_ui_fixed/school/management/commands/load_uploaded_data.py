import csv
import random
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from school.models import ClassSubject, Exam, Group, Mark, SchoolClass, SchoolConfig, Section, Student, Subject
from school.services.importexport import import_students
from school.services.result_engine import applicable_class_subjects


class Command(BaseCommand):
    help = "Load the supplied student register and marks CSVs; optionally generate 2025/2026 demo exam history."

    def add_arguments(self, parser):
        parser.add_argument("--students", required=True, help="Path to students-list CSV")
        parser.add_argument("--marks", required=True, help="Path to marks CSV")
        parser.add_argument("--generate-history", action="store_true", help="Generate deterministic demo marks for 2025 terms and 2026 Half-Yearly")

    @transaction.atomic
    def handle(self, *args, **opts):
        student_path, marks_path = Path(opts["students"]), Path(opts["marks"])
        if not student_path.exists() or not marks_path.exists():
            raise CommandError("Both --students and --marks paths must exist.")
        # Normalize class/section structures before import, including any new sections in the file.
        for label, level in (("Six", 6), ("Seven", 7), ("Eight", 8), ("Nine", 9), ("Ten", 10)):
            SchoolClass.objects.get_or_create(level=level, defaults={"name": label})
        for group_name in ("Science", "Arts", "Commerce", "General"):
            Group.objects.get_or_create(name=group_name)
        rows = []
        with student_path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                raw_class = (row.get("Class") or "").strip().lower()
                class_map = {"six": "Six", "6": "Six", "sixth": "Six", "seven": "Seven", "7": "Seven",
                             "eight": "Eight", "8": "Eight", "nine": "Nine", "9": "Nine", "ten": "Ten", "10": "Ten"}
                row["Class"] = class_map.get(raw_class, row.get("Class", ""))
                cls = SchoolClass.objects.filter(name__iexact=row["Class"]).first()
                if cls and row.get("Section"):
                    Section.objects.get_or_create(school_class=cls, name=row["Section"].strip())
                rows.append({
                    "student_id": row.get("ID") or "", "roll": row.get("Roll") or "", "name": row.get("Name") or "",
                    "father_name": row.get("Father Name") or "", "mother_name": row.get("Mother Name") or "",
                    "dob": row.get("Date of Birth") or "", "mobile": str(row.get("Phone") or "").replace('="', '').replace('"', ""),
                    "address": row.get("Address") or "", "class": row["Class"], "section": row.get("Section") or "",
                    "gender": "M" if (row.get("Name") or "").strip().upper().startswith(("MD ", "MOHAMMAD ", "EMON ", "ROBIN ", "RAZZAK ", "IMRAN ", "SABBIR ", "JOY ")) else "F",
                    "academic_year": "2026",
                })
        result = import_students(rows)
        self.stdout.write(self.style.SUCCESS(f"Student register: {result['created']} created, {result['updated']} updated, {len(result['errors'])} row errors."))
        if result["errors"]:
            self.stdout.write(self.style.WARNING(str(result["errors"][:10])))

        # Interpret the uploaded register's science-component columns to assign the matching Class Ten stream before seeding history.
        ten = SchoolClass.objects.get(level=10)
        science_group = Group.objects.filter(name="Science").first()
        with marks_path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                if any(row.get(k) not in (None, "") for k in ("Phy_CQ", "Chem_CQ", "Chem_Total")):
                    Student.objects.filter(school_class=ten, name__iexact=(row.get("Name") or "").strip()).update(group=science_group)
        # Keep the source file's explicitly listed Science column available for the 2026 Class Ten exam.
        if Subject.objects.filter(code="127").exists():
            ClassSubject.objects.get_or_create(school_class=ten, subject=Subject.objects.get(code="127"), group=None)

        # Set up the requested history. Demo marks are deterministic and are explicitly synthetic.
        if opts["generate_history"]:
            rng = random.Random(2026)
            exam_plan = [(2025, "First Term", "test"), (2025, "Mid Term", "test"),
                         (2025, "Final Exam", "annual"), (2026, "Half-Yearly", "half_yearly")]
            for cls in SchoolClass.objects.all():
                for year, name, typ in exam_plan:
                    exam, _ = Exam.objects.get_or_create(school_class=cls, name=name, academic_year=str(year),
                                                         defaults={"exam_type": typ, "pass_mark": None})
                    if Mark.objects.filter(exam=exam).exists():
                        continue
                    students = Student.objects.filter(school_class=cls, is_active=True).select_related("group", "section")
                    for student in students:
                        for cs in applicable_class_subjects(student):
                            sub = cs.subject
                            vals = {}
                            for component in ("cq", "short", "mcq", "practical"):
                                maximum = getattr(sub, f"{component}_max")
                                vals[component] = round(maximum * rng.uniform(0.35, 0.98), 1) if maximum else 0
                            Mark.objects.get_or_create(student=student, exam=exam, subject=sub, defaults=vals)
            self.stdout.write(self.style.SUCCESS("Created missing 2025 term/final and 2026 Half-Yearly demo history."))

        # Uploaded marks are the real provided scores and override matching demo entries.
        ten = SchoolClass.objects.get(level=10)
        exam, _ = Exam.objects.get_or_create(school_class=ten, name="Half-Yearly", academic_year="2026",
                                             defaults={"exam_type": "half_yearly"})
        by_name = {self._key(s.name): s for s in Student.objects.filter(school_class=ten)}
        subjects = {s.code: s for s in Subject.objects.all()}
        mapping = {
            "Eng1_Total": ("107", "cq"), "Eng2_Total": ("108", "cq"),
            "Math_CQ": ("109", "cq"), "Math_MCQ": ("109", "mcq"),
            "Sci_CQ": ("127", "cq"), "Sci_MCQ": ("127", "mcq"),
            "Phy_CQ": ("136", "cq"), "Phy_MCQ": ("136", "mcq"), "Phy_Prac": ("136", "practical"),
            "Chem_CQ": ("137", "cq"), "Chem_MCQ": ("137", "mcq"), "Chem_Prac": ("137", "practical"),
        }
        imported = skipped = 0
        with marks_path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row_num, row in enumerate(csv.DictReader(fh), start=2):
                # DictReader tolerates the uploaded file's extra trailing commas by placing them under key None.
                student = by_name.get(self._key(row.get("Name", "")))
                if not student:
                    skipped += 1
                    continue
                has_science = any(row.get(k) not in (None, "") for k in ("Phy_CQ", "Chem_CQ", "Chem_Total"))
                if has_science:
                    student.group = Group.objects.filter(name="Science").first()
                    student.save(update_fields=["group"])
                for column, (code, component) in mapping.items():
                    raw = row.get(column)
                    if raw in (None, ""):
                        continue
                    subject = subjects.get(code)
                    if not subject:
                        continue
                    try:
                        value = float(raw)
                    except (TypeError, ValueError):
                        continue
                    defaults = {"cq": 0, "short": 0, "mcq": 0, "practical": 0,
                                "continuous_assessment": 0, "viva": 0, "assignment": 0, "absent": False}
                    defaults[component] = value
                    obj, _ = Mark.objects.update_or_create(student=student, exam=exam, subject=subject, defaults=defaults)
                    imported += 1
        # The source file reports English as a single out-of-100 score in Eng*_Total, so those values are kept as CQ-like totals.
        exam.component_distribution = {
            "107": {"cq": 100, "short": 0, "mcq": 0, "practical": 0},
            "108": {"cq": 100, "short": 0, "mcq": 0, "practical": 0},
        }
        exam.save(update_fields=["component_distribution"])
        self.stdout.write(self.style.SUCCESS(f"Uploaded marks imported: {imported} component values; {skipped} rows did not match a Class Ten student by name."))

    @staticmethod
    def _key(value):
        return " ".join(str(value or "").strip().casefold().split())

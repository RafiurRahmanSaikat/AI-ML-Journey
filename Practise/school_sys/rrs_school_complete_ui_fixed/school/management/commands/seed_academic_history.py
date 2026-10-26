import random
from django.core.management.base import BaseCommand
from django.db import transaction
from school.models import Exam, Mark, SchoolClass, SchoolConfig, Student
from school.services.result_engine import applicable_class_subjects

EXAM_PLAN = [
    ("2025", "First Term", "other"), ("2025", "Mid Term", "test"), ("2025", "Final Exam", "annual"),
    ("2026", "First Term", "other"), ("2026", "Mid Term", "test"), ("2026", "Half-Yearly", "half_yearly"),
]

class Command(BaseCommand):
    help = "Create deterministic exam history and marks for Classes 6–10: all three 2025 terms and 2026 through Half-Yearly."

    @transaction.atomic
    def handle(self, *args, **opts):
        rng = random.Random(20261015)
        created_exams = created_marks = 0
        for cls in SchoolClass.objects.filter(level__gte=6, level__lte=10):
            students = list(Student.objects.filter(school_class=cls, is_active=True).select_related("group", "school_class", "fourth_subject"))
            for year, name, kind in EXAM_PLAN:
                exam, made = Exam.objects.get_or_create(school_class=cls, name=name, academic_year=year,
                    defaults={"exam_type": kind, "pass_mark": 33, "require_component_pass": True})
                created_exams += int(made)
                for student in students:
                    for cs in applicable_class_subjects(student):
                        subject = cs.subject
                        # Keep real marks from the supplied 2026 half-yearly CSV intact.
                        if year == "2026" and name == "Half-Yearly" and Mark.objects.filter(student=student, exam=exam, subject=subject).exists():
                            continue
                        ability = rng.uniform(0.43, 0.94)
                        vals = {}
                        for comp in ("cq", "short", "mcq", "practical"):
                            maximum = getattr(subject, f"{comp}_max", 0)
                            vals[comp] = round(maximum * min(1, max(0, rng.gauss(ability, 0.08))), 1) if maximum else 0
                        vals.update(continuous_assessment=0, viva=0, assignment=0, absent=False)
                        _, made = Mark.objects.update_or_create(student=student, exam=exam, subject=subject, defaults=vals)
                        created_marks += int(made)
        cfg = SchoolConfig.get()
        cfg.current_academic_year = "2026"
        cfg.save(update_fields=["current_academic_year"])
        self.stdout.write(self.style.SUCCESS(f"History ready: {created_exams} exams created, {created_marks} mark records created/updated."))

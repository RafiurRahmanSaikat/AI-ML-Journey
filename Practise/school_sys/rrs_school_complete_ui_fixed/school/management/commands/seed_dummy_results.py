import random

from django.core.management.base import BaseCommand
from django.db import transaction

from school.models import Exam, Group, Mark, SchoolClass, SchoolConfig, Section, Student, Subject
from school.services.result_engine import applicable_class_subjects

NAMES = ["Rahim Uddin", "Karim Hossain", "Ayesha Siddika", "Fatema Akter", "Sumaiya Islam", "Imran Hasan",
         "Nabila Rahman", "Tanvir Ahmed", "Mim Chowdhury", "Sabbir Hossain", "Rima Das", "Joy Barua",
         "Shuvo Dey", "Puja Rani", "Mahfuz Alam", "Tasnim Jahan", "Arif Billah", "Lamia Sultana"]


class Command(BaseCommand):
    help = "Create dummy students, exams and marks. Run seed_data first."

    @transaction.atomic
    def handle(self, *args, **opts):
        rnd = random.Random(42)
        year = SchoolConfig.get().current_academic_year
        groups = {g.name: g for g in Group.objects.all()}
        for cls in SchoolClass.objects.all():
            sec = Section.objects.filter(school_class=cls, name="A").first()
            plan = [None] if cls.level <= 8 else ["Science", "Arts"]  # Commerce group exists but has no students
            for gname in plan:
                existing = Student.objects.filter(school_class=cls, group=groups.get(gname)).count()
                for i in range(existing, 6):
                    fourth = None
                    if gname == "Science" and i % 2 == 0:
                        fourth = Subject.objects.get(code="126")
                    if gname == "Arts" and i % 2 == 0:
                        fourth = Subject.objects.get(code="134")
                    Student.objects.create(
                        name=rnd.choice(NAMES), gender=rnd.choice("MF"), school_class=cls, section=sec,
                        group=groups.get(gname), roll=i + 1, fourth_subject=fourth,
                        religion="Hindu" if i == 5 else "Islam")

            kinds = [("Half Yearly", "half_yearly"), ("Annual", "annual")]
            if cls.level == 10:
                kinds += [("Pre-Test", "pre_test"), ("Model Test", "model_test"), ("Test Exam", "test")]
            for name, typ in kinds:
                exam, _ = Exam.objects.get_or_create(school_class=cls, name=name, academic_year=year,
                                                     defaults={"exam_type": typ})
                for st in Student.objects.filter(school_class=cls):
                    ability = rnd.uniform(0.38, 0.95)
                    for cs in applicable_class_subjects(st):
                        s = cs.subject
                        vals = {c: round(getattr(s, f"{c}_max") * min(1, max(0, rnd.gauss(ability, 0.08))))
                                for c in ("cq", "short", "mcq", "practical")}
                        Mark.objects.update_or_create(student=st, exam=exam, subject=s, defaults=vals)
        self.stdout.write(self.style.SUCCESS("Dummy students, exams and marks created."))

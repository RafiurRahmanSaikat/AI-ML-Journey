from django.db import models
from django.core.exceptions import ValidationError as DjangoValidationError
from apps.academics.models import SchoolClass
from apps.students.models import Student
class Subject(models.Model):
    code = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=120)
    name_bn = models.CharField(max_length=120, blank=True)
    group = models.CharField(max_length=16, choices=[("COMMON","Common"),("SCIENCE","Science"),("HUMANITIES","Humanities"),("BUSINESS","Business"),("OPTIONAL","Optional")], default="COMMON")
    total_marks = models.PositiveSmallIntegerField(default=100)
    active = models.BooleanField(default=True)
    def __str__(self): return f"{self.code} - {self.name}"
class Exam(models.Model):
    class Kind(models.TextChoices):
        HALF_YEARLY="HALF_YEARLY","Half Yearly"
        ANNUAL="ANNUAL","Annual"
        PRE_TEST="PRE_TEST","Pre Test"
        MODEL_TEST="MODEL_TEST","Model Test"
        TEST="TEST","Test"
        OTHER="OTHER","Other"
    name = models.CharField(max_length=100)
    academic_year = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=20, choices=Kind.choices)
    school_classes = models.ManyToManyField(SchoolClass, related_name="exams")
    subjects = models.ManyToManyField(Subject, through="ExamSubject", related_name="exams")
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["name","academic_year"], name="uniq_exam_name_year")]
        ordering = ["-academic_year","name"]
    def __str__(self): return f"{self.name} {self.academic_year}"
class ExamSubject(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT)
    total_marks = models.PositiveSmallIntegerField(default=100)
    cq_max = models.PositiveSmallIntegerField(default=50)
    short_max = models.PositiveSmallIntegerField(default=20)
    mcq_max = models.PositiveSmallIntegerField(default=30)
    practical_max = models.PositiveSmallIntegerField(default=0)
    pass_marks = models.PositiveSmallIntegerField(default=33)
    written_pass_marks = models.PositiveSmallIntegerField(default=0)
    cq_pass_marks = models.PositiveSmallIntegerField(default=0)
    mcq_pass_marks = models.PositiveSmallIntegerField(default=0)
    practical_pass_marks = models.PositiveSmallIntegerField(default=0)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["exam","subject"], name="uniq_subject_per_exam")]
    def __str__(self): return f"{self.exam}: {self.subject}"
class Result(models.Model):
    student = models.ForeignKey(Student, related_name="results", on_delete=models.CASCADE)
    exam_subject = models.ForeignKey(ExamSubject, related_name="results", on_delete=models.CASCADE)
    cq_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    short_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    mcq_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    practical_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    grade = models.CharField(max_length=2, default="F")
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    passed = models.BooleanField(default=False)
    is_synthetic = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["student","exam_subject"], name="uniq_student_exam_subject")]
    def calculate(self):
        cfg = self.exam_subject
        self.total_marks = self.cq_marks + self.short_marks + self.mcq_marks + self.practical_marks
        # Component pass rules are configurable. A zero threshold disables a component gate.
        gates = [(self.cq_marks, cfg.cq_pass_marks), (self.mcq_marks, cfg.mcq_pass_marks),
                 (self.practical_marks, cfg.practical_pass_marks)]
        components_pass = all(threshold == 0 or score >= threshold for score, threshold in gates)
        if cfg.written_pass_marks and (self.cq_marks + self.short_marks) < cfg.written_pass_marks:
            components_pass = False
        percent = (float(self.total_marks) / cfg.total_marks * 100) if cfg.total_marks else 0
        if not components_pass or percent < 33:
            self.grade, self.grade_point, self.passed = "F", 0, False
        elif percent >= 80: self.grade, self.grade_point, self.passed = "A+", 5, True
        elif percent >= 70: self.grade, self.grade_point, self.passed = "A", 4, True
        elif percent >= 60: self.grade, self.grade_point, self.passed = "A-", 3.5, True
        elif percent >= 50: self.grade, self.grade_point, self.passed = "B", 3, True
        elif percent >= 40: self.grade, self.grade_point, self.passed = "C", 2, True
        else: self.grade, self.grade_point, self.passed = "D", 1, True
    def clean(self):
        cfg = self.exam_subject
        components = {
            "cq_marks": (self.cq_marks, cfg.cq_max),
            "short_marks": (self.short_marks, cfg.short_max),
            "mcq_marks": (self.mcq_marks, cfg.mcq_max),
            "practical_marks": (self.practical_marks, cfg.practical_max),
        }
        errors = {}
        for field, (score, maximum) in components.items():
            if score < 0 or score > maximum:
                errors[field] = f"Marks must be between 0 and {maximum}."
        if sum((score for score, _ in components.values()), 0) > cfg.total_marks:
            errors["total_marks"] = f"Component marks cannot exceed {cfg.total_marks}."
        if errors:
            raise DjangoValidationError(errors)

    def save(self, *args, **kwargs):
        self.calculate()
        self.clean()
        super().save(*args, **kwargs)
        # Bangla 1st+2nd and English 1st+2nd use the supplied combined 66/200 pass rule.
        paired_codes = {"101": "102", "102": "101", "107": "108", "108": "107"}
        code = self.exam_subject.subject.code
        partner_code = paired_codes.get(code)
        if partner_code:
            partner = Result.objects.filter(
                student_id=self.student_id,
                exam_subject__exam_id=self.exam_subject.exam_id,
                exam_subject__subject__code=partner_code,
            ).first()
            if partner:
                if (self.total_marks + partner.total_marks) < 66:
                    Result.objects.filter(pk__in=[self.pk, partner.pk]).update(
                        grade="F", grade_point=0, passed=False
                    )
                else:
                    partner.calculate()
                    Result.objects.filter(pk=partner.pk).update(
                        grade=partner.grade, grade_point=partner.grade_point, passed=partner.passed
                    )
                    Result.objects.filter(pk=self.pk).update(
                        grade=self.grade, grade_point=self.grade_point, passed=self.passed
                    )

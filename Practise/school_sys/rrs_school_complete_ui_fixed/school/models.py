from django.contrib.auth.models import AbstractUser
from django.db import models


def default_grading_scale():
    return [
        {"min": 80, "max": 100, "grade": "A+", "gp": 5.0},
        {"min": 70, "max": 79, "grade": "A", "gp": 4.0},
        {"min": 60, "max": 69, "grade": "A-", "gp": 3.5},
        {"min": 50, "max": 59, "grade": "B", "gp": 3.0},
        {"min": 40, "max": 49, "grade": "C", "gp": 2.0},
        {"min": 33, "max": 39, "grade": "D", "gp": 1.0},
        {"min": 0, "max": 32, "grade": "F", "gp": 0.0},
    ]


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super Admin"
        HEADMASTER = "headmaster", "Headmaster"
        TEACHER = "teacher", "Teacher"
        STUDENT = "student", "Student/Staff"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TEACHER)


class SchoolConfig(models.Model):
    """Singleton: always pk=1."""
    name = models.CharField(max_length=200, default="RRS High School H20")
    ein = models.CharField(max_length=20, default="12187")
    estd = models.PositiveIntegerField(default=2022)
    location = models.CharField(max_length=200, default="Cox's Bazar")
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to="logo/", blank=True, null=True)
    headmaster_name = models.CharField(max_length=120, default="Md. Shahjahan Khan")
    current_academic_year = models.CharField(max_length=9, default="2026")
    default_pass_mark = models.PositiveSmallIntegerField(default=33, help_text="Pass percentage per subject")
    student_id_pattern = models.CharField(max_length=100, default="RRS{Session}{ID:04d}", help_text="Tokens: Session, Year, Class, ClassCode, Section, Group, GroupCode, Roll, ID")
    grading_scale = models.JSONField(default=default_grading_scale)
    period_duration_minutes = models.PositiveSmallIntegerField(default=40)
    routine_settings = models.JSONField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.name


class SchoolClass(models.Model):
    name = models.CharField(max_length=20, unique=True)  # "Six"
    level = models.PositiveSmallIntegerField(unique=True)  # 6

    class Meta:
        ordering = ["level"]
        verbose_name_plural = "classes"

    def __str__(self):
        return self.name


class Group(models.Model):
    name = models.CharField(max_length=30, unique=True)  # Science / Arts / Commerce

    def __str__(self):
        return self.name


class ClassGroup(models.Model):
    """Enable/disable a stream for a particular class without deleting the group."""
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="group_settings")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="class_settings")
    is_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ("school_class", "group")
        ordering = ["school_class__level", "group__name"]

    def __str__(self):
        return f"{self.school_class} — {self.group}: {'enabled' if self.is_enabled else 'disabled'}"


class Section(models.Model):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=10)

    class Meta:
        unique_together = ("school_class", "name")
        ordering = ["school_class__level", "name"]

    def __str__(self):
        return f"{self.school_class} - {self.name}"


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="teacher")
    name = models.CharField(max_length=120)
    designation = models.CharField(max_length=80, default="Assistant Teacher")
    mobile = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to="teachers/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Subject(models.Model):
    class Religion(models.TextChoices):
        ALL = "", "All"
        ISLAM = "Islam", "Islam"
        HINDU = "Hindu", "Hindu"
        CHRISTIAN = "Christian", "Christian"
        BUDDHIST = "Buddhist", "Buddhist"

    name = models.CharField(max_length=150)
    name_bn = models.CharField(max_length=150, blank=True)
    code = models.CharField(max_length=10, unique=True)
    total_marks = models.PositiveSmallIntegerField(default=100)
    cq_max = models.PositiveSmallIntegerField(default=0)
    short_max = models.PositiveSmallIntegerField(default=0)
    mcq_max = models.PositiveSmallIntegerField(default=0)
    practical_max = models.PositiveSmallIntegerField(default=0)
    # pass thresholds at the NCTB 33% level; 0 = no separate threshold
    cq_pass = models.PositiveSmallIntegerField(default=0)
    written_pass = models.PositiveSmallIntegerField(default=0, help_text="Threshold on CQ+Short")
    mcq_pass = models.PositiveSmallIntegerField(default=0)
    practical_pass = models.PositiveSmallIntegerField(default=0)
    religion = models.CharField(max_length=10, choices=Religion.choices, blank=True, default="")

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class ClassSubject(models.Model):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="class_subjects")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="class_subjects")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True,
                              help_text="Blank = every group in this class")
    is_optional = models.BooleanField(default=False, help_text="4th-subject candidate")
    is_enabled = models.BooleanField(default=True, help_text="Whether this subject is active for this class/group")
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ("school_class", "subject", "group")
        ordering = ["school_class__level", "subject__code"]

    def __str__(self):
        return f"{self.school_class}: {self.subject}"


class Student(models.Model):
    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"

    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="student")
    name = models.CharField(max_length=120)
    name_bn = models.CharField(max_length=120, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices, default=Gender.FEMALE)
    dob = models.DateField(null=True, blank=True)
    religion = models.CharField(max_length=10, default="Islam")
    father_name = models.CharField(max_length=120, blank=True)
    mother_name = models.CharField(max_length=120, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to="students/", blank=True, null=True)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.PROTECT, related_name="students")
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="students")
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
    roll = models.PositiveIntegerField(null=True, blank=True)
    student_id = models.CharField(max_length=20, unique=True, blank=True)
    registration_no = models.CharField(max_length=30, blank=True)
    academic_year = models.CharField(max_length=9, blank=True)
    fourth_subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="+")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["school_class__level", "section__name", "roll", "name"]

    def save(self, *args, **kwargs):
        if not self.academic_year:
            self.academic_year = SchoolConfig.get().current_academic_year
        if not self.student_id:
            self.student_id = f"TMP{id(self)}"
            super().save(*args, **kwargs)
            cfg = SchoolConfig.get()
            group_code = (self.group.name[:1].upper() if self.group_id else "G")
            values = {
                "Session": self.academic_year, "Year": self.academic_year,
                "Class": self.school_class.name, "ClassCode": str(self.school_class.level),
                "Section": self.section.name if self.section_id else "X",
                "Group": self.group.name if self.group_id else "General", "GroupCode": group_code,
                "Roll": str(self.roll or self.pk), "ID": self.pk,
            }
            try:
                candidate = cfg.student_id_pattern.format_map(values)
            except (KeyError, ValueError):
                candidate = f"RRS{self.academic_year}{self.pk:04d}"
            if Student.objects.exclude(pk=self.pk).filter(student_id=candidate).exists():
                candidate = f"{candidate}-{self.pk:04d}"
            self.student_id = candidate[:20]
            if not self.registration_no:
                self.registration_no = f"REG-{self.academic_year}-{self.pk:05d}"
            super().save(update_fields=["student_id", "registration_no"])
            return
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.student_id})"


class Exam(models.Model):
    class Type(models.TextChoices):
        HALF_YEARLY = "half_yearly", "Half Yearly"
        ANNUAL = "annual", "Annual / Final"
        PRE_TEST = "pre_test", "Pre-Test"
        MODEL_TEST = "model_test", "Model Test"
        TEST = "test", "Test Exam"
        OTHER = "other", "Other"

    name = models.CharField(max_length=80)
    exam_type = models.CharField(max_length=20, choices=Type.choices, default=Type.OTHER)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="exams")
    academic_year = models.CharField(max_length=9)
    pass_mark = models.PositiveSmallIntegerField(null=True, blank=True,
                                                 help_text="Pass %, overrides school default (33)")
    component_distribution = models.JSONField(default=dict, blank=True, help_text="Optional per-subject component maxima/pass rules")
    grading_scale = models.JSONField(null=True, blank=True, help_text="Optional exam-specific grading scale")
    require_component_pass = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        unique_together = ("school_class", "name", "academic_year")
        ordering = ["-academic_year", "school_class__level", "id"]

    def __str__(self):
        return f"{self.name} {self.academic_year} - {self.school_class}"


class Mark(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="marks")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="marks")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="marks")
    cq = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    short = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    mcq = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    practical = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    continuous_assessment = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    viva = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    assignment = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    absent = models.BooleanField(default=False)

    class Meta:
        unique_together = ("student", "exam", "subject")

    @property
    def total(self):
        return self.cq + self.short + self.mcq + self.practical + self.continuous_assessment + self.viva + self.assignment

    def __str__(self):
        return f"{self.student_id}/{self.exam_id}/{self.subject.code}"

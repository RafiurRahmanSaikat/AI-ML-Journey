from django.db import models
from apps.academics.models import SchoolClass, Section
class Student(models.Model):
    class Group(models.TextChoices):
        SCIENCE = "SCIENCE", "Science"
        HUMANITIES = "HUMANITIES", "Humanities / Arts"
        BUSINESS = "BUSINESS", "Business Studies"
    admission_no = models.CharField(max_length=32, unique=True, blank=True)
    roll = models.PositiveSmallIntegerField(null=True, blank=True)
    name = models.CharField(max_length=180)
    father_name = models.CharField(max_length=180, blank=True)
    father_name_bn = models.CharField(max_length=180, blank=True)
    mother_name = models.CharField(max_length=180, blank=True)
    mother_name_bn = models.CharField(max_length=180, blank=True)
    school_class = models.ForeignKey(SchoolClass, related_name="students", on_delete=models.PROTECT)
    section = models.ForeignKey(Section, related_name="students", on_delete=models.PROTECT)
    group = models.CharField(max_length=16, choices=Group.choices, default=Group.HUMANITIES)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["school_class__numeric_level","section__name","roll","name"]
        indexes = [models.Index(fields=["school_class","section","roll"]), models.Index(fields=["name"])]
    def save(self, *args, **kwargs):
        if self.section_id and self.school_class_id and self.section.school_class_id != self.school_class_id:
            raise ValueError("Student class must match the selected section's class.")
        if not self.admission_no:
            # Stable enough for local setup; unique collision is retried by caller/importer.
            from django.utils.crypto import get_random_string
            self.admission_no = "ADM-" + get_random_string(8).upper()
        super().save(*args, **kwargs)
    def __str__(self): return f"{self.name} ({self.admission_no})"

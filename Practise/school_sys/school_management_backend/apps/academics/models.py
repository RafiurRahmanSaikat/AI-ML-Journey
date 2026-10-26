from django.db import models
class SchoolClass(models.Model):
    name = models.CharField(max_length=30, unique=True)  # e.g. Six, Seven, Eight, Nine, Ten
    numeric_level = models.PositiveSmallIntegerField(unique=True)
    active = models.BooleanField(default=True)
    class Meta:
        ordering = ["numeric_level"]
    def __str__(self): return self.name
class Section(models.Model):
    school_class = models.ForeignKey(SchoolClass, related_name="sections", on_delete=models.PROTECT)
    name = models.CharField(max_length=20)
    capacity = models.PositiveSmallIntegerField(default=60)
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["school_class","name"], name="uniq_section_per_class")]
        ordering = ["school_class__numeric_level","name"]
    def __str__(self): return f"{self.school_class.name}-{self.name}"

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from . import models

admin.site.register(models.User, UserAdmin)
for m in (models.SchoolConfig, models.SchoolClass, models.Section, models.Group, models.Teacher,
          models.Subject, models.ClassSubject, models.Student, models.Exam, models.Mark):
    admin.site.register(m)

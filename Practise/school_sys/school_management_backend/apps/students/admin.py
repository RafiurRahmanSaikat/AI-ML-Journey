from django.contrib import admin
from .models import Student
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display=("admission_no","roll","name","school_class","section","group","active")
    list_filter=("school_class","section","group","active")
    search_fields=("admission_no","name","father_name","phone")

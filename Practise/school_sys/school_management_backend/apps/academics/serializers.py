from rest_framework import serializers
from .models import SchoolClass, Section
class SchoolClassSerializer(serializers.ModelSerializer):
    class Meta: model=SchoolClass; fields="__all__"
class SectionSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    student_count = serializers.IntegerField(source="students.count", read_only=True)
    class Meta: model=Section; fields=["id","school_class","class_name","name","capacity","active","student_count"]

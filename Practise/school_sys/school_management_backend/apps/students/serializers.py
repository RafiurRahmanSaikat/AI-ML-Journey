from rest_framework import serializers
from .models import Student
class StudentSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    class Meta:
        model=Student
        fields=["id","admission_no","roll","name","father_name","father_name_bn","mother_name","mother_name_bn",
                "school_class","class_name","section","section_name","group","date_of_birth","phone","address","active","created_at","updated_at"]
        read_only_fields=["admission_no","created_at","updated_at"]
    def validate(self, attrs):
        cls=attrs.get("school_class", getattr(self.instance,"school_class",None))
        sec=attrs.get("section", getattr(self.instance,"section",None))
        if cls and sec and sec.school_class_id != cls.id:
            raise serializers.ValidationError({"section":"Section must belong to the selected class."})
        return attrs

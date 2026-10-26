from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from apps.core.permissions import AdminOrHeadmaster
from apps.students.models import Student
from .models import SchoolClass, Section
from .serializers import SchoolClassSerializer, SectionSerializer
class SchoolClassViewSet(viewsets.ModelViewSet):
    queryset=SchoolClass.objects.all()
    serializer_class=SchoolClassSerializer
    permission_classes=[AdminOrHeadmaster]
class SectionViewSet(viewsets.ModelViewSet):
    queryset=Section.objects.select_related("school_class").all()
    serializer_class=SectionSerializer
    permission_classes=[AdminOrHeadmaster]
    def destroy(self, request, *args, **kwargs):
        section=self.get_object()
        target_id=request.query_params.get("move_to_section")
        count=section.students.count()
        if count and not target_id:
            raise ValidationError({"move_to_section":"This section has students. Supply ?move_to_section=<destination_section_id> to move them before deletion."})
        with transaction.atomic():
            if count:
                try: target=Section.objects.get(pk=target_id, school_class=section.school_class)
                except Section.DoesNotExist: raise ValidationError({"move_to_section":"Destination must be another section in the same class."})
                Student.objects.filter(section=section).update(section=target)
            section.delete()
        return Response({"deleted":True,"students_moved":count},status=status.HTTP_200_OK)

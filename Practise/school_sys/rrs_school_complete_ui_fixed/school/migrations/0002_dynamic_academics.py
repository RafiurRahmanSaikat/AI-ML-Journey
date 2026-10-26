from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("school", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="schoolconfig", name="student_id_pattern",
            field=models.CharField(default="RRS{Session}{ID:04d}", help_text="Tokens: Session, Year, Class, ClassCode, Section, Group, GroupCode, Roll, ID", max_length=100),
        ),
        migrations.CreateModel(
            name="ClassGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="class_settings", to="school.group")),
                ("school_class", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="group_settings", to="school.schoolclass")),
            ],
            options={"ordering": ["school_class__level", "group__name"], "unique_together": {("school_class", "group")}},
        ),
        migrations.AddField(
            model_name="classsubject", name="is_enabled",
            field=models.BooleanField(default=True, help_text="Whether this subject is active for this class/group"),
        ),
        migrations.AddField(
            model_name="exam", name="component_distribution",
            field=models.JSONField(blank=True, default=dict, help_text="Optional per-subject component maxima/pass rules"),
        ),
        migrations.AddField(
            model_name="exam", name="grading_scale",
            field=models.JSONField(blank=True, help_text="Optional exam-specific grading scale", null=True),
        ),
        migrations.AddField(
            model_name="exam", name="require_component_pass",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="mark", name="continuous_assessment",
            field=models.DecimalField(decimal_places=1, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="mark", name="viva",
            field=models.DecimalField(decimal_places=1, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="mark", name="assignment",
            field=models.DecimalField(decimal_places=1, default=0, max_digits=5),
        ),
    ]

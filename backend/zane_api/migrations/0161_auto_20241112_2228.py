from datetime import timedelta
from django.db import migrations, models
from django.db.models import F, Func, Value, Q
from django.utils import timezone


class Cast(Func):
    function = "CAST"
    template = "%(expressions)s::%(db_type)s"

    def __init__(self, expression, db_type, **extra):
        super().__init__(expression, db_type=db_type, **extra)


def populate_content_text(apps, schema_editor):
    SimpleLog = apps.get_model("zane_api", "SimpleLog")

    pattern = Value(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    replacement = Value("")
    flags = Value("g")

    SimpleLog.objects.filter(
        ~Q(source="PROXY"),
        content__isnull=False,
        time__gte=timezone.now() - timedelta(days=30),
    ).update(
        content_text=Func(
            Cast(F("content"), db_type="text"),
            pattern,
            replacement,
            flags,
            function="REGEXP_REPLACE",
            output_field=models.TextField(),
        )
    )


def clear_content_text(apps, schema_editor):
    SimpleLog = apps.get_model("zane_api", "SimpleLog")

    # Clear the content_text field (or set to None)
    SimpleLog.objects.update(content_text=None)


class Migration(migrations.Migration):
    dependencies = [
        ("zane_api", "0160_simplelog_content_text"),
    ]

    operations = [
        migrations.RunPython(
            populate_content_text,
            reverse_code=clear_content_text,
        ),
    ]

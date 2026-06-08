from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("libra", "0003_bookcopy_shelf_label"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BarcodeLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("language", models.CharField(max_length=10, verbose_name="Gjuha")),
                ("prefix", models.CharField(max_length=5, verbose_name="Prefiksi")),
                ("from_number", models.IntegerField(verbose_name="Nga Nr.")),
                ("to_number", models.IntegerField(verbose_name="Deri Nr.")),
                ("count", models.IntegerField(verbose_name="Sasia")),
                ("generated_at", models.DateTimeField(auto_now_add=True, verbose_name="Gjeneruar më")),
                (
                    "generated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Gjeneruar nga",
                    ),
                ),
            ],
            options={
                "verbose_name": "Log Barkodesh",
                "verbose_name_plural": "Log-et e Barkodeve",
                "ordering": ["-generated_at"],
            },
        ),
    ]

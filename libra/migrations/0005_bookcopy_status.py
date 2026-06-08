from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("libra", "0004_barcodelog"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookcopy",
            name="status",
            field=models.CharField(
                choices=[("ok", "Mirë"), ("lost", "Humbur")],
                default="ok",
                max_length=10,
                verbose_name="Gjendja",
            ),
        ),
    ]

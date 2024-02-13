# Generated by Django 4.1.2 on 2022-11-22 01:43

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("trade", "0007_alter_articleop_op_alter_commodity_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommCollectRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("op_time", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "commodity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="trade.commodity",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="trade.user"
                    ),
                ),
            ],
        ),
    ]

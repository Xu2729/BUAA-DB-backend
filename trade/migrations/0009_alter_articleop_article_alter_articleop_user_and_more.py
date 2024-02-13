# Generated by Django 4.1.2 on 2022-11-22 01:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("trade", "0008_commcollectrecord"),
    ]

    operations = [
        migrations.AlterField(
            model_name="articleop",
            name="article",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="trade.article"
            ),
        ),
        migrations.AlterField(
            model_name="articleop",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="trade.user"
            ),
        ),
        migrations.AlterField(
            model_name="commcollectrecord",
            name="commodity",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="trade.commodity"
            ),
        ),
        migrations.AlterField(
            model_name="commcollectrecord",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="trade.user"
            ),
        ),
    ]

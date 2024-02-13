# Generated by Django 4.1.2 on 2022-12-18 12:57

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trade", "0009_alter_articleop_article_alter_articleop_user_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="article",
            name="post_time",
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
        migrations.AlterField(
            model_name="articleop",
            name="op_time",
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
        migrations.AlterField(
            model_name="commcollectrecord",
            name="op_time",
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
        migrations.AlterField(
            model_name="comment",
            name="comment_time",
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
        migrations.AlterField(
            model_name="file",
            name="upload_time",
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
        migrations.AlterField(
            model_name="log",
            name="op_time",
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
        migrations.AlterField(
            model_name="order",
            name="start_time",
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
        migrations.AlterField(
            model_name="reply",
            name="reply_time",
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
        migrations.AlterField(
            model_name="shop",
            name="reg_time",
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
        migrations.AlterField(
            model_name="stuauthreq",
            name="req_time",
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
        migrations.AlterField(
            model_name="user",
            name="reg_time",
            field=models.DateTimeField(default=datetime.datetime.now),
        ),
    ]

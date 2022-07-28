# Generated by Django 4.0.6 on 2022-07-28 22:01

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("teamtracking", "0010_alter_note_team_alter_tcrsresponse_team_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="team",
            name="assigned_TA",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assigned_TA",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0019_alter_comment_content_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Massage',
            new_name='Service',
        ),
        migrations.RenameField(
            model_name='messagereservation',
            old_name='massage',
            new_name='service',
        ),
        migrations.AlterField(
            model_name='service',
            name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='services', to='main_app.servicegroup', verbose_name='Група'),
        ),
        migrations.AlterField(
            model_name='service',
            name='image',
            field=models.ImageField(upload_to='services/'),
        ),
    ]

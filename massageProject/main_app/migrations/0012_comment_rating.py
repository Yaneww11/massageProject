from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0011_homepage_footer_tagline_homepage_footer_tagline_bg_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='rating',
            field=models.IntegerField(default=5),
        ),
    ]

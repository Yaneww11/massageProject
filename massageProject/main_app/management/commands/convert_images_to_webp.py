from django.core.management.base import BaseCommand
from django.db.models import Model

from massageProject.main_app.models import BusinessInfo, HomePage, Image, Service, Specialist

MODEL_FIELDS = [
    (Service, 'image'),
    (Specialist, 'image'),
    (BusinessInfo, 'main_image'),
    (Image, 'image'),
    (HomePage, 'logo'),
]


class Command(BaseCommand):
    help = 'Converts existing (non-WebP) uploaded images to WebP, in place.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List images that would be converted without changing anything.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        total = 0

        for model, field_name in MODEL_FIELDS:
            for instance in model.objects.all():
                field_file = getattr(instance, field_name)
                if not field_file or field_file.name.lower().endswith('.webp'):
                    continue

                total += 1
                self.stdout.write(f'{model.__name__}({instance.pk}).{field_name}: {field_file.name}')
                if dry_run:
                    continue

                instance.convert_image_field_to_webp(field_name)
                Model.save(instance, update_fields=[field_name])

        if dry_run:
            self.stdout.write(self.style.WARNING(f'{total} image(s) would be converted (dry run).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Converted {total} image(s) to WebP.'))

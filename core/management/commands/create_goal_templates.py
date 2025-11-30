"""
Management command to create default goal templates
"""
from django.core.management.base import BaseCommand
from core.models import GoalTemplate


class Command(BaseCommand):
    help = 'Create default goal templates for the system'

    def handle(self, *args, **options):
        templates_data = [
            {
                'name': 'Emergency Fund',
                'description': 'Build a safety net for unexpected expenses. Aim for 3-6 months of expenses.',
                'target_amount': 50000.00,
                'category': 'emergency',
                'suggested_deadline_months': 12,
                'icon_name': 'shield',
                'is_featured': True,
            },
            {
                'name': 'House Down Payment',
                'description': 'Save for your dream home. Typically 10-20% of property value.',
                'target_amount': 500000.00,
                'category': 'house',
                'suggested_deadline_months': 36,
                'icon_name': 'home',
                'is_featured': True,
            },
            {
                'name': 'Wedding Savings',
                'description': 'Plan for your special day. Cover venue, catering, and all the details.',
                'target_amount': 300000.00,
                'category': 'wedding',
                'suggested_deadline_months': 24,
                'icon_name': 'heart',
                'is_featured': True,
            },
            {
                'name': 'Motorcycle/Boda',
                'description': 'Get your own transport. Save for a reliable motorcycle.',
                'target_amount': 150000.00,
                'category': 'boda',
                'suggested_deadline_months': 18,
                'icon_name': 'bike',
                'is_featured': False,
            },
            {
                'name': 'Business Startup',
                'description': 'Launch your own business. Save for initial capital and setup costs.',
                'target_amount': 200000.00,
                'category': 'business',
                'suggested_deadline_months': 24,
                'icon_name': 'briefcase',
                'is_featured': False,
            },
            {
                'name': 'Education Fund',
                'description': 'Invest in education. Save for school fees, courses, or training.',
                'target_amount': 100000.00,
                'category': 'education',
                'suggested_deadline_months': 12,
                'icon_name': 'graduation-cap',
                'is_featured': False,
            },
            {
                'name': 'Plot/Land Purchase',
                'description': 'Buy your own piece of land. Secure your future with property ownership.',
                'target_amount': 1000000.00,
                'category': 'plot',
                'suggested_deadline_months': 60,
                'icon_name': 'map-pin',
                'is_featured': False,
            },
            {
                'name': 'Vehicle Purchase',
                'description': 'Get your own car. Save for a reliable vehicle for personal or business use.',
                'target_amount': 800000.00,
                'category': 'vehicle',
                'suggested_deadline_months': 48,
                'icon_name': 'car',
                'is_featured': False,
            },
        ]

        created_count = 0
        for data in templates_data:
            template, created = GoalTemplate.objects.get_or_create(
                name=data['name'],
                defaults=data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created template: {template.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Template already exists: {template.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {created_count} new templates')
        )


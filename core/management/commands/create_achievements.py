"""
Management command to create default achievements
"""
from django.core.management.base import BaseCommand
from core.models import Achievement


class Command(BaseCommand):
    help = 'Create default achievements for the system'

    def handle(self, *args, **options):
        achievements_data = [
            {
                'name': 'First Steps',
                'description': 'Create your first savings goal',
                'icon_name': 'target',
                'criteria_type': 'first_goal',
                'criteria_value': 1,
                'points': 10,
                'rarity': 'common',
            },
            {
                'name': 'Goal Achiever',
                'description': 'Successfully achieve a savings goal',
                'icon_name': 'trophy',
                'criteria_type': 'goal_achieved',
                'criteria_value': 1,
                'points': 50,
                'rarity': 'uncommon',
            },
            {
                'name': 'Week Warrior',
                'description': 'Maintain a 7-day savings streak',
                'icon_name': 'flame',
                'criteria_type': 'streak_7',
                'criteria_value': 7,
                'points': 25,
                'rarity': 'common',
            },
            {
                'name': 'Monthly Master',
                'description': 'Maintain a 30-day savings streak',
                'icon_name': 'flame',
                'criteria_type': 'streak_30',
                'criteria_value': 30,
                'points': 100,
                'rarity': 'rare',
            },
            {
                'name': 'Century Champion',
                'description': 'Maintain a 100-day savings streak',
                'icon_name': 'flame',
                'criteria_type': 'streak_100',
                'criteria_value': 100,
                'points': 500,
                'rarity': 'legendary',
            },
            {
                'name': 'Thousandaire',
                'description': 'Save KSh 1,000 total',
                'icon_name': 'coins',
                'criteria_type': 'total_saved_1000',
                'criteria_value': 1000,
                'points': 30,
                'rarity': 'common',
            },
            {
                'name': 'Ten Thousandaire',
                'description': 'Save KSh 10,000 total',
                'icon_name': 'coins',
                'criteria_type': 'total_saved_10000',
                'criteria_value': 10000,
                'points': 150,
                'rarity': 'uncommon',
            },
            {
                'name': 'Hundred Thousandaire',
                'description': 'Save KSh 100,000 total',
                'icon_name': 'coins',
                'criteria_type': 'total_saved_100000',
                'criteria_value': 100000,
                'points': 1000,
                'rarity': 'epic',
            },
            {
                'name': 'Tribe Member',
                'description': 'Join your first savings tribe',
                'icon_name': 'users',
                'criteria_type': 'join_tribe',
                'criteria_value': 1,
                'points': 15,
                'rarity': 'common',
            },
            {
                'name': 'Tribe Leader',
                'description': 'Create your own savings tribe',
                'icon_name': 'crown',
                'criteria_type': 'create_tribe',
                'criteria_value': 1,
                'points': 40,
                'rarity': 'uncommon',
            },
            {
                'name': 'Statement Analyzer',
                'description': 'Upload your first M-Pesa statement',
                'icon_name': 'file-text',
                'criteria_type': 'upload_statement',
                'criteria_value': 1,
                'points': 20,
                'rarity': 'common',
            },
        ]

        created_count = 0
        for data in achievements_data:
            achievement, created = Achievement.objects.get_or_create(
                criteria_type=data['criteria_type'],
                criteria_value=data['criteria_value'],
                defaults=data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created achievement: {achievement.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Achievement already exists: {achievement.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {created_count} new achievements')
        )


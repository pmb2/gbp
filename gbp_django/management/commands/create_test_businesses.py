from django.core.management.base import BaseCommand
from gbp_django.models import Business
from django.utils import timezone

class Command(BaseCommand):
    help = 'Creates test business records with varying completion levels'

    def handle(self, *args, **kwargs):
        # Delete existing test businesses
        Business.objects.filter(business_id__startswith='test-').delete()
        
        test_businesses = [
            {
                'business_id': 'test-business-0',
                'business_name': 'New Business (0%)',
                'business_email': 'test0@example.com',
                'is_verified': False,
                'address': 'No info',
                'phone_number': 'No info',
                'website_url': 'No info',
                'category': 'No info',
            },
            {
                'business_id': 'test-business-20',
                'business_name': 'Business Name Added (20%)',
                'business_email': 'test20@example.com',
                'is_verified': True,
                'address': 'No info',
                'phone_number': 'No info',
                'website_url': 'No info', 
                'category': 'No info',
            },
            {
                'business_id': 'test-business-40',
                'business_name': 'Address Added (40%)',
                'business_email': 'test40@example.com',
                'is_verified': True,
                'address': '123 Test Street, Test City, TS 12345',
                'phone_number': 'No info',
                'website_url': 'No info',
                'category': 'No info',
            },
            {
                'business_id': 'test-business-60',
                'business_name': 'Phone Added (60%)',
                'business_email': 'test60@example.com',
                'is_verified': True,
                'address': '456 Test Avenue, Test City, TS 12345',
                'phone_number': '(555) 123-4567',
                'website_url': 'No info',
                'category': 'No info',
            },
            {
                'business_id': 'test-business-80',
                'business_name': 'Website Added (80%)',
                'business_email': 'test80@example.com',
                'is_verified': True,
                'address': '789 Test Boulevard, Test City, TS 12345',
                'phone_number': '(555) 234-5678',
                'website_url': 'https://test80.example.com',
                'category': 'No info',
            },
            {
                'business_id': 'test-business-100',
                'business_name': 'Complete Business (100%)',
                'business_email': 'test100@example.com',
                'is_verified': True,
                'address': '321 Test Road, Test City, TS 12345',
                'phone_number': '(555) 345-6789',
                'website_url': 'https://test100.example.com',
                'category': 'Test Business',
                'email_verification_pending': False,
                'email_verified_at': timezone.now(),
            },
        ]

        for business_data in test_businesses:
            Business.objects.create(
                user_id=1,  # Link to user ID 1
                **business_data
            )

        self.stdout.write(self.style.SUCCESS('Successfully created test businesses'))

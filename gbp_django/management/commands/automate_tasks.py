from django.core.management.base import BaseCommand
from gbp_django.models import Business
from gbp_django.utils import upload_photo, generate_post, update_qa, respond_to_reviews

class Command(BaseCommand):
    help = 'Automate tasks like photo uploads, post creation, and review responses.'

    def handle(self, *args, **kwargs):
        businesses = Business.objects.all()
        for business in businesses:
            self.stdout.write(f"Processing business: {business.business_name}")

            # Automate photo uploads
            upload_photo(business)

            # Generate and schedule posts
            generate_post(business)

            # Update Q&A
            update_qa(business)

            # Respond to reviews
            respond_to_reviews(business)

        self.stdout.write(self.style.SUCCESS('Successfully automated tasks for all businesses.'))

from django.core.management.base import BaseCommand
from gbp_django.tasks.tasks import automate_all_business_tasks


class Command(BaseCommand):
    help = 'Trigger automation tasks for all businesses.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting automation tasks for all businesses...")
        
        # Set up environment for automation integration
        base_dir = os.path.dirname(os.path.realpath(__file__))
        cookies_folder = os.path.join(base_dir, "browser_cookies")
        os.makedirs(cookies_folder, exist_ok=True)
        chrome_path = r"/usr/bin/chromium-browser"
        credentials_file = os.path.join(base_dir, "credentials.json")

        # Interactive onboarding for a new business or use pre‑configured ones
        add_new = input("Would you like to add a new business? (y/n): ").strip().lower()
        if add_new == "y":
            new_id, new_url = onboard_new_business(cookies_folder, chrome_path)
            businesses = {new_id: new_url}
        else:
            # Pre‑configured business URLs (replace with real data)
            businesses = {
                "business1": "https://business.google.com/your_business_id1",
                "business2": "https://business.google.com/your_business_id2"
            }
        
        # Define task data for each business
        tasks_data = {
            biz_id: {
                "location_name": "accounts/EXAMPLE/locations/EXAMPLE",
                "new_hours": "Mon-Fri 09:00-17:00",
                "new_website": f"https://new-website-for-{biz_id}.example.com",
                "review_id": "reviewEXAMPLE",
                "review_text": "The service was excellent!",
                "review_response": "Thank you for your kind feedback! We are thrilled to serve you.",
                "post_content": "We're excited to announce a new promotion this week!",
                "photo_path": r"/path/to/photo.jpg"
            }
            for biz_id in businesses
        }
    
        # Instantiate the BusinessProfileManager and run tasks concurrently
        manager = BusinessProfileManager(businesses, cookies_folder, chrome_path, credentials_file, headless=True)
        try:
            asyncio.run(manager.run_all_businesses(tasks_data))
            self.stdout.write(self.style.SUCCESS("Automation tasks completed successfully."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error running automation tasks: {e}"))

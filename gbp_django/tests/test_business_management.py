from django.test import TestCase
from django.contrib.auth import get_user_model
from gbp_django.models import Business
from gbp_django.api.business_management import store_business_data
import json

User = get_user_model()

class BusinessManagementTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            google_id='test123'
        )
        
        # Sample business data from Google API
        self.business_data = {
            'accounts': [{
                'name': 'test-business-1',
                'accountName': 'Test Business',
                'primaryOwner': {'email': 'test@example.com'},
                'organizationInfo': {
                    'address': {'formattedAddress': '123 Test St'},
                    'primaryPhone': '555-0123',
                    'websiteUrl': 'https://test.com',
                    'primaryCategory': {'displayName': 'Test Category'}
                }
            }]
        }

    def test_store_business_data_new_business(self):
        """Test storing data for a new business"""
        stored_businesses = store_business_data(
            self.business_data, 
            self.user.id,
            'fake-access-token'
        )
        
        self.assertEqual(len(stored_businesses), 1)
        business = stored_businesses[0]
        
        self.assertEqual(business.business_name, 'Test Business')
        self.assertEqual(business.business_id, 'test-business-1')
        self.assertEqual(business.user_id, self.user.id)
        self.assertEqual(business.business_email, 'test@example.com')
        
    def test_store_business_data_no_accounts(self):
        """Test storing data when no business accounts exist"""
        empty_data = {'accounts': []}
        
        stored_businesses = store_business_data(
            empty_data,
            self.user.id, 
            'fake-access-token'
        )
        
        self.assertEqual(len(stored_businesses), 1)
        business = stored_businesses[0]
        
        self.assertTrue(business.business_id.startswith('unvalidated-'))
        self.assertEqual(business.business_name, 'My Business')
        self.assertFalse(business.is_verified)
        
    def test_store_business_data_update_existing(self):
        """Test updating an existing business"""
        # Create existing business
        existing = Business.objects.create(
            user=self.user,
            business_id='test-business-1',
            business_name='Old Name',
            business_email='old@example.com'
        )
        
        stored_businesses = store_business_data(
            self.business_data,
            self.user.id,
            'fake-access-token'
        )
        
        self.assertEqual(len(stored_businesses), 1)
        updated = stored_businesses[0]
        
        self.assertEqual(updated.id, existing.id)
        self.assertEqual(updated.business_name, 'Test Business')
        self.assertEqual(updated.business_email, 'test@example.com')
        
    def test_bulk_upload_businesses(self):
        """Test bulk upload of businesses from CSV"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        import csv
        import io
        
        # Create test CSV content
        csv_content = io.StringIO()
        writer = csv.writer(csv_content)
        writer.writerow(['Business Name', 'Email', 'Address', 'Phone', 'Website', 'Category'])
        writer.writerow(['Test Biz 1', 'test1@example.com', '123 Test St', '555-0101', 'test1.com', 'Test Cat 1'])
        writer.writerow(['Test Biz 2', 'test2@example.com', '456 Test Ave', '555-0102', 'test2.com', 'Test Cat 2'])
        
        # Create file object
        csv_file = SimpleUploadedFile(
            'test.csv',
            csv_content.getvalue().encode('utf-8'),
            content_type='text/csv'
        )
        
        # Call bulk upload view
        from django.test import Client
        client = Client()
        client.force_login(self.user)
        response = client.post('/api/business/bulk-upload/', {'file': csv_file})
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['processed'], 2)
        
        # Verify businesses were created
        self.assertEqual(Business.objects.count(), 2)
        biz1 = Business.objects.get(business_name='Test Biz 1')
        self.assertEqual(biz1.business_email, 'test1@example.com')
        biz2 = Business.objects.get(business_name='Test Biz 2')
        self.assertEqual(biz2.business_email, 'test2@example.com')

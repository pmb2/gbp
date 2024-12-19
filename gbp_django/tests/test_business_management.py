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

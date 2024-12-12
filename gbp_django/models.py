from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from pgvector.django import VectorField

class UserManager(BaseUserManager):
    def create_user(self, email, google_id, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, google_id=google_id, **extra_fields)
        # Ensure session state is initialized
        Session.store_session_state(user_id=user.id, state='initialized')
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, google_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(email, google_id, password, **extra_fields)

class User(AbstractBaseUser):
    google_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    email = models.EmailField(max_length=255, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    profile_picture_url = models.TextField(blank=True)
    google_access_token = models.TextField(null=True, blank=True)
    google_refresh_token = models.TextField(null=True, blank=True)
    google_token_expiry = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['google_id']

    def __str__(self):
        return self.email

class Session(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    state = models.CharField(max_length=255)
    priority = models.CharField(max_length=50, default='normal')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @staticmethod
    def store_session_state(user_id, state):
        session_record, created = Session.objects.get_or_create(user_id=user_id)
        session_record.state = state
        session_record.save()

    @staticmethod
    def get_session_state(user_id):
        try:
            return Session.objects.get(user_id=user_id).state
        except Session.DoesNotExist:
            return None

class Business(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=255)
    business_id = models.CharField(max_length=255, unique=True, default='Pending Verification')  # For test data
    business_email = models.EmailField(max_length=255)
    email_verification_token = models.CharField(max_length=100, null=True, blank=True)
    email_verification_pending = models.BooleanField(default=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    address = models.TextField(blank=True, null=True, default='No info')
    phone_number = models.CharField(max_length=20, blank=True, null=True, default='No info')
    website_url = models.TextField(blank=True, null=True, default='No info')
    category = models.CharField(max_length=255, blank=True, null=True, default='No info')
    is_verified = models.BooleanField(default=False)
    email_settings = models.JSONField(default=dict, help_text="Email notification preferences", blank=True)
    
    def get_email_preferences(self):
        """Get email preferences with defaults"""
        defaults = {
            'compliance_alerts': True,
            'content_approval': True,
            'weekly_summary': True,
            'verification_reminders': True,
            'auto_approve_hours': 24
        }
        return {**defaults, **self.email_settings}
    
    def update_email_preferences(self, preferences):
        """Update email preferences"""
        current = self.get_email_preferences()
        current.update(preferences)
        self.email_settings = current
        self.save(update_fields=['email_settings'])
    automation_status = models.CharField(max_length=50, default='Active')
    qa_automation = models.CharField(max_length=20, default='manual')  # manual, approval, auto
    posts_automation = models.CharField(max_length=20, default='manual')
    reviews_automation = models.CharField(max_length=20, default='manual')
    description = models.TextField(blank=True, null=True)
    embedding = VectorField(dimensions=1536, null=True)  # For business profile embedding
    compliance_score = models.IntegerField(default=0)  # Store compliance percentage
    last_post_date = models.DateTimeField(null=True, blank=True)
    next_update_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_profile_completion(self):
        """Calculate profile completion percentage"""
        print(f"\n[DEBUG] Calculating profile completion for business: {self.business_name}")
        print(f"[DEBUG] Verification status: {self.is_verified}")
        print(f"[DEBUG] Business ID: {self.business_id}")
        
        if not self.is_verified:
            print("[DEBUG] Business not verified, returning 0%")
            return 0
            
        completion_score = 0
        required_fields = [
            ('business_name', 20),
            ('address', 20),
            ('phone_number', 20),
            ('website_url', 20),
            ('category', 20)
        ]
        
        for field, score in required_fields:
            value = getattr(self, field)
            print(f"[DEBUG] Checking {field}: {value}")
            if value and value not in ['No info', 'Pending verification', None, '']:
                completion_score += score
                print(f"[DEBUG] Added {score} points for {field}")
                
        final_score = min(completion_score, 100)
        print(f"[DEBUG] Final completion score: {final_score}%")
        return final_score

    def __str__(self):
        return self.business_name

class Post(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    post_id = models.CharField(max_length=255, unique=True, default='default-post-id')
    post_type = models.CharField(max_length=50)
    content = models.TextField(blank=True, null=True)
    media_url = models.TextField(blank=True, null=True)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Review(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    review_id = models.CharField(max_length=255, unique=True)
    reviewer_name = models.CharField(max_length=255, blank=True, null=True)
    reviewer_profile_url = models.TextField(blank=True, null=True)
    rating = models.IntegerField()
    content = models.TextField(blank=True, null=True)
    responded = models.BooleanField(default=False)
    response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class QandA(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    question = models.TextField()
    answer = models.TextField(blank=True, null=True)
    answered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class FAQ(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='faqs')
    question = models.TextField()
    answer = models.TextField()
    embedding = VectorField(dimensions=1536)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business.business_name} - {self.question[:50]}"

class AutomationLog(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=50)
    details = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default='pending')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    error_message = models.TextField(blank=True, null=True)
    retries = models.IntegerField(default=0)
    executed_at = models.DateTimeField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=50)
    status = models.CharField(max_length=50)
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    approval_token = models.CharField(max_length=100, unique=True)

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'status': self.status,
            'content': self.content,
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'created_at': self.created_at.isoformat(),
        }

class EmailLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True)
    type = models.CharField(max_length=50)
    status = models.CharField(max_length=20)
    sent_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(blank=True, null=True)
    clicked_at = models.DateTimeField(blank=True, null=True)

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def get_user_notifications(user_id):
        return Notification.objects.filter(user_id=user_id, read=False)

    def mark_as_read(self):
        self.read = True
        self.save()

    def delete_notification(self):
        self.delete()

class BusinessAttribute(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    value = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

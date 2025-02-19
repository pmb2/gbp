from django.conf import settings
from pgvector.django import VectorField
from django.core.validators import RegexValidator
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from pgvector.django import VectorField
from datetime import time, timedelta, datetime
from dateutil.relativedelta import relativedelta

class UserManager(BaseUserManager):
    def create_user(self, email, google_id=None, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, google_id=google_id, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, google_id=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(email, google_id, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
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
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        """
        Returns True if the user has the specified permission.
        """
        return True

    def has_module_perms(self, app_label):
        """
        Returns True if the user has permissions for the given app.
        """
        return True

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
    id = models.BigAutoField(primary_key=True)
    business_id = models.CharField(max_length=255, unique=True, default='unverified')
    google_account_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    google_location_id = models.CharField(max_length=255, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    website_url = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    profile_photo_url = models.TextField(null=True, blank=True)
    verification_status = models.CharField(
        max_length=50,
        choices=[
            ('UNVERIFIED', 'Unverified'),
            ('PENDING', 'Verification Pending'),
            ('VERIFIED', 'Verified'),
            ('SUSPENDED', 'Suspended'),
        ],
        default='UNVERIFIED'
    )
    verification_method = models.CharField(
        max_length=50,
        choices=[
            ('NONE', 'None'),
            ('EMAIL', 'Email'),
            ('PHONE', 'Phone'),
            ('POSTCARD', 'Postcard'),
            ('OTHER', 'Other'),
        ],
        default='NONE'
    )
    last_verification_attempt = models.DateTimeField(null=True, blank=True)
    business_email = models.EmailField(max_length=255, default='pending@verification.com')
    email_verification_token = models.CharField(max_length=100, null=True, blank=True)
    email_verification_pending = models.BooleanField(default=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    address = models.TextField(default='Pending verification')
    phone_number = models.CharField(max_length=20, default='Pending verification') 
    website_url = models.TextField(default='Pending verification')
    category = models.CharField(max_length=255, default='Pending verification')
    is_verified = models.BooleanField(default=False)
    business_hours = models.JSONField(default=dict, blank=True)
    business_attributes = models.JSONField(default=dict, blank=True)
    services_offered = models.JSONField(default=list, blank=True)
    is_connected = models.BooleanField(default=False)  # Indicates if connected via Google OAuth
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
        print(f"\n[OAUTH FLOW] Calculating profile completion for {self.business_name}:")
        print(f"   - ID: {self.business_id}")
        print(f"   - User: {self.user.id}")
        print(f"   - Google Account: {self.google_account_id or 'Not connected'}")
        print(f"   - Verified: {self.is_verified}")
        print(f"   - Connected: {self.is_connected}")
        
        # For unconnected businesses, return 0%
        if not self.is_connected:
            print("[DEBUG] Business not connected, returning 0%")
            return 0
            
        # For connected but unverified businesses, calculate basic completion
        if not self.is_verified:
            completion_score = 0
            if self.business_name and self.business_name != 'My Business':
                completion_score += 20
            if self.business_email and self.business_email != 'pending@verification.com':
                completion_score += 20
            print(f"[DEBUG] Unverified business completion: {completion_score}%")
            return completion_score
            
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
            if value and value not in ['No info', 'Pending verification', None, '']:
                completion_score += score
                
        final_score = min(completion_score, 100)
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
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    embedding = VectorField(dimensions=1536, null=True)

    def __str__(self):
        return f"{self.question[:50]}..."

class KnowledgeFile(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='knowledge_files')
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    file_size = models.IntegerField()
    content = models.TextField()  # To store extracted text content
    embedding = VectorField(dimensions=1536, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.business.business_name} - {self.file_name}"

class AutomationLog(models.Model):
    @staticmethod
    def default_none():
        return None
    business_id = models.CharField(
        max_length=255,
        help_text="Associated business ID for this log entry",
        validators=[RegexValidator(r'^[a-zA-Z0-9_-]+$', 'Valid business ID required')]
    )
    action_type = models.CharField(
        max_length=50,
        choices=[
            ('FILE_UPLOAD', 'File Upload'),
            ('AUTO_RESPONSE', 'Automated Response'),
            ('SCHEDULED_TASK', 'Scheduled Task'),
            ('SYSTEM_ALERT', 'System Alert')
        ],
        default='FILE_UPLOAD'
    )
    details = models.JSONField(
        blank=True, 
        null=True,
        help_text="Structured data about the automation event"
    )
    status = models.CharField(
        max_length=50,
        choices=[
            ('PENDING', 'Pending'),
            ('RUNNING', 'Running'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed')
        ],
        default='PENDING'
    )
    user_id = models.CharField(
        max_length=255,
        help_text="User who initiated the action",
        validators=[RegexValidator(r'^[a-zA-Z0-9_-]+$', 'Valid user ID required')]
    )
    error_message = models.TextField(blank=True, null=True)
    retries = models.IntegerField(default=0)

    # DateTime fields with proper null handling
    executed_at = models.DateTimeField(
        blank=True,
        null=True,
        default=None,  # Explicit None instead of function reference
        help_text="Timestamp of actual execution"
    )
    deleted_at = models.DateTimeField(
        blank=True,
        null=True,
        default=None,
        help_text="Soft delete timestamp"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        help_text="Record creation timestamp"
    )

    class Meta:
        indexes = [
            models.Index(fields=['business_id', '-created_at']),
            models.Index(fields=['status', 'action_type']),
        ]


def default_scheduled_time():
    return time(9, 0)


class Task(models.Model):
    TASK_TYPES = [
        ('POST', 'Social Post'),
        ('PHOTO', 'Photo Upload'),
        ('REVIEW', 'Review Monitoring'),
        ('QA', 'Q&A Check'),
        ('COMPLIANCE', 'Compliance Check')
    ]
    FREQUENCIES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('CUSTOM', 'Custom')
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('PAUSED', 'Paused')
    ]
    
    business = models.ForeignKey('Business', on_delete=models.CASCADE, default=1)
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, default='POST')
    frequency = models.CharField(max_length=20, choices=FREQUENCIES, default='WEEKLY')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    next_run = models.DateTimeField(default=timezone.now, null=True)

    scheduled_time = models.TimeField(default=default_scheduled_time)
    scheduled_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    parameters = models.JSONField(default=dict)
    last_run = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    content = models.TextField(
        blank=True,
        null=True,
        help_text="Generated content for the task"
    )
    template = models.TextField(
        blank=True,
        help_text="Prompt template used for this task"
    )

    def calculate_next_run(self):
        """Calculate next scheduled run time based on frequency"""
        if not self.business.is_verified:
            raise ValueError("Cannot schedule tasks for unverified businesses")
            
        base_time = self.next_run or timezone.now()
        
        if self.frequency == 'DAILY':
            return base_time + timedelta(days=1)
        elif self.frequency == 'WEEKLY':
            return base_time + timedelta(weeks=1)
        elif self.frequency == 'MONTHLY':
            return base_time + relativedelta(months=1)
        elif self.frequency == 'CUSTOM' and self.scheduled_date and self.scheduled_time:
            return datetime.combine(self.scheduled_date, self.scheduled_time)
        elif self.frequency == 'CUSTOM' and self.next_run:
            return self.next_run
        return base_time  # Fallback to current time if no valid schedule


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

class KnowledgeChunk(models.Model):
    knowledge_file = models.ForeignKey(
        KnowledgeFile,
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    content = models.TextField()
    embedding = VectorField(dimensions=1536)
    position = models.IntegerField()  # To maintain the order of chunks
    created_at = models.DateTimeField(auto_now_add=True)

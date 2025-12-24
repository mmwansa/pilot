import os
import platform
import shutil
import uuid
from datetime import datetime
from functools import reduce
from pathlib import Path

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser, Permission
from django.core.cache import caches
from django.core.files.storage import FileSystemStorage
from django.db import connection, models
from django.db.models import ManyToManyField
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify

# from allauth.account.models import EmailAddress
# from allauth.account.signals import email_confirmed
# from django.dispatch import receiver
from va_explorer.va_data_management.models import Location, VerbalAutopsy
from .constants import FEEDBACK_MODULE_FEATURES


class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifiers
    for authentication instead of username.
    """

    def create_user(self, email, password, **extra_fields):
        """
        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError(_("Email is required"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_password = self.password

    email = models.EmailField(_("email address"), unique=True)
    name = models.CharField(_("Name of User"), blank=True, max_length=255)
    #start new fields for case management
    mobile1 = models.CharField(_("Mobile 1"), blank=True, max_length=255)
    mobile2 = models.CharField(_("Mobile 2"), blank=True, max_length=255)
    address = models.CharField(_("Address"), blank=True, max_length=255)
    #end new fields
    has_valid_password = models.BooleanField(
        _("The user has a user-defined password"), default=False
    )
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    location_restrictions = ManyToManyField(
        Location, related_name="users", db_table="users_user_location_restrictions"
    )

    # The query set of verbal autopsies that this user has access to, based on
    # location restrictions
    # Note: locations are organized in a tree structure, and users have access
    # to all children of any parent location nodes they have access to
    def verbal_autopsies(self, date_cutoff=None, end_date=None):
        # only pull in VAs after certain time period. By default, everything after
        # 1901 (should be everything)
        date_cutoff = date_cutoff if date_cutoff else "1901-01-01"
        end_date = end_date if end_date else datetime.today().strftime("%Y-%m-%d")
        va_objects = VerbalAutopsy.objects.filter(
            Id10023__gte=date_cutoff, Id10023__lte=end_date
        )

        if self.location_restrictions.count() > 0:
            # Get the query set of all locations at or below the parent nodes
            # the user can access by joining the query sets of all the location
            # trees; using the | operator leads to an efficient query
            location_sets = [
                Location.get_tree(location)
                for location in self.location_restrictions.all()
            ]
            locations = reduce((lambda set1, set2: set1 | set2), location_sets)
            # Return the list of all verbal autopsies associated with that
            # query set of locations
            return va_objects.filter(location__in=locations)
        else:
            # No location restrictions, which implies access to all data
            return va_objects

    def is_fieldworker(self):
        return self.groups.filter(name="Field Workers").exists()

    @property
    def can_view_pii(self):
        return self.has_perm("va_analytics.view_pii")

    @can_view_pii.setter
    def can_view_pii(self, value):
        permission = Permission.objects.get(
            content_type__app_label="va_analytics", codename="view_pii"
        )
        if value:
            self.user_permissions.add(permission)
        else:
            self.user_permissions.remove(permission)

    @property
    def can_download_data(self):
        return self.has_perm("va_analytics.download_data")

    @can_download_data.setter
    def can_download_data(self, value):
        permission = Permission.objects.get(
            content_type__app_label="va_analytics", codename="download_data"
        )
        if value:
            self.user_permissions.add(permission)
        else:
            self.user_permissions.remove(permission)

    @property
    def can_supervise_users(self):
        return self.has_perm("va_analytics.supervise_users")

    @can_supervise_users.setter
    def can_supervise_users(self, value):
        permission = Permission.objects.get(
            content_type__app_label="va_analytics", codename="supervise_users"
        )
        if value:
            self.user_permissions.add(permission)
        else:
            self.user_permissions.remove(permission)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return f'{self.name} - {self.email}'

    def get_absolute_url(self):
        """Get url for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.pk})

    # TODO: Remove if we do not require email confirmation; we will no longer
    # need the lines below
    # def add_email_address(self, request, new_email):
    #     return EmailAddress.objects.add_email(
    #         request, self.user, new_email, confirm=True
    #     )
    #
    # @receiver(email_confirmed)
    # def update_user_email(sender, email_address, **kwargs):
    #     email_address.set_as_primary()
    #
    #     EmailAddress.objects.filter(
    #         user=email_address.user).exclude(primary=True).delete()

    def save(self, *args, **kwargs):
        # TODO: May need to be changed depending on how username comes in from ODK?
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)
        if self.original_password != self.password:
            UserPasswordHistory.remember_password(self)

    @property
    def unread_messages(self):
        return self.messages.unread()

    @property
    def mailbox_unread_count(self):
        return self.unread_messages.count()


class UserPasswordHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    old_password = models.CharField(max_length=128)
    auto_now_add = True

    @classmethod
    def remember_password(cls, user):
        cls(user=user, old_password=user.password).save()


class UserMessageQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(read_at__isnull=True)


class UserMessageManager(models.Manager.from_queryset(UserMessageQuerySet)):
    pass


class UnreadUserMessageManager(UserMessageManager):
    def get_queryset(self):
        return super().get_queryset().unread()


class UserMessage(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="messages", related_query_name="message"
    )
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    objects = UserMessageManager()
    unread = UnreadUserMessageManager()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        subject = self.subject or _("Message")
        return f"{subject} ({self.user})"

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])

    def get_absolute_url(self):
        return reverse("users:message_detail", kwargs={"pk": self.pk})


class Feedback(models.Model):
    class Module(models.TextChoices):
        DATA_MANAGEMENT = "data_management", "Data Management"
        PERSONNEL_MANAGEMENT = "personnel_management", "Personnel Management"
        SCHEDULE_MANAGEMENT = "schedule_management", "Schedule Management"
        ANALYTICS = "analytics", "Dashboards (Analytics)"

    class Severity(models.TextChoices):
        CRITICAL = "critical", "Critical"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"
        ENHANCEMENT = "enhancement", "Enhancement"

    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"

    subject = models.CharField(max_length=255)
    module = models.CharField(max_length=64, choices=Module.choices)
    feature = models.CharField(max_length=64)
    severity = models.CharField(
        max_length=16, choices=Severity.choices, default=Severity.MEDIUM
    )
    description = models.TextField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.NEW
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="feedback_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.subject} ({self.get_module_display()})"

    @staticmethod
    def module_feature_map():
        return FEEDBACK_MODULE_FEATURES

    @classmethod
    def feature_choices_for(cls, module):
        return cls.module_feature_map().get(module, [])

    def get_feature_display(self):
        return dict(self.feature_choices_for(self.module)).get(self.feature, self.feature)

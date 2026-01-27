"""
User Django ORM model.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom user manager."""

    def create_user(self, email, nickname, password=None, name=None, phone=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, nickname=nickname, name=name, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nickname, password=None, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, nickname, password, **extra_fields)


class UserModel(AbstractBaseUser):
    """Custom user model based on ERD."""

    email = models.EmailField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name='이메일'
    )
    password = models.CharField(
        max_length=255,
        verbose_name='비밀번호'
    )
    name = models.CharField(
        max_length=50,
        verbose_name='이름'
    )
    nickname = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='닉네임'
    )
    phone = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name='전화번호'
    )
    token_balance = models.IntegerField(
        null=True,
        blank=True,
        default=0,
        verbose_name='보유토큰'
    )
    social_provider = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name='소셜제공자'
    )
    social_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='소셜ID'
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='생성시각'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='수정시각'
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='논리적삭제플래그'
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nickname', 'name', 'phone']


    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    @property
    def is_deleted(self) -> bool:
        """Check if user is soft deleted."""
        return self.deleted_at is not None

    def has_perm(self, perm, obj=None):
        """Check if user has a specific permission."""
        return self.is_superuser

    def has_module_perms(self, app_label):
        """Check if user has permissions to view the app."""
        return self.is_superuser

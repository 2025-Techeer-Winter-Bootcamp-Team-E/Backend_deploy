"""
Users module Celery tasks.
"""
from celery import shared_task


@shared_task(name='modules.users.tasks.send_welcome_email')
def send_welcome_email(user_id: str, email: str):
    """Send welcome email to new user."""
    # TODO: Implement email sending
    print(f"Sending welcome email to {email} for user {user_id}")
    return True


@shared_task(name='modules.users.tasks.send_verification_email')
def send_verification_email(user_id: str, email: str, token: str):
    """Send verification email to user."""
    # TODO: Implement email verification
    print(f"Sending verification email to {email}")
    return True


@shared_task(name='modules.users.tasks.send_password_reset_email')
def send_password_reset_email(user_id: str, email: str, token: str):
    """Send password reset email to user."""
    # TODO: Implement password reset email
    print(f"Sending password reset email to {email}")
    return True

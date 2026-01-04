from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model with role-based access control.
    Supports both students and instructors.
    """
    
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        INSTRUCTOR = 'INSTRUCTOR', 'Instructor'
        ADMIN = 'ADMIN', 'Admin'
    
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True  # Index for faster role-based queries
    )
    
    student_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="Unique student identification number"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['student_id']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.Role(self.role).label})"
    
    @property
    def is_student(self):
        """Check if user is a student."""
        return self.role == self.Role.STUDENT
    
    @property
    def is_instructor(self):
        """Check if user is an instructor."""
        return self.role == self.Role.INSTRUCTOR

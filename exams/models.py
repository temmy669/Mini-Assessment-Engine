from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.utils import timezone
import json


class Course(models.Model):
    """
    Course model to organize exams.
    """
    code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courses',
        limit_choices_to={'role': 'INSTRUCTOR'}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'courses'
        ordering = ['code']
        indexes = [
            models.Index(fields=['code', 'instructor']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Exam(models.Model):
    """
    Exam model representing an assessment.
    Contains metadata, duration, and scheduling information.
    """
    
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PUBLISHED = 'PUBLISHED', 'Published'
        ARCHIVED = 'ARCHIVED', 'Archived'
    
    title = models.CharField(max_length=200, db_index=True)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='exams'
    )
    description = models.TextField(blank=True)
    
    # Duration in minutes
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Duration of exam in minutes"
    )
    
    # Scheduling
    start_time = models.DateTimeField(
        help_text="When the exam becomes available",
        db_index=True
    )
    end_time = models.DateTimeField(
        help_text="When the exam closes",
        db_index=True
    )
    
    # Configuration
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )
    passing_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=60.00,
        help_text="Minimum score to pass (percentage)"
    )
    max_attempts = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of submission attempts allowed"
    )
    
    # Metadata (stored as JSON for flexibility)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata like instructions, resources, etc."
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_exams'
    )
    
    class Meta:
        db_table = 'exams'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['status', 'start_time', 'end_time']),
            models.Index(fields=['course', 'status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.course.code}"
    
    @property
    def is_active(self):
        """Check if exam is currently active."""
        now = timezone.now()
        return (
            self.status == self.Status.PUBLISHED
            and self.start_time <= now <= self.end_time
        )
    
    @property
    def total_marks(self):
        """Calculate total marks for the exam."""
        return self.questions.aggregate(
            total=models.Sum('marks')
        )['total'] or 0


class Question(models.Model):
    """
    Question model supporting multiple question types.
    """
    
    class QuestionType(models.TextChoices):
        MULTIPLE_CHOICE = 'MCQ', 'Multiple Choice'
        SHORT_ANSWER = 'SHORT', 'Short Answer'
        ESSAY = 'ESSAY', 'Essay'
        TRUE_FALSE = 'TF', 'True/False'
    
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    question_type = models.CharField(
        max_length=10,
        choices=QuestionType.choices,
        db_index=True
    )
    
    # Question content
    question_text = models.TextField(help_text="The question text")
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order in the exam"
    )
    marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=1.00,
        help_text="Marks allocated to this question"
    )
    
    # Answer storage (flexible JSON structure)
    expected_answer = models.JSONField(
        help_text="Expected answer(s) - structure depends on question type"
    )
    
    # Options for MCQ (stored as JSON array)
    options = models.JSONField(
        null=True,
        blank=True,
        help_text="Options for multiple choice questions"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata like hints, explanation, etc."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'questions'
        ordering = ['exam', 'order']
        indexes = [
            models.Index(fields=['exam', 'order']),
            models.Index(fields=['question_type']),
        ]
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}"


class Submission(models.Model):
    """
    Submission model tracking student exam attempts.
    Optimized for efficient result retrieval.
    """
    
    class Status(models.TextChoices):
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        GRADING = 'GRADING', 'Grading'
        GRADED = 'GRADED', 'Graded'
    
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions',
        limit_choices_to={'role': 'STUDENT'}
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    
    # Submission tracking
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
        db_index=True
    )
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    
    # Grading results
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Final score as percentage"
    )
    marks_obtained = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total marks obtained"
    )
    total_marks = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total marks for the exam"
    )
    
    # Feedback
    feedback = models.JSONField(
        default=dict,
        blank=True,
        help_text="Grading feedback and comments"
    )
    
    class Meta:
        db_table = 'submissions'
        ordering = ['-submitted_at']
        indexes = [
            # Optimized for student result retrieval
            models.Index(fields=['student', '-submitted_at']),
            models.Index(fields=['exam', 'student', 'attempt_number']),
            models.Index(fields=['status', 'submitted_at']),
            # Composite index for common queries
            models.Index(fields=['student', 'exam', '-attempt_number']),
        ]
        unique_together = [['exam', 'student', 'attempt_number']]
    
    def __str__(self):
        return f"{self.student.username} - {self.exam.title} (Attempt {self.attempt_number})"
    
    @property
    def is_passed(self):
        """Check if submission passed based on exam passing score."""
        if self.score is None:
            return None
        return self.score >= self.exam.passing_score
    
    @property
    def time_taken(self):
        """Calculate time taken for submission."""
        if self.submitted_at:
            delta = self.submitted_at - self.started_at
            return int(delta.total_seconds() / 60)  # in minutes
        return None


class Answer(models.Model):
    """
    Individual answers for each question in a submission.
    Normalized structure for efficient querying.
    """
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    
    # Student's answer (flexible JSON structure)
    answer_text = models.JSONField(
        help_text="Student's answer - structure depends on question type"
    )
    
    # Grading results
    marks_awarded = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    is_correct = models.BooleanField(null=True, blank=True)
    
    # Feedback
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'answers'
        ordering = ['submission', 'question__order']
        indexes = [
            models.Index(fields=['submission', 'question']),
            models.Index(fields=['question', 'is_correct']),
        ]
        unique_together = [['submission', 'question']]
    
    def __str__(self):
        return f"Answer to {self.question} by {self.submission.student.username}"
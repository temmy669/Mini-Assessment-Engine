from django.contrib import admin
from django.utils.html import format_html
from .models import Course, Exam, Question, Submission, Answer


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'instructor', 'created_at']
    list_filter = ['instructor', 'created_at']
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['created_at', 'updated_at']


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ['order', 'question_type', 'question_text', 'marks']


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'course', 'status', 'start_time',
        'end_time', 'duration_minutes', 'is_active_badge'
    ]
    list_filter = ['status', 'course', 'start_time', 'created_by']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at', 'total_marks', 'is_active']
    inlines = [QuestionInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'course', 'description', 'status')
        }),
        ('Scheduling', {
            'fields': ('start_time', 'end_time', 'duration_minutes')
        }),
        ('Configuration', {
            'fields': ('passing_score', 'max_attempts', 'metadata')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'total_marks', 'is_active'),
            'classes': ('collapse',)
        }),
    )
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green;">● Active</span>'
            )
        return format_html(
            '<span style="color: gray;">○ Inactive</span>'
        )
    is_active_badge.short_description = 'Status'


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['exam', 'order', 'question_type', 'marks', 'question_preview']
    list_filter = ['exam', 'question_type']
    search_fields = ['question_text']
    ordering = ['exam', 'order']
    
    def question_preview(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_preview.short_description = 'Question'


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ['question', 'answer_text', 'marks_awarded', 'is_correct', 'feedback']
    can_delete = False


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'student', 'exam', 'attempt_number', 'status',
        'score_badge', 'submitted_at', 'graded_at'
    ]
    list_filter = ['status', 'exam', 'submitted_at']
    search_fields = ['student__username', 'student__email', 'exam__title']
    readonly_fields = [
        'started_at', 'submitted_at', 'graded_at',
        'score', 'marks_obtained', 'total_marks', 'is_passed'
    ]
    inlines = [AnswerInline]
    
    fieldsets = (
        ('Submission Info', {
            'fields': ('student', 'exam', 'attempt_number', 'status')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'submitted_at', 'graded_at')
        }),
        ('Grading Results', {
            'fields': ('score', 'marks_obtained', 'total_marks', 'is_passed', 'feedback')
        }),
    )
    
    def score_badge(self, obj):
        if obj.score is None:
            return format_html('<span style="color: gray;">Not Graded</span>')
        
        color = 'green' if obj.is_passed else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}%</span>',
            color, obj.score
        )
    score_badge.short_description = 'Score'


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = [
        'submission', 'question', 'marks_awarded',
        'is_correct_badge', 'graded_at'
    ]
    list_filter = ['is_correct', 'graded_at', 'submission__exam']
    search_fields = ['submission__student__username', 'question__question_text']
    readonly_fields = ['created_at', 'updated_at']
    
    def is_correct_badge(self, obj):
        if obj.is_correct is None:
            return format_html('<span style="color: gray;">Not Graded</span>')
        
        if obj.is_correct:
            return format_html('<span style="color: green;">✓ Correct</span>')
        return format_html('<span style="color: red;">✗ Incorrect</span>')
    is_correct_badge.short_description = 'Result'
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from .models import Course, Exam, Question, Submission, Answer
from accounts.models import User


class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course model."""
    
    instructor_name = serializers.CharField(source='instructor.get_full_name', read_only=True)
    exam_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'code', 'name', 'description', 
            'instructor', 'instructor_name', 'exam_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_exam_count(self, obj):
        return obj.exams.filter(status=Exam.Status.PUBLISHED).count()


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer for Question model."""
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'question_text', 'order',
            'marks', 'options', 'metadata'
        ]
    
    def to_representation(self, instance):
        """Hide expected_answer from students."""
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        # Only show expected_answer to instructors
        if request and hasattr(request, 'user'):
            if request.user.is_instructor or request.user.is_staff:
                data['expected_answer'] = instance.expected_answer
        
        return data


class QuestionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer including expected answers (for instructors)."""
    
    class Meta:
        model = Question
        fields = '__all__'


class ExamListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for exam listings."""
    
    course_name = serializers.CharField(source='course.name', read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)
    question_count = serializers.SerializerMethodField()
    is_active = serializers.ReadOnlyField()
    
    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'course', 'course_name', 'course_code',
            'duration_minutes', 'start_time', 'end_time',
            'status', 'is_active', 'question_count', 'total_marks',
            'passing_score', 'max_attempts'
        ]
    
    def get_question_count(self, obj):
        return obj.questions.count()


class ExamDetailSerializer(serializers.ModelSerializer):
    """Detailed exam serializer with questions."""
    
    questions = QuestionSerializer(many=True, read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)
    total_marks = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    
    class Meta:
        model = Exam
        fields = [
            'id', 'title', 'course', 'course_name', 'description',
            'duration_minutes', 'start_time', 'end_time',
            'status', 'is_active', 'passing_score', 'max_attempts',
            'total_marks', 'questions', 'metadata', 'created_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class AnswerSerializer(serializers.ModelSerializer):
    """Serializer for individual answers."""
    
    question_text = serializers.CharField(source='question.question_text', read_only=True)
    question_marks = serializers.DecimalField(
        source='question.marks',
        max_digits=5,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = Answer
        fields = [
            'id', 'question', 'question_text', 'question_marks',
            'answer_text', 'marks_awarded', 'is_correct',
            'feedback', 'graded_at'
        ]
        read_only_fields = ['marks_awarded', 'is_correct', 'feedback', 'graded_at']


class SubmissionCreateSerializer(serializers.Serializer):
    """
    Serializer for creating/submitting exam answers.
    Validates that all questions are answered and exam is active.
    """
    
    answers = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        help_text="List of answers with question_id and answer_text"
    )
    
    def validate_answers(self, value):
        """Validate answer structure."""
        for answer in value:
            if 'question_id' not in answer:
                raise serializers.ValidationError(
                    "Each answer must have a 'question_id'"
                )
            if 'answer_text' not in answer:
                raise serializers.ValidationError(
                    "Each answer must have 'answer_text'"
                )
        return value
    
    def validate(self, data):
        """Validate exam status and attempt limits."""
        exam = self.context['exam']
        student = self.context['request'].user
        
        # Check if exam is active
        if not exam.is_active:
            raise serializers.ValidationError(
                "This exam is not currently active."
            )
        
        # Check attempt limit
        attempt_count = Submission.objects.filter(
            exam=exam,
            student=student,
            status=Submission.Status.GRADED
        ).count()
        
        if attempt_count >= exam.max_attempts:
            raise serializers.ValidationError(
                f"Maximum attempts ({exam.max_attempts}) exceeded."
            )
        
        # Validate all questions are answered
        question_ids = set(exam.questions.values_list('id', flat=True))
        answer_ids = set(a['question_id'] for a in data['answers'])
        
        if question_ids != answer_ids:
            missing = question_ids - answer_ids
            extra = answer_ids - question_ids
            
            errors = []
            if missing:
                errors.append(f"Missing answers for questions: {missing}")
            if extra:
                errors.append(f"Invalid question IDs: {extra}")
            
            raise serializers.ValidationError(" ".join(errors))
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create submission and answers atomically."""
        exam = self.context['exam']
        student = self.context['request'].user
        
        # Get next attempt number
        last_attempt = Submission.objects.filter(
            exam=exam,
            student=student
        ).order_by('-attempt_number').first()
        
        attempt_number = (last_attempt.attempt_number + 1) if last_attempt else 1
        
        # Create submission
        submission = Submission.objects.create(
            exam=exam,
            student=student,
            attempt_number=attempt_number,
            status=Submission.Status.SUBMITTED,
            submitted_at=timezone.now(),
            total_marks=exam.total_marks
        )
        
        # Create answers
        answers_to_create = []
        for answer_data in validated_data['answers']:
            question = Question.objects.get(id=answer_data['question_id'])
            answers_to_create.append(
                Answer(
                    submission=submission,
                    question=question,
                    answer_text=answer_data['answer_text']
                )
            )
        
        Answer.objects.bulk_create(answers_to_create)
        
        return submission


class SubmissionSerializer(serializers.ModelSerializer):
    """Serializer for submission listings."""
    
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    is_passed = serializers.ReadOnlyField()
    time_taken = serializers.ReadOnlyField()
    
    class Meta:
        model = Submission
        fields = [
            'id', 'exam', 'exam_title', 'student', 'student_name',
            'attempt_number', 'status', 'started_at', 'submitted_at',
            'graded_at', 'score', 'marks_obtained', 'total_marks',
            'is_passed', 'time_taken'
        ]
        read_only_fields = [
            'started_at', 'submitted_at', 'graded_at',
            'score', 'marks_obtained', 'status'
        ]


class SubmissionDetailSerializer(serializers.ModelSerializer):
    """Detailed submission with answers and feedback."""
    
    answers = AnswerSerializer(many=True, read_only=True)
    exam_title = serializers.CharField(source='exam.title', read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    is_passed = serializers.ReadOnlyField()
    time_taken = serializers.ReadOnlyField()
    
    class Meta:
        model = Submission
        fields = [
            'id', 'exam', 'exam_title', 'student', 'student_name',
            'attempt_number', 'status', 'started_at', 'submitted_at',
            'graded_at', 'score', 'marks_obtained', 'total_marks',
            'is_passed', 'time_taken', 'feedback', 'answers'
        ]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'student_id', 'created_at'
        ]
        read_only_fields = ['created_at']
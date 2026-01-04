from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Q, Count, Avg
from django.utils import timezone

from .models import Course, Exam, Question, Submission, Answer
from .serializers import (
    CourseSerializer, ExamListSerializer, ExamDetailSerializer,
    QuestionSerializer, SubmissionSerializer, SubmissionDetailSerializer,
    SubmissionCreateSerializer
)
from .permissions import (
    IsStudent, IsInstructor, IsInstructorOrReadOnly,
    IsOwnerOrInstructor, CanSubmitExam, CanViewExam
)
from .grading import grading_service

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
)


@extend_schema_view(
    list=extend_schema(tags=["Courses"]),
    retrieve=extend_schema(tags=["Courses"]),
)
class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing courses.
    Students can view all published courses.
    """
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['code', 'instructor']
    search_fields = ['code', 'name', 'description']
    ordering_fields = ['code', 'name', 'created_at']
    
    def get_queryset(self):
        """Optimize query with select_related."""
        return Course.objects.select_related('instructor').all()


@extend_schema_view(
    list=extend_schema(tags=["Exams"]),
    retrieve=extend_schema(tags=["Exams"]),
    my_submissions=extend_schema(tags=["Exams", "Submissions"]),
    statistics=extend_schema(tags=["Exams", "Analytics"]),
)
class ExamViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing exams.
    Students can only view published exams.
    Instructors can view all exams.
    """
    permission_classes = [IsAuthenticated, CanViewExam]
    filterset_fields = ['course', 'status']
    search_fields = ['title', 'description']
    ordering_fields = ['start_time', 'end_time', 'created_at']
    
    def get_serializer_class(self):
        """Use different serializers for list and detail views."""
        if self.action == 'list':
            return ExamListSerializer
        return ExamDetailSerializer
    
    def get_queryset(self):
        """
        Optimize queries and filter based on user role.
        Students see only published exams.
        """
        queryset = Exam.objects.select_related('course', 'created_by')
        
        # Prefetch questions for detail view
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                Prefetch(
                    'questions',
                    queryset=Question.objects.order_by('order')
                )
            )
        
        # Filter by role
        if self.request.user.is_student:
            queryset = queryset.filter(
                status=Exam.Status.PUBLISHED,
                start_time__lte=timezone.now()
            )
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def my_submissions(self, request, pk=None):
        """
        Get all submissions for current student for this exam.
        Optimized with select_related and prefetch_related.
        """
        exam = self.get_object()
        
        submissions = Submission.objects.filter(
            exam=exam,
            student=request.user
        ).select_related('exam', 'student').prefetch_related(
            Prefetch(
                'answers',
                queryset=Answer.objects.select_related('question').order_by('question__order')
            )
        ).order_by('-attempt_number')
        
        serializer = SubmissionDetailSerializer(submissions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    @extend_schema(
        tags=["Analytics"],
        summary="Exam statistics",
        description="Instructor-only exam performance statistics."
    )
    def statistics(self, request, pk=None):
        """Get statistics for an exam (instructors only)."""
        if not request.user.is_instructor:
            return Response(
                {'error': 'Only instructors can view statistics'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        exam = self.get_object()
        
        submissions = Submission.objects.filter(
            exam=exam,
            status=Submission.Status.GRADED
        )
        
        stats = submissions.aggregate(
            total_submissions=Count('id'),
            average_score=Avg('score'),
            pass_rate=Avg(
                models.Case(
                    models.When(score__gte=exam.passing_score, then=1),
                    default=0,
                    output_field=models.FloatField()
                )
            ) * 100
        )
        
        return Response({
            'exam_id': exam.id,
            'exam_title': exam.title,
            'total_submissions': stats['total_submissions'] or 0,
            'average_score': round(stats['average_score'] or 0, 2),
            'pass_rate': round(stats['pass_rate'] or 0, 2),
            'total_students': submissions.values('student').distinct().count()
        })

@extend_schema_view(
    list=extend_schema(tags=["Exams"]),
    retrieve=extend_schema(tags=["Exams"]),
    my_submissions=extend_schema(tags=["Exams", "Submissions"]),
    statistics=extend_schema(tags=["Exams", "Analytics"]),
)
class SubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing submissions.
    Students can only view their own submissions.
    Instructors can view all submissions.
    
    Optimized for efficient result retrieval using:
    - select_related for foreign keys
    - prefetch_related for reverse relations
    - Database indexes on commonly queried fields
    """
    permission_classes = [IsAuthenticated, IsOwnerOrInstructor]
    filterset_fields = ['exam', 'status', 'attempt_number']
    ordering_fields = ['submitted_at', 'score', 'attempt_number']
    
    def get_serializer_class(self):
        """Use different serializers for list and detail views."""
        if self.action == 'list':
            return SubmissionSerializer
        return SubmissionDetailSerializer
    
    def get_queryset(self):
        """
        Optimized queryset with proper joins and prefetching.
        Critical for performance when retrieving student results.
        """
        # Base queryset with essential relations
        queryset = Submission.objects.select_related(
            'exam',
            'exam__course',
            'student'
        )
        
        # For detail views, prefetch all answers with questions
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related(
                Prefetch(
                    'answers',
                    queryset=Answer.objects.select_related('question').order_by('question__order')
                )
            )
        
        # Filter based on user role
        if self.request.user.is_student:
            # Students only see their own submissions
            # Uses indexed field for fast lookup
            queryset = queryset.filter(student=self.request.user)
        
        return queryset.order_by('-submitted_at')
    
    @action(detail=False, methods=['get'])
    def my_results(self, request):
        """
        Optimized endpoint for students to retrieve their results.
        Uses database indexes and minimal queries for fast retrieval.
        """
        # Get all graded submissions for the student
        # This query is optimized with indexes on (student, submitted_at)
        submissions = self.get_queryset().filter(
            status=Submission.Status.GRADED
        ).select_related(
            'exam',
            'exam__course'
        )
        
        # Add filtering options
        course_id = request.query_params.get('course')
        if course_id:
            submissions = submissions.filter(exam__course_id=course_id)
        
        serializer = self.get_serializer(submissions, many=True)
        return Response(serializer.data)

@extend_schema(
    tags=["Exam Submissions"],
    summary="Submit an exam",
    description="Submit answers for an active exam and receive automated grading."
)
class ExamSubmissionView(generics.CreateAPIView):
    """
    Secure endpoint for submitting exam answers.
    
    Security features:
    - Token authentication required
    - Students can only submit their own answers
    - Validates exam is active
    - Enforces attempt limits
    - Atomic transaction for data integrity
    """
    serializer_class = SubmissionCreateSerializer
    permission_classes = [IsAuthenticated, IsStudent, CanSubmitExam]
    
    def get_exam(self):
        """Get exam from URL parameter."""
        exam_id = self.kwargs.get('exam_id')
        return get_object_or_404(
            Exam.objects.prefetch_related('questions'),
            id=exam_id
        )
    
    def create(self, request, *args, **kwargs):
        """
        Create submission and trigger automated grading.
        Returns submission details with grading results.
        """
        exam = self.get_exam()
        
        # Prepare serializer with context
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'exam': exam}
        )
        serializer.is_valid(raise_exception=True)
        
        # Create submission (atomic transaction in serializer)
        submission = serializer.save()
        
        try:
            # Trigger automated grading
            grading_result = grading_service.grade_submission(submission)
            
            # Return detailed response with grading results
            submission.refresh_from_db()
            response_serializer = SubmissionDetailSerializer(submission)
            
            return Response(
                {
                    'message': 'Submission graded successfully',
                    'submission': response_serializer.data,
                    'grading_summary': {
                        'score': grading_result['score'],
                        'marks_obtained': grading_result['marks_obtained'],
                        'total_marks': grading_result['total_marks'],
                        'is_passed': grading_result['is_passed'],
                        'feedback': grading_result['feedback']
                    }
                },
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            # If grading fails, submission still exists but in SUBMITTED state
            return Response(
                {
                    'message': 'Submission received but grading failed',
                    'submission_id': submission.id,
                    'error': str(e)
                },
                status=status.HTTP_202_ACCEPTED
            )

@extend_schema(
    tags=["Student Dashboard"],
    summary="Student dashboard overview",
    description="Returns statistics, recent submissions, and upcoming exams."
)
class StudentDashboardView(generics.GenericAPIView):
    """
    Dashboard endpoint providing overview of student's academic progress.
    Optimized with aggregated queries.
    """
    permission_classes = [IsAuthenticated, IsStudent]
    
    def get(self, request):
        """Get dashboard data for current student."""
        student = request.user
        
        # Get submission statistics
        submissions = Submission.objects.filter(
            student=student,
            status=Submission.Status.GRADED
        ).select_related('exam', 'exam__course')
        
        total_exams = submissions.values('exam').distinct().count()
        
        stats = submissions.aggregate(
            total_submissions=Count('id'),
            average_score=Avg('score'),
            passed_count=Count(
                'id',
                filter=Q(score__gte=models.F('exam__passing_score'))
            )
        )
        
        # Get recent submissions
        recent_submissions = submissions.order_by('-submitted_at')[:5]
        
        # Get upcoming exams
        upcoming_exams = Exam.objects.filter(
            status=Exam.Status.PUBLISHED,
            start_time__lte=timezone.now(),
            end_time__gte=timezone.now()
        ).exclude(
            submissions__student=student,
            submissions__status=Submission.Status.GRADED
        ).select_related('course').order_by('end_time')[:5]
        
        return Response({
            'statistics': {
                'total_exams_taken': total_exams,
                'total_submissions': stats['total_submissions'] or 0,
                'average_score': round(stats['average_score'] or 0, 2),
                'exams_passed': stats['passed_count'] or 0,
                'pass_rate': round(
                    (stats['passed_count'] / total_exams * 100) if total_exams > 0 else 0,
                    2
                )
            },
            'recent_submissions': SubmissionSerializer(recent_submissions, many=True).data,
            'upcoming_exams': ExamListSerializer(upcoming_exams, many=True).data
        })


# Import models for aggregation
from django.db import models
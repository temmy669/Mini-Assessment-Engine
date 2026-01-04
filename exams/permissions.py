from rest_framework import permissions


class IsStudent(permissions.BasePermission):
    """Permission to check if user is a student."""
    
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_student
        )


class IsInstructor(permissions.BasePermission):
    """Permission to check if user is an instructor."""
    
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_instructor
        )


class IsInstructorOrReadOnly(permissions.BasePermission):
    """Allow instructors full access, others read-only."""
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_instructor


class IsOwnerOrInstructor(permissions.BasePermission):
    """
    Permission to ensure students can only access their own submissions.
    Instructors can access all submissions.
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Instructors can access all submissions
        if request.user.is_instructor or request.user.is_staff:
            return True
        
        # Students can only access their own submissions
        if hasattr(obj, 'student'):
            return obj.student == request.user
        
        return False


class CanSubmitExam(permissions.BasePermission):
    """
    Permission to check if a student can submit an exam.
    Validates exam is active and attempt limits not exceeded.
    """
    
    message = "You do not have permission to submit this exam."
    
    def has_permission(self, request, view):
        # Must be authenticated student
        if not (request.user and request.user.is_authenticated and request.user.is_student):
            return False
        
        # For POST requests, check exam-specific permissions
        if request.method == 'POST':
            exam = view.get_exam()
            
            # Check if exam is active
            if not exam.is_active:
                self.message = "This exam is not currently active."
                return False
            
            # Check attempt limit
            from .models import Submission
            attempt_count = Submission.objects.filter(
                exam=exam,
                student=request.user,
                status=Submission.Status.GRADED
            ).count()
            
            if attempt_count >= exam.max_attempts:
                self.message = f"Maximum attempts ({exam.max_attempts}) exceeded."
                return False
        
        return True


class CanViewExam(permissions.BasePermission):
    """
    Permission to check if user can view exam details.
    Students can only view published, active exams.
    Instructors can view all exams.
    """
    
    def has_object_permission(self, request, view, obj):
        # Instructors can view all exams
        if request.user.is_instructor or request.user.is_staff:
            return True
        
        # Students can only view published exams
        from .models import Exam
        if request.user.is_student:
            return obj.status == Exam.Status.PUBLISHED
        
        return False
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta

from accounts.models import User
from exams.models import Course, Exam, Question, Submission, Answer
from exams.grading import grading_service


class UserModelTest(TestCase):
    """Test custom User model."""
    
    def setUp(self):
        self.student = User.objects.create_user(
            username='teststudent',
            email='student@test.com',
            password='testpass123',
            role=User.Role.STUDENT,
            student_id='TEST001'
        )
        
        self.instructor = User.objects.create_user(
            username='testinstructor',
            email='instructor@test.com',
            password='testpass123',
            role=User.Role.INSTRUCTOR
        )
    
    def test_user_creation(self):
        """Test user creation with roles."""
        self.assertEqual(self.student.role, User.Role.STUDENT)
        self.assertTrue(self.student.is_student)
        self.assertFalse(self.student.is_instructor)
        
        self.assertEqual(self.instructor.role, User.Role.INSTRUCTOR)
        self.assertTrue(self.instructor.is_instructor)
        self.assertFalse(self.instructor.is_student)
    
    def test_student_id_unique(self):
        """Test student_id uniqueness."""
        with self.assertRaises(Exception):
            User.objects.create_user(
                username='another',
                email='another@test.com',
                password='pass',
                student_id='TEST001'
            )


class ExamModelTest(TestCase):
    """Test Exam and Question models."""
    
    def setUp(self):
        self.instructor = User.objects.create_user(
            username='instructor',
            email='inst@test.com',
            password='pass',
            role=User.Role.INSTRUCTOR
        )
        
        self.course = Course.objects.create(
            code='TEST101',
            name='Test Course',
            instructor=self.instructor
        )
        
        self.exam = Exam.objects.create(
            title='Test Exam',
            course=self.course,
            duration_minutes=60,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            status=Exam.Status.PUBLISHED,
            created_by=self.instructor
        )
    
    def test_exam_is_active(self):
        """Test exam active status."""
        self.assertTrue(self.exam.is_active)
        
        # Test past exam
        past_exam = Exam.objects.create(
            title='Past Exam',
            course=self.course,
            duration_minutes=60,
            start_time=timezone.now() - timedelta(days=2),
            end_time=timezone.now() - timedelta(days=1),
            status=Exam.Status.PUBLISHED,
            created_by=self.instructor
        )
        self.assertFalse(past_exam.is_active)
    
    def test_exam_total_marks(self):
        """Test total marks calculation."""
        Question.objects.create(
            exam=self.exam,
            question_type=Question.QuestionType.MULTIPLE_CHOICE,
            question_text='Test question 1',
            order=1,
            marks=5.00,
            expected_answer='A',
            options=['A', 'B', 'C', 'D']
        )
        
        Question.objects.create(
            exam=self.exam,
            question_type=Question.QuestionType.SHORT_ANSWER,
            question_text='Test question 2',
            order=2,
            marks=10.00,
            expected_answer={'text': 'Answer'}
        )
        
        self.assertEqual(self.exam.total_marks, 15.00)


class GradingServiceTest(TestCase):
    """Test automated grading service."""
    
    def setUp(self):
        self.instructor = User.objects.create_user(
            username='instructor',
            password='pass',
            role=User.Role.INSTRUCTOR
        )
        self.student = User.objects.create_user(
            username='student',
            password='pass',
            role=User.Role.STUDENT
        )
        
        self.course = Course.objects.create(
            code='TEST',
            name='Test',
            instructor=self.instructor
        )
        
        self.exam = Exam.objects.create(
            title='Test Exam',
            course=self.course,
            duration_minutes=60,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            status=Exam.Status.PUBLISHED,
            created_by=self.instructor
        )
        
        # Create questions
        self.mcq = Question.objects.create(
            exam=self.exam,
            question_type=Question.QuestionType.MULTIPLE_CHOICE,
            question_text='What is 2+2?',
            order=1,
            marks=5.00,
            expected_answer='C',
            options=['A. 3', 'B. 5', 'C. 4', 'D. 6']
        )
        
        self.tf = Question.objects.create(
            exam=self.exam,
            question_type=Question.QuestionType.TRUE_FALSE,
            question_text='The sky is blue.',
            order=2,
            marks=3.00,
            expected_answer='True',
            options=['True', 'False']
        )
        
        self.short = Question.objects.create(
            exam=self.exam,
            question_type=Question.QuestionType.SHORT_ANSWER,
            question_text='Define data structure.',
            order=3,
            marks=7.00,
            expected_answer={
                'text': 'A data structure is a way of organizing and storing data'
            }
        )
    
    def test_mcq_grading(self):
        """Test multiple choice grading."""
        submission = Submission.objects.create(
            student=self.student,
            exam=self.exam,
            status=Submission.Status.SUBMITTED,
            submitted_at=timezone.now()
        )
        
        # Correct answer
        Answer.objects.create(
            submission=submission,
            question=self.mcq,
            answer_text='C'
        )
        
        # Incorrect answer for TF
        Answer.objects.create(
            submission=submission,
            question=self.tf,
            answer_text='False'
        )
        
        # Partial answer for short
        Answer.objects.create(
            submission=submission,
            question=self.short,
            answer_text={'text': 'Data structure organizes data'}
        )
        
        # Grade submission
        result = grading_service.grade_submission(submission)
        
        # Refresh from DB
        submission.refresh_from_db()
        
        self.assertEqual(submission.status, Submission.Status.GRADED)
        self.assertIsNotNone(submission.score)
        self.assertGreater(submission.score, 0)
        self.assertEqual(result['grading_results'][0]['is_correct'], True)
        self.assertEqual(result['grading_results'][1]['is_correct'], False)


class AuthenticationAPITest(APITestCase):
    """Test authentication endpoints."""
    
    def test_user_registration(self):
        """Test user registration."""
        url = reverse('accounts:register')
        data = {
            'username': 'newstudent',
            'email': 'new@test.com',
            'password': 'testpass123',
            'role': 'STUDENT',
            'first_name': 'New',
            'last_name': 'Student'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['username'], 'newstudent')
    
    def test_user_login(self):
        """Test user login."""
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        url = reverse('accounts:login')
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)


class ExamAPITest(APITestCase):
    """Test exam-related API endpoints."""
    
    def setUp(self):
        self.instructor = User.objects.create_user(
            username='instructor',
            password='pass',
            role=User.Role.INSTRUCTOR
        )
        
        self.student = User.objects.create_user(
            username='student',
            password='pass',
            role=User.Role.STUDENT
        )
        
        self.course = Course.objects.create(
            code='TEST',
            name='Test Course',
            instructor=self.instructor
        )
        
        self.exam = Exam.objects.create(
            title='Test Exam',
            course=self.course,
            duration_minutes=60,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            status=Exam.Status.PUBLISHED,
            created_by=self.instructor
        )
        
        self.question = Question.objects.create(
            exam=self.exam,
            question_type=Question.QuestionType.MULTIPLE_CHOICE,
            question_text='Test question',
            order=1,
            marks=10.00,
            expected_answer='A',
            options=['A', 'B', 'C', 'D']
        )
    
    def test_list_exams_requires_authentication(self):
        """Test that listing exams requires authentication."""
        url = reverse('exams:exam-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_student_can_view_published_exams(self):
        """Test students can view published exams."""
        self.client.force_authenticate(user=self.student)
        url = reverse('exams:exam-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_student_cannot_view_draft_exams(self):
        """Test students cannot view draft exams."""
        draft_exam = Exam.objects.create(
            title='Draft Exam',
            course=self.course,
            duration_minutes=60,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=2),
            status=Exam.Status.DRAFT,
            created_by=self.instructor
        )
        
        self.client.force_authenticate(user=self.student)
        url = reverse('exams:exam-list')
        response = self.client.get(url)
        
        # Should only see published exam
        self.assertEqual(len(response.data['results']), 1)


class SubmissionAPITest(APITestCase):
    """Test submission endpoints."""
    
    def setUp(self):
        self.instructor = User.objects.create_user(
            username='instructor',
            password='pass',
            role=User.Role.INSTRUCTOR
        )
        
        self.student = User.objects.create_user(
            username='student',
            password='pass',
            role=User.Role.STUDENT
        )
        
        self.course = Course.objects.create(
            code='TEST',
            name='Test',
            instructor=self.instructor
        )
        
        self.exam = Exam.objects.create(
            title='Test Exam',
            course=self.course,
            duration_minutes=60,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            status=Exam.Status.PUBLISHED,
            created_by=self.instructor
        )
        
        self.question = Question.objects.create(
            exam=self.exam,
            question_type=Question.QuestionType.MULTIPLE_CHOICE,
            question_text='Test',
            order=1,
            marks=10.00,
            expected_answer='A',
            options=['A', 'B']
        )
    
    def test_submit_exam(self):
        """Test submitting exam answers."""
        self.client.force_authenticate(user=self.student)
        
        url = reverse('exams:exam-submit', kwargs={'exam_id': self.exam.id})
        data = {
            'answers': [
                {
                    'question_id': self.question.id,
                    'answer_text': 'A'
                }
            ]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('submission', response.data)
        self.assertIn('grading_summary', response.data)
        
        # Verify submission was created
        submission = Submission.objects.get(student=self.student, exam=self.exam)
        self.assertEqual(submission.status, Submission.Status.GRADED)
        self.assertIsNotNone(submission.score)
    
    def test_cannot_exceed_attempt_limit(self):
        """Test attempt limit enforcement."""
        self.exam.max_attempts = 1
        self.exam.save()
        
        # Create first submission
        Submission.objects.create(
            student=self.student,
            exam=self.exam,
            attempt_number=1,
            status=Submission.Status.GRADED,
            submitted_at=timezone.now()
        )
        
        self.client.force_authenticate(user=self.student)
        
        url = reverse('exams:exam-submit', kwargs={'exam_id': self.exam.id})
        data = {
            'answers': [
                {
                    'question_id': self.question.id,
                    'answer_text': 'A'
                }
            ]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_student_can_only_view_own_submissions(self):
        """Test students can only view their own submissions."""
        other_student = User.objects.create_user(
            username='other',
            password='pass',
            role=User.Role.STUDENT
        )
        
        submission = Submission.objects.create(
            student=other_student,
            exam=self.exam,
            status=Submission.Status.GRADED,
            submitted_at=timezone.now()
        )
        
        self.client.force_authenticate(user=self.student)
        url = reverse('exams:submission-list')
        response = self.client.get(url)
        
        # Should see 0 submissions (not other student's)
        self.assertEqual(len(response.data['results']), 0)
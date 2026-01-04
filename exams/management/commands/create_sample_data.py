from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from exams.models import Course, Exam, Question


class Command(BaseCommand):
    help = 'Creates sample data for testing the assessment engine'
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Creating sample data...')
        
        # Create users
        instructor, _ = User.objects.get_or_create(
            username='instructor1',
            defaults={
                'email': 'instructor@acadai.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'role': User.Role.INSTRUCTOR,
                'is_staff': True
            }
        )
        instructor.set_password('password123')
        instructor.save()
        self.stdout.write(self.style.SUCCESS(f'✓ Created instructor: {instructor.username}'))
        
        student, _ = User.objects.get_or_create(
            username='student1',
            defaults={
                'email': 'student@acadai.com',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'role': User.Role.STUDENT,
                'student_id': 'STU001'
            }
        )
        student.set_password('password123')
        student.save()
        self.stdout.write(self.style.SUCCESS(f'✓ Created student: {student.username}'))
        
        # Create course
        course, _ = Course.objects.get_or_create(
            code='CS101',
            defaults={
                'name': 'Introduction to Computer Science',
                'description': 'Fundamental concepts of computer science',
                'instructor': instructor
            }
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created course: {course.code}'))
        
        # Create exam
        exam, created = Exam.objects.get_or_create(
            title='Midterm Exam - Data Structures',
            course=course,
            defaults={
                'description': 'Assessment covering arrays, linked lists, and trees',
                'duration_minutes': 60,
                'start_time': timezone.now() - timedelta(days=1),
                'end_time': timezone.now() + timedelta(days=7),
                'status': Exam.Status.PUBLISHED,
                'passing_score': 60.00,
                'max_attempts': 2,
                'created_by': instructor,
                'metadata': {
                    'instructions': 'Answer all questions. Partial credit available.',
                    'resources': 'Open book exam'
                }
            }
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Created exam: {exam.title}'))
        
        if created:
            # Create questions
            questions_data = [
                {
                    'question_type': Question.QuestionType.MULTIPLE_CHOICE,
                    'question_text': 'What is the time complexity of binary search?',
                    'order': 1,
                    'marks': 5.00,
                    'expected_answer': 'C',
                    'options': ['A. O(n)', 'B. O(n²)', 'C. O(log n)', 'D. O(1)']
                },
                {
                    'question_type': Question.QuestionType.TRUE_FALSE,
                    'question_text': 'A linked list requires contiguous memory allocation.',
                    'order': 2,
                    'marks': 3.00,
                    'expected_answer': 'False',
                    'options': ['True', 'False']
                },
                {
                    'question_type': Question.QuestionType.SHORT_ANSWER,
                    'question_text': 'Explain the difference between a stack and a queue.',
                    'order': 3,
                    'marks': 7.00,
                    'expected_answer': {
                        'text': 'A stack is a Last-In-First-Out (LIFO) data structure '
                                'where elements are added and removed from the same end. '
                                'A queue is a First-In-First-Out (FIFO) data structure '
                                'where elements are added at one end and removed from the other.'
                    }
                },
                {
                    'question_type': Question.QuestionType.ESSAY,
                    'question_text': 'Discuss the advantages and disadvantages of using '
                                     'arrays versus linked lists for data storage.',
                    'order': 4,
                    'marks': 10.00,
                    'expected_answer': {
                        'text': 'Arrays provide fast random access and cache locality '
                                'but have fixed size and expensive insertions. Linked lists '
                                'allow dynamic size and efficient insertions but have slower '
                                'access time and higher memory overhead due to pointers.'
                    }
                }
            ]
            
            for q_data in questions_data:
                Question.objects.create(exam=exam, **q_data)
            
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(questions_data)} questions'))
        
        # Print summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('Sample data created successfully!'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write('\nLogin credentials:')
        self.stdout.write(f'  Instructor: username=instructor1, password=password123')
        self.stdout.write(f'  Student: username=student1, password=password123')
        self.stdout.write('\nYou can now:')
        self.stdout.write('  1. Run the server: python manage.py runserver')
        self.stdout.write('  2. Visit Swagger docs: http://localhost:8000/swagger/')
        self.stdout.write('  3. Login and get token: POST /api/auth/login/')
        self.stdout.write('  4. Submit exam: POST /api/exams/{id}/submit/')
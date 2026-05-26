# Acad AI Mini Assessment Engine

A Django-based REST API for managing academic assessments with automated grading capabilities.

## Features

- **Secure Authentication**: Token-based authentication with role-based access control
- **Exam Management**: Create and manage exams with multiple question types
- **Automated Grading**: Built-in grading engine supporting:
  - Multiple Choice Questions (exact match)
  - True/False (exact match)
  - Short Answer (keyword matching with partial credit)
  - Essay (keyword matching with partial credit)
- **Student Portal**: Dashboard with performance analytics
- **Instructor Tools**: Statistics and result management
- **API Documentation**: Comprehensive Swagger/OpenAPI documentation or link to postman collection

## Requirements

- Python 3.8+
- Django 4.2+
- Django REST Framework 3.14+
- SQLite (default) or PostgreSQL (production)

## Installation

### 1. Clone and Setup

```bash
# Create project directory
mkdir acad_ai_assessment
cd acad_ai_assessment

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install django djangorestframework django-filter drf-yasg
pip freeze > requirements.txt
```

### 2. Create Django Project

```bash
# Create project
django-admin startproject assessment_engine .

# Create apps
python manage.py startapp exams
python manage.py startapp accounts
```

### 3. Configure Settings

Copy the `settings.py` configuration provided in the artifacts and update:
- `SECRET_KEY` (generate a new one for production)
- `DEBUG = False` for production
- `ALLOWED_HOSTS` to include your domain

### 4. Create Models

Copy all model files into their respective locations:
- `accounts/models.py` - User model
- `exams/models.py` - Exam, Question, Submission, Answer models

### 5. Create Migrations

```bash
# Create migrations
python manage.py makemigrations accounts
python manage.py makemigrations exams

# Apply migrations
python manage.py migrate
```

### 6. Create Management Command Directory

```bash
mkdir -p exams/management/commands
touch exams/management/__init__.py
touch exams/management/commands/__init__.py
```

Copy the `create_sample_data.py` management command.

### 7. Create Sample Data

```bash
python manage.py create_sample_data
```

This creates:
- Instructor account: `username=instructor1, password=password123`
- Student account: `username=student1, password=password123`
- Sample course and exam with questions

### 8. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 9. Run Development Server

```bash
python manage.py runserver
```

## API Documentation

Once the server is running, access the API documentation:

- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/
- **Admin Panel**: http://localhost:8000/admin/

## Authentication

### Register New User

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newstudent",
    "email": "student@example.com",
    "password": "securepass123",
    "role": "STUDENT",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

### Login

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "student1",
    "password": "password123"
  }'
```

Response:
```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

### Use Token in Requests

Include the token in the Authorization header:
```
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

## API Endpoints

### Authentication
- `POST /api/auth/register/` - Register new user
- `POST /api/auth/login/` - Login and get token
- `POST /api/auth/logout/` - Logout (delete token)
- `GET /api/auth/profile/` - View profile
- `PUT /api/auth/profile/` - Update profile

### Courses
- `GET /api/courses/` - List all courses
- `GET /api/courses/{id}/` - Get course details

### Exams
- `GET /api/exams/` - List available exams
- `GET /api/exams/{id}/` - Get exam details with questions
- `GET /api/exams/{id}/my_submissions/` - Get my submissions for this exam
- `GET /api/exams/{id}/statistics/` - Get exam statistics (instructors only)

### Submissions
- `POST /api/exams/{id}/submit/` - Submit exam answers
- `GET /api/submissions/` - List submissions
- `GET /api/submissions/{id}/` - Get submission details
- `GET /api/submissions/my_results/` - Get all my results

### Dashboard
- `GET /api/dashboard/` - Student dashboard with analytics

## Usage Examples

### 1. List Available Exams

```bash
curl -X GET http://localhost:8000/api/exams/ \
  -H "Authorization: Token YOUR_TOKEN"
```

### 2. Get Exam Details

```bash
curl -X GET http://localhost:8000/api/exams/1/ \
  -H "Authorization: Token YOUR_TOKEN"
```

### 3. Submit Exam

```bash
curl -X POST http://localhost:8000/api/exams/1/submit/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "answers": [
      {
        "question_id": 1,
        "answer_text": "C"
      },
      {
        "question_id": 2,
        "answer_text": "False"
      },
      {
        "question_id": 3,
        "answer_text": {
          "text": "A stack is LIFO while queue is FIFO"
        }
      }
    ]
  }'
```

Response includes:
- Submission details
- Grading results
- Score and feedback
- Individual answer grades

### 4. View My Results

```bash
curl -X GET http://localhost:8000/api/submissions/my_results/ \
  -H "Authorization: Token YOUR_TOKEN"
```

### 5. View Dashboard

```bash
curl -X GET http://localhost:8000/api/dashboard/ \
  -H "Authorization: Token YOUR_TOKEN"
```

## Running Tests

```bash
# Run all tests
python manage.py test

# Run specific test class
python manage.py test exams.tests.GradingServiceTest

# Run with verbose output
python manage.py test --verbosity=2
```

## Architecture

### Database Schema

```
Users (Custom User Model)
├── id (PK)
├── username
├── email
├── role (STUDENT/INSTRUCTOR/ADMIN)
└── student_id

Courses
├── id (PK)
├── code
├── name
├── instructor_id (FK → Users)
└── timestamps

Exams
├── id (PK)
├── title
├── course_id (FK → Courses)
├── duration_minutes
├── start_time
├── end_time
├── status (DRAFT/PUBLISHED/ARCHIVED)
├── passing_score
├── max_attempts
└── timestamps

Questions
├── id (PK)
├── exam_id (FK → Exams)
├── question_type (MCQ/SHORT/ESSAY/TF)
├── question_text
├── order
├── marks
├── expected_answer (JSON)
└── options (JSON)

Submissions
├── id (PK)
├── student_id (FK → Users)
├── exam_id (FK → Exams)
├── attempt_number
├── status (IN_PROGRESS/SUBMITTED/GRADING/GRADED)
├── score
├── marks_obtained
└── timestamps

Answers
├── id (PK)
├── submission_id (FK → Submissions)
├── question_id (FK → Questions)
├── answer_text (JSON)
├── marks_awarded
├── is_correct
└── feedback
```

### Key Design Decisions

1. **Indexing Strategy**:
   - Composite indexes on frequently queried fields
   - Index on (student, submitted_at) for fast result retrieval
   - Index on (exam, status) for filtering

2. **Query Optimization**:
   - `select_related()` for foreign keys
   - `prefetch_related()` for reverse relations
   - Minimal queries using annotations and aggregations

3. **Security**:
   - Token authentication
   - Role-based permissions
   - Students can only access their own data
   - Input validation at serializer level
   - Atomic transactions for submissions

4. **Grading Service**:
   - Strategy pattern for different question types
   - Keyword matching algorithm for open-ended questions
   - Partial credit support
   - Modular design for easy extension

## Configuration

### Production Settings

For production deployment:

1. **Use PostgreSQL**:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'assessment_db',
        'USER': 'db_user',
        'PASSWORD': 'db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

2. **Security Settings**:
```python
DEBUG = False
SECRET_KEY = config('SECRET_KEY')
ALLOWED_HOSTS = ['yourdomain.com']
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

3. **Static Files**:
```bash
python manage.py collectstatic
```

##  Performance Features

1. **Database Optimization**:
   - Strategic indexing on frequently queried fields
   - Composite indexes for multi-column queries
   - Query optimization using select_related and prefetch_related

2. **Caching** (can be added):
   - Cache exam details
   - Cache submission results
   - Redis integration for session storage

3. **Pagination**:
   - Default page size: 20 items
   - Configurable per endpoint

## Grading Algorithm

### Multiple Choice / True-False
- Exact match comparison
- All or nothing scoring

### Short Answer / Essay
1. **Text Preprocessing**:
   - Lowercase conversion
   - Punctuation removal
   - Whitespace normalization

2. **Keyword Extraction**:
   - Remove stop words
   - Extract meaningful terms

3. **Similarity Calculation**:
   - Jaccard similarity: `|A ∩ B| / |A ∪ B|`
   - Keyword coverage: `|student ∩ expected| / |expected|`
   - Weighted combination: `0.4 × jaccard + 0.6 × coverage`

4. **Scoring**:
   - ≥90% similarity: Excellent (full marks)
   - ≥70% similarity: Good (70-90% marks)
   - ≥50% similarity: Partial (50-70% marks)
   - <50% similarity: Insufficient (<50% marks)

## Future Enhancements

1. **LLM Integration**:
   - OpenAI/Claude integration for advanced grading
   - Contextual understanding of answers
   - Detailed feedback generation

2. **Real-time Features**:
   - WebSocket support for live exams
   - Proctoring capabilities
   - Live grading updates

3. **Analytics**:
   - Advanced performance metrics
   - Question difficulty analysis
   - Learning outcome tracking

4. **Additional Question Types**:
   - File upload questions
   - Code evaluation
   - Matching questions
   - Fill-in-the-blank

## Support

For issues or questions:
- Review the Swagger documentation
- Check test cases for examples
- Examine the grading service implementation

## License

MIT License - Feel free to use for academic purposes.

---

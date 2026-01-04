from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
import re
from collections import Counter
from django.utils import timezone
from django.db import transaction
from .models import Submission, Answer, Question


class GradingStrategy(ABC):
    """Abstract base class for grading strategies."""
    
    @abstractmethod
    def grade(self, question: Question, student_answer: Any, expected_answer: Any) -> Tuple[float, bool, str]:
        """
        Grade a single answer.
        
        Returns:
            Tuple of (marks_awarded, is_correct, feedback)
        """
        pass


class MultipleChoiceGrader(GradingStrategy):
    """Grading strategy for multiple choice questions."""
    
    def grade(self, question: Question, student_answer: Any, expected_answer: Any) -> Tuple[float, bool, str]:
        """Grade MCQ by exact match."""
        if not isinstance(student_answer, (str, int)):
            return 0.0, False, "Invalid answer format."
        
        if not isinstance(expected_answer, (str, int)):
            return 0.0, False, "Invalid expected answer format."
        
        # Normalize answers
        student_ans = str(student_answer).strip().upper()
        expected_ans = str(expected_answer).strip().upper()
        
        is_correct = student_ans == expected_ans
        marks = question.marks if is_correct else 0.0
        
        feedback = "Correct!" if is_correct else f"Incorrect. Expected: {expected_ans}"
        
        return float(marks), is_correct, feedback


class TrueFalseGrader(GradingStrategy):
    """Grading strategy for true/false questions."""
    
    def grade(self, question: Question, student_answer: Any, expected_answer: Any) -> Tuple[float, bool, str]:
        """Grade True/False by exact match."""
        # Normalize boolean values
        true_values = {'true', 't', 'yes', 'y', '1', 1, True}
        false_values = {'false', 'f', 'no', 'n', '0', 0, False}
        
        student_bool = None
        if str(student_answer).lower().strip() in true_values:
            student_bool = True
        elif str(student_answer).lower().strip() in false_values:
            student_bool = False
        
        expected_bool = None
        if str(expected_answer).lower().strip() in true_values:
            expected_bool = True
        elif str(expected_answer).lower().strip() in false_values:
            expected_bool = False
        
        if student_bool is None:
            return 0.0, False, "Invalid answer format. Please answer True or False."
        
        is_correct = student_bool == expected_bool
        marks = question.marks if is_correct else 0.0
        
        feedback = "Correct!" if is_correct else f"Incorrect. Expected: {expected_bool}"
        
        return float(marks), is_correct, feedback


class KeywordMatchingGrader(GradingStrategy):
    """
    Grading strategy using keyword matching and density.
    Suitable for short answers and essays.
    """
    
    def __init__(self, partial_credit: bool = True):
        self.partial_credit = partial_credit
    
    def _preprocess_text(self, text: str) -> str:
        """Normalize text for comparison."""
        if not isinstance(text, str):
            text = str(text)
        
        # Convert to lowercase and remove extra whitespace
        text = text.lower().strip()
        # Remove punctuation except apostrophes
        text = re.sub(r'[^\w\s\']', ' ', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text
    
    def _extract_keywords(self, text: str) -> set:
        """Extract meaningful keywords from text."""
        # Remove common stop words
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
            'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
            'that', 'the', 'to', 'was', 'will', 'with'
        }
        
        words = self._preprocess_text(text).split()
        keywords = {w for w in words if w not in stop_words and len(w) > 2}
        
        return keywords
    
    def _calculate_similarity(self, student_text: str, expected_text: str) -> float:
        """Calculate similarity score between 0 and 1."""
        student_keywords = self._extract_keywords(student_text)
        expected_keywords = self._extract_keywords(expected_text)
        
        if not expected_keywords:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = len(student_keywords & expected_keywords)
        union = len(student_keywords | expected_keywords)
        
        if union == 0:
            return 0.0
        
        jaccard_similarity = intersection / union
        
        # Calculate keyword coverage (what % of expected keywords are present)
        coverage = intersection / len(expected_keywords) if expected_keywords else 0.0
        
        # Weighted combination: prioritize coverage
        similarity = (0.4 * jaccard_similarity) + (0.6 * coverage)
        
        return similarity
    
    def grade(self, question: Question, student_answer: Any, expected_answer: Any) -> Tuple[float, bool, str]:
        """Grade using keyword matching."""
        if not isinstance(student_answer, str) or not student_answer.strip():
            return 0.0, False, "No answer provided."
        
        if not isinstance(expected_answer, str):
            expected_answer = str(expected_answer)
        
        # Calculate similarity
        similarity = self._calculate_similarity(student_answer, expected_answer)
        
        # Determine marks based on similarity
        if self.partial_credit:
            # Award partial credit based on similarity
            marks = float(question.marks) * similarity
            
            # Determine correctness threshold
            is_correct = similarity >= 0.7
            
            # Generate feedback
            if similarity >= 0.9:
                feedback = "Excellent answer! Very comprehensive."
            elif similarity >= 0.7:
                feedback = "Good answer. Covers most key points."
            elif similarity >= 0.5:
                feedback = "Partial credit awarded. Some key points missing."
            elif similarity >= 0.3:
                feedback = "Limited understanding demonstrated. Review the topic."
            else:
                feedback = "Insufficient answer. Missing most key concepts."
        else:
            # All or nothing grading
            is_correct = similarity >= 0.8
            marks = float(question.marks) if is_correct else 0.0
            feedback = "Correct!" if is_correct else "Incorrect or incomplete answer."
        
        return marks, is_correct, feedback


class GradingService:
    """
    Main grading service that orchestrates the grading process.
    Uses strategy pattern for different question types.
    """
    
    def __init__(self):
        self.graders = {
            Question.QuestionType.MULTIPLE_CHOICE: MultipleChoiceGrader(),
            Question.QuestionType.TRUE_FALSE: TrueFalseGrader(),
            Question.QuestionType.SHORT_ANSWER: KeywordMatchingGrader(partial_credit=True),
            Question.QuestionType.ESSAY: KeywordMatchingGrader(partial_credit=True),
        }
    
    def _get_grader(self, question_type: str) -> GradingStrategy:
        """Get appropriate grader for question type."""
        return self.graders.get(
            question_type,
            KeywordMatchingGrader(partial_credit=True)  # Default fallback
)
    
    @transaction.atomic
    def grade_submission(self, submission: Submission) -> Dict[str, Any]:
        """
        Grade a complete submission.
        
        Returns:
            Dictionary containing grading results and statistics.
        """
        if submission.status != Submission.Status.SUBMITTED:
            raise ValueError("Can only grade submissions with status SUBMITTED")
        
        # Update status to grading
        submission.status = Submission.Status.GRADING
        submission.save(update_fields=['status'])
        
        answers = submission.answers.select_related('question').all()
        
        total_marks_obtained = 0.0
        total_marks_possible = 0.0
        correct_count = 0
        total_count = len(answers)
        
        grading_results = []
        
        # Grade each answer
        for answer in answers:
            question = answer.question
            grader = self._get_grader(question.question_type)
            
            # Extract answer text
            student_answer = answer.answer_text
            if isinstance(student_answer, dict) and 'text' in student_answer:
                student_answer = student_answer['text']
            
            # Extract expected answer
            expected_answer = question.expected_answer
            if isinstance(expected_answer, dict) and 'text' in expected_answer:
                expected_answer = expected_answer['text']
            
            # Grade the answer
            marks_awarded, is_correct, feedback = grader.grade(
                question, student_answer, expected_answer
            )
            
            # Update answer record
            answer.marks_awarded = marks_awarded
            answer.is_correct = is_correct
            answer.feedback = feedback
            answer.graded_at = timezone.now()
            answer.save()
            
            # Accumulate statistics
            total_marks_obtained += marks_awarded
            total_marks_possible += float(question.marks)
            if is_correct:
                correct_count += 1
            
            grading_results.append({
                'question_id': question.id,
                'marks_awarded': marks_awarded,
                'is_correct': is_correct,
                'feedback': feedback
            })
        
        # Calculate final score
        score = (total_marks_obtained / total_marks_possible * 100) if total_marks_possible > 0 else 0.0
        
        # Update submission
        submission.status = Submission.Status.GRADED
        submission.marks_obtained = total_marks_obtained
        submission.score = score
        submission.graded_at = timezone.now()
        submission.feedback = {
            'total_questions': total_count,
            'correct_answers': correct_count,
            'accuracy': f"{(correct_count / total_count * 100):.1f}%" if total_count > 0 else "0%",
            'performance': self._get_performance_feedback(score),
            'graded_by': 'Automated Grading System'
        }
        submission.save()
        
        return {
            'submission_id': submission.id,
            'score': float(score),
            'marks_obtained': float(total_marks_obtained),
            'total_marks': float(total_marks_possible),
            'is_passed': submission.is_passed,
            'grading_results': grading_results,
            'feedback': submission.feedback
        }
    
    def _get_performance_feedback(self, score: float) -> str:
        """Generate performance feedback based on score."""
        if score >= 90:
            return "Outstanding! Excellent understanding of the material."
        elif score >= 80:
            return "Very good! Strong grasp of the concepts."
        elif score >= 70:
            return "Good work! Solid understanding with room for improvement."
        elif score >= 60:
            return "Satisfactory. Consider reviewing key concepts."
        elif score >= 50:
            return "Below expectations. Additional study recommended."
        else:
            return "Needs significant improvement. Please review the material thoroughly."


# Singleton instance
grading_service = GradingService()
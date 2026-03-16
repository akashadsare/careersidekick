"""
Seed script for answer library questions (M1.1).

Populates the answer_library_questions table with 20+ common ATS screening questions.
Run this after database migrations.

Usage:
    cd backend
    python -m scripts.seed_answer_library
"""

from app.db import SessionLocal
from app.db_models import AnswerLibraryQuestion


# 20+ Common ATS Questions by category
QUESTIONS = [
    # Work Authorization (critical)
    {
        'question_text': 'Are you authorized to work in this country?',
        'question_category': 'work_auth',
        'portal_types': ['greenhouse', 'lever', 'workday', 'ashby'],
        'frequency_rank': 1,
    },
    {
        'question_text': 'Do you require sponsorship for work authorization?',
        'question_category': 'work_auth',
        'portal_types': ['greenhouse', 'lever', 'workday'],
        'frequency_rank': 2,
    },
    {
        'question_text': 'What is your visa status?',
        'question_category': 'work_auth',
        'portal_types': ['workday'],
        'frequency_rank': 3,
    },
    
    # Experience (common)
    {
        'question_text': 'How many years of experience do you have in the primary technology/skill for this role?',
        'question_category': 'experience',
        'portal_types': ['greenhouse', 'lever', 'ashby'],
        'frequency_rank': 4,
    },
    {
        'question_text': 'Describe your experience with [Technology/Framework]',
        'question_category': 'experience',
        'portal_types': ['greenhouse', 'lever'],
        'frequency_rank': 5,
    },
    {
        'question_text': 'What is your current or most recent title?',
        'question_category': 'experience',
        'portal_types': ['workday', 'greenhouse'],
        'frequency_rank': 6,
    },
    {
        'question_text': 'How many years of management experience do you have?',
        'question_category': 'experience',
        'portal_types': ['greenhouse', 'lever'],
        'frequency_rank': 7,
    },
    
    # Location & Work Model (common)
    {
        'question_text': 'Are you able to relocate to [Location]?',
        'question_category': 'location',
        'portal_types': ['greenhouse', 'lever'],
        'frequency_rank': 8,
    },
    {
        'question_text': 'What is your preferred work arrangement (remote, hybrid, or onsite)?',
        'question_category': 'location',
        'portal_types': ['greenhouse', 'lever', 'ashby'],
        'frequency_rank': 9,
    },
    {
        'question_text': 'Are you currently located in or willing to relocate to [City/Region]?',
        'question_category': 'location',
        'portal_types': ['workday'],
        'frequency_rank': 10,
    },
    
    # Salary & Compensation
    {
        'question_text': 'What is your expected salary range?',
        'question_category': 'compensation',
        'portal_types': ['greenhouse', 'lever', 'ashby'],
        'frequency_rank': 11,
    },
    {
        'question_text': 'What is your salary expectation for this role?',
        'question_category': 'compensation',
        'portal_types': ['workday'],
        'frequency_rank': 12,
    },
    
    # Availability
    {
        'question_text': 'What is your notice period (when can you start)?',
        'question_category': 'availability',
        'portal_types': ['greenhouse', 'lever'],
        'frequency_rank': 13,
    },
    {
        'question_text': 'When are you available to start?',
        'question_category': 'availability',
        'portal_types': ['workday', 'ashby'],
        'frequency_rank': 14,
    },
    
    # Education & Skills
    {
        'question_text': 'What is your highest level of education?',
        'question_category': 'education',
        'portal_types': ['greenhouse', 'workday'],
        'frequency_rank': 15,
    },
    {
        'question_text': 'Do you have a degree in [Field]?',
        'question_category': 'education',
        'portal_types': ['greenhouse', 'lever'],
        'frequency_rank': 16,
    },
    
    # Culture & Motivation
    {
        'question_text': 'Why are you interested in this role?',
        'question_category': 'culture',
        'portal_types': ['greenhouse', 'lever', 'ashby'],
        'frequency_rank': 17,
    },
    {
        'question_text': 'Why are you interested in joining our company?',
        'question_category': 'culture',
        'portal_types': ['greenhouse', 'lever', 'workday'],
        'frequency_rank': 18,
    },
    {
        'question_text': 'Tell us about a time you overcame a challenge at work',
        'question_category': 'culture',
        'portal_types': ['greenhouse', 'lever'],
        'frequency_rank': 19,
    },
    {
        'question_text': 'What are your long-term career goals?',
        'question_category': 'culture',
        'portal_types': ['greenhouse', 'ashby'],
        'frequency_rank': 20,
    },
    
    # Additional common questions
    {
        'question_text': 'Have you worked for a company like ours before?',
        'question_category': 'experience',
        'portal_types': ['greenhouse', 'lever'],
        'frequency_rank': 21,
    },
    {
        'question_text': 'Do you have a portfolio or GitHub profile we can review?',
        'question_category': 'skills',
        'portal_types': ['greenhouse', 'lever', 'ashby'],
        'frequency_rank': 22,
    },
    {
        'question_text': 'Are you able to pass a background check?',
        'question_category': 'compliance',
        'portal_types': ['greenhouse', 'workday'],
        'frequency_rank': 23,
    },
    {
        'question_text': 'Are you willing to work weekends/evenings if needed?',
        'question_category': 'availability',
        'portal_types': ['greenhouse'],
        'frequency_rank': 24,
    },
]


def seed_answer_library():
    """Populate answer library with common questions."""
    db = SessionLocal()
    
    try:
        # Check if questions already exist
        existing_count = db.query(AnswerLibraryQuestion).count()
        if existing_count > 0:
            print(f'Answer library already seeded with {existing_count} questions. Skipping.')
            return
        
        # Insert questions
        for q in QUESTIONS:
            question = AnswerLibraryQuestion(
                question_text=q['question_text'],
                question_category=q['question_category'],
                portal_types=q['portal_types'],
                frequency_rank=q['frequency_rank'],
            )
            db.add(question)
        
        db.commit()
        print(f'Successfully seeded {len(QUESTIONS)} answer library questions.')
    
    except Exception as e:
        db.rollback()
        print(f'Error seeding answer library: {e}')
        raise
    
    finally:
        db.close()


if __name__ == '__main__':
    seed_answer_library()

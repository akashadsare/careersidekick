"""
Candidate profile onboarding endpoints (M1.1)

Handles:
- Resume upload and storage (S3)
- Resume parsing to structured fields
- Candidate profile creation and updates
- Answer library management
"""

import json
import os
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..db_models import AnswerLibraryQuestion, CandidateAnswer, CandidateProfile, Resume
from ..models import (
    CandidateAnswerCreateRequest,
    CandidateAnswerResponse,
    CandidateAnswersListResponse,
    CandidateProfileCreateRequest,
    CandidateProfileResponse,
    CandidateProfileUpdateRequest,
    AnswerLibraryQuestionResponse,
    ResumeParseData,
    ResumeUploadResponse,
)

router = APIRouter()

# Configuration
MAX_RESUME_SIZE_MB = 10
ALLOWED_MIME_TYPES = {'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}


def parse_resume_text(text: str) -> ResumeParseData:
    """
    Mock resume parser. In production, integrate with Affinda or similar.
    
    For now, use simple heuristics to extract common fields.
    Phase 2 will integrate proper resume parsing service.
    """
    data = ResumeParseData()
    
    lines = text.lower().split('\n')
    
    # Simple heuristics for common fields
    email_patterns = [line.strip() for line in lines if '@' in line and '.com' in line]
    if email_patterns:
        data.email = email_patterns[0].strip()
    
    phone_patterns = [line.strip() for line in lines if any(c.isdigit() for c in line) and len(line) < 20 and ('-' in line or '(' in line)]
    if phone_patterns:
        data.phone = phone_patterns[0].strip()
    
    # Try to extract years of experience
    for line in lines:
        if 'years' in line and 'experience' in line:
            try:
                import re
                matches = re.findall(r'(\d+)\+?\s*year', line)
                if matches:
                    data.years_experience = int(matches[0])
                    break
            except (ValueError, IndexError):
                pass
    
    # Extract skills (simple: look for common tech keywords)
    common_skills = {
        'python', 'javascript', 'typescript', 'nodejs', 'react', 'fastapi', 
        'sql', 'postgres', 'aws', 'docker', 'kubernetes', 'git', 'agile',
        'machine learning', 'data analysis', 'api', 'rest', 'graphql'
    }
    data.skills = [skill for skill in common_skills if skill in text.lower()]
    
    return data


async def parse_resume_file(file_content: bytes, mime_type: str) -> ResumeParseData:
    """
    Parse resume file (PDF or DOCX) to extract structured data.
    
    Phase 1: Simple text extraction
    Phase 2: Integrate Affinda or Eden AI API
    """
    
    # For now, attempt basic text extraction
    text = ""
    
    if mime_type == 'application/pdf':
        # Phase 2: Use PyPDF2 or pdfplumber for better extraction
        # For now, skip PDF complex parsing
        text = "[PDF parsing not yet implemented; please manually review]"
    
    elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        # Phase 2: Use python-docx for DOCX parsing
        try:
            from docx import Document
            doc = Document(BytesIO(file_content))
            text = '\n'.join([para.text for para in doc.paragraphs])
        except ImportError:
            text = "[DOCX parsing requires python-docx; manual review recommended]"
    
    return parse_resume_text(text)


@router.post('/candidates', response_model=CandidateProfileResponse, status_code=status.HTTP_201_CREATED)
def create_candidate_profile(
    req: CandidateProfileCreateRequest,
    db: Session = Depends(get_db),
) -> CandidateProfileResponse:
    """
    Create a new candidate profile (M1.1 — Candidate Profile Onboarding).
    
    - Full name, email, phone, location, years of experience
    - Work authorization and remote preference
    - Target titles, companies, salary floor
    - LinkedIn profile URL
    """
    candidate = CandidateProfile(
        full_name=req.full_name,
        email=req.email,
        phone=req.phone,
        location=req.location,
        years_experience=req.years_experience,
        work_authorization=req.work_authorization,
        remote_preference=req.remote_preference,
        target_titles=req.target_titles or [],
        target_companies=req.target_companies or [],
        salary_floor_usd=req.salary_floor_usd,
        linkedin_url=req.linkedin_url,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    
    return CandidateProfileResponse(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        location=candidate.location,
        years_experience=candidate.years_experience,
        work_authorization=candidate.work_authorization,
        remote_preference=candidate.remote_preference,
        target_titles=candidate.target_titles,
        target_companies=candidate.target_companies,
        salary_floor_usd=candidate.salary_floor_usd,
        linkedin_url=candidate.linkedin_url,
        primary_resume_id=candidate.primary_resume_id,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


@router.get('/candidates/{candidate_id}', response_model=CandidateProfileResponse)
def get_candidate_profile(
    candidate_id: int,
    db: Session = Depends(get_db),
) -> CandidateProfileResponse:
    """Retrieve a candidate profile by ID."""
    candidate = db.query(CandidateProfile).filter(CandidateProfile.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Candidate not found')
    
    return CandidateProfileResponse(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        location=candidate.location,
        years_experience=candidate.years_experience,
        work_authorization=candidate.work_authorization,
        remote_preference=candidate.remote_preference,
        target_titles=candidate.target_titles,
        target_companies=candidate.target_companies,
        salary_floor_usd=candidate.salary_floor_usd,
        linkedin_url=candidate.linkedin_url,
        primary_resume_id=candidate.primary_resume_id,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


@router.patch('/candidates/{candidate_id}', response_model=CandidateProfileResponse)
def update_candidate_profile(
    candidate_id: int,
    req: CandidateProfileUpdateRequest,
    db: Session = Depends(get_db),
) -> CandidateProfileResponse:
    """Update candidate profile fields."""
    candidate = db.query(CandidateProfile).filter(CandidateProfile.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Candidate not found')
    
    if req.full_name is not None:
        candidate.full_name = req.full_name
    if req.email is not None:
        candidate.email = req.email
    if req.phone is not None:
        candidate.phone = req.phone
    if req.location is not None:
        candidate.location = req.location
    if req.years_experience is not None:
        candidate.years_experience = req.years_experience
    if req.work_authorization is not None:
        candidate.work_authorization = req.work_authorization
    if req.remote_preference is not None:
        candidate.remote_preference = req.remote_preference
    if req.target_titles is not None:
        candidate.target_titles = req.target_titles
    if req.target_companies is not None:
        candidate.target_companies = req.target_companies
    if req.salary_floor_usd is not None:
        candidate.salary_floor_usd = req.salary_floor_usd
    if req.linkedin_url is not None:
        candidate.linkedin_url = req.linkedin_url
    
    db.commit()
    db.refresh(candidate)
    
    return CandidateProfileResponse(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        location=candidate.location,
        years_experience=candidate.years_experience,
        work_authorization=candidate.work_authorization,
        remote_preference=candidate.remote_preference,
        target_titles=candidate.target_titles,
        target_companies=candidate.target_companies,
        salary_floor_usd=candidate.salary_floor_usd,
        linkedin_url=candidate.linkedin_url,
        primary_resume_id=candidate.primary_resume_id,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


@router.post('/candidates/{candidate_id}/resumes', response_model=ResumeUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    candidate_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ResumeUploadResponse:
    """
    Upload and parse a resume file (M1.1 — Resume Upload & Parsing).
    
    Supported formats:
    - application/pdf
    - application/vnd.openxmlformats-officedocument.wordprocessingml.document (DOCX)
    
    Returns parsed fields: name, email, phone, location, years of experience, skills.
    """
    
    # Verify candidate exists
    candidate = db.query(CandidateProfile).filter(CandidateProfile.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Candidate not found')
    
    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Unsupported file type. Allowed: {", ".join(ALLOWED_MIME_TYPES)}'
        )
    
    # Read file content
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    
    if file_size_mb > MAX_RESUME_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'File size exceeds {MAX_RESUME_SIZE_MB}MB limit'
        )
    
    # Parse resume
    try:
        parsed_data = await parse_resume_file(content, file.content_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Resume parsing failed: {str(e)}'
        )
    
    # Store resume record (S3 key is mock for now; Phase 2 will integrate actual S3)
    s3_key = f"resumes/{candidate_id}/{file.filename}"
    
    resume = Resume(
        candidate_id=candidate_id,
        file_name=file.filename or 'resume.pdf',
        s3_key=s3_key,
        file_size_bytes=len(content),
        mime_type=file.content_type,
        parsed_data=parsed_data.model_dump(),
        parser_used='simple_heuristic',
        parse_confidence=0.5,  # Phase 1: mock confidence; Phase 2: real parser confidence
        is_primary=candidate.primary_resume_id is None,  # First resume is primary by default
    )
    db.add(resume)
    db.flush()
    
    # Set as primary if it's the first upload
    if candidate.primary_resume_id is None:
        candidate.primary_resume_id = resume.id
    
    # Pre-populate candidate fields from resume if not already set
    if parsed_data.full_name and not candidate.full_name:
        candidate.full_name = parsed_data.full_name
    if parsed_data.email and not candidate.email:
        candidate.email = parsed_data.email
    if parsed_data.phone and not candidate.phone:
        candidate.phone = parsed_data.phone
    if parsed_data.years_experience and not candidate.years_experience:
        candidate.years_experience = parsed_data.years_experience
    
    db.commit()
    db.refresh(resume)
    
    return ResumeUploadResponse(
        id=resume.id,
        file_name=resume.file_name,
        file_size_bytes=resume.file_size_bytes,
        mime_type=resume.mime_type,
        s3_key=resume.s3_key,
        parsed_data=parsed_data,
        parser_used=resume.parser_used,
        parse_confidence=resume.parse_confidence,
        is_primary=resume.is_primary,
        created_at=resume.created_at,
    )


@router.get('/answer-library', response_model=list[AnswerLibraryQuestionResponse])
def get_answer_library(
    category: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[AnswerLibraryQuestionResponse]:
    """
    Get common ATS questions from answer library (M1.1 — Answer Library).
    
    Optional filters:
    - category: Filter by question category (e.g., 'work_auth', 'experience', 'culture')
    - limit: Maximum number of questions to return
    """
    query = db.query(AnswerLibraryQuestion).order_by(AnswerLibraryQuestion.frequency_rank)
    
    if category:
        query = query.filter(AnswerLibraryQuestion.question_category == category)
    
    query = query.limit(limit)
    questions = query.all()
    
    return [
        AnswerLibraryQuestionResponse(
            id=q.id,
            question_text=q.question_text,
            question_category=q.question_category,
            portal_types=q.portal_types,
            frequency_rank=q.frequency_rank,
        )
        for q in questions
    ]


@router.get('/candidates/{candidate_id}/answers', response_model=CandidateAnswersListResponse)
def get_candidate_answers(
    candidate_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> CandidateAnswersListResponse:
    """
    Get all candidate answers to library questions (M1.1 — Answer Library).
    """
    candidate = db.query(CandidateProfile).filter(CandidateProfile.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Candidate not found')
    
    answers = db.query(CandidateAnswer).filter(CandidateAnswer.candidate_id == candidate_id).limit(limit).all()
    
    library_question_ids = {a.library_question_id for a in answers}
    library_questions = db.query(AnswerLibraryQuestion).filter(AnswerLibraryQuestion.id.in_(library_question_ids)).all()
    
    return CandidateAnswersListResponse(
        answers=[
            CandidateAnswerResponse(
                id=a.id,
                library_question_id=a.library_question_id,
                answer_text=a.answer_text,
                is_custom=a.is_custom,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in answers
        ],
        total=len(answers),
        library_questions=[
            AnswerLibraryQuestionResponse(
                id=q.id,
                question_text=q.question_text,
                question_category=q.question_category,
                portal_types=q.portal_types,
                frequency_rank=q.frequency_rank,
            )
            for q in library_questions
        ],
    )


@router.post('/candidates/{candidate_id}/answers', response_model=CandidateAnswerResponse, status_code=status.HTTP_201_CREATED)
def create_candidate_answer(
    candidate_id: int,
    req: CandidateAnswerCreateRequest,
    db: Session = Depends(get_db),
) -> CandidateAnswerResponse:
    """
    Add or update a candidate's answer to a library question (M1.1 — Answer Library).
    """
    candidate = db.query(CandidateProfile).filter(CandidateProfile.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Candidate not found')
    
    question = db.query(AnswerLibraryQuestion).filter(AnswerLibraryQuestion.id == req.library_question_id).first()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Library question not found')
    
    # Check if answer already exists
    existing_answer = (
        db.query(CandidateAnswer)
        .filter(
            CandidateAnswer.candidate_id == candidate_id,
            CandidateAnswer.library_question_id == req.library_question_id,
        )
        .first()
    )
    
    if existing_answer:
        existing_answer.answer_text = req.answer_text
        existing_answer.is_custom = req.is_custom
        db.commit()
        db.refresh(existing_answer)
        return CandidateAnswerResponse(
            id=existing_answer.id,
            library_question_id=existing_answer.library_question_id,
            answer_text=existing_answer.answer_text,
            is_custom=existing_answer.is_custom,
            created_at=existing_answer.created_at,
            updated_at=existing_answer.updated_at,
        )
    
    # Create new answer
    answer = CandidateAnswer(
        candidate_id=candidate_id,
        library_question_id=req.library_question_id,
        answer_text=req.answer_text,
        is_custom=req.is_custom,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    
    return CandidateAnswerResponse(
        id=answer.id,
        library_question_id=answer.library_question_id,
        answer_text=answer.answer_text,
        is_custom=answer.is_custom,
        created_at=answer.created_at,
        updated_at=answer.updated_at,
    )

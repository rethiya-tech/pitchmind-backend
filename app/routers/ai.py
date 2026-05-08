from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.dependencies.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["ai"])


class QuestionRequest(BaseModel):
    prompt: str


class QuestionResponse(BaseModel):
    questions: list[str]


@router.post("/generate-questions", response_model=QuestionResponse)
async def generate_questions_endpoint(
    body: QuestionRequest,
    current_user: User = Depends(get_current_user),
):
    if len(body.prompt.strip()) < 20:
        raise HTTPException(
            status_code=422,
            detail={"code": "PROMPT_TOO_SHORT", "message": "Prompt must be at least 20 characters"},
        )
    from app.services.claude import generate_questions
    questions = await generate_questions(body.prompt.strip())
    return QuestionResponse(questions=questions)

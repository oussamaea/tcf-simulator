
from pydantic import BaseModel, Field, validator
from typing import List, Literal, Optional

class MCQQuestion(BaseModel):
    question: str
    options: List[str] = Field(min_items=4, max_items=4)
    correct_answer: str

    @validator("options")
    def options_must_be_text(cls, v):
        bad = {"A","B","C","D"}
        if any((isinstance(o,str) and o.strip().upper() in bad) or not isinstance(o, str) for o in v):
            raise ValueError("Options must be full text in French, not A/B/C/D or non-strings")
        return v

    @validator("correct_answer")
    def answer_must_match_option(cls, v, values):
        opts = values.get("options", [])
        if v not in opts:
            raise ValueError("correct_answer must be exactly one of options")
        return v

class MCQQuiz(BaseModel):
    passage: Optional[str] = None
    script: Optional[str] = None
    questions: List[MCQQuestion]

class WritingRubric(BaseModel):
    criteria: list
    descriptors: str

class WritingTask(BaseModel):
    instructions: str
    rubric: dict
    template_md: str

class SpeakingTask(BaseModel):
    prompts: List[str]
    rubric: dict


import os, time
from dotenv import load_dotenv
from openai import OpenAI
from .logger import log, log_exception

load_dotenv()
_client = None

def get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.getenv("OPENAI_API_KEY")
        _client = OpenAI(api_key=key)
    return _client

def get_models():
    gen = os.getenv("OPENAI_MODEL_GENERATION", "gpt-4o-mini")
    grade = os.getenv("OPENAI_MODEL_GRADING", "gpt-4o")
    stt = os.getenv("OPENAI_MODEL_TRANSCRIBE", "gpt-4o-transcribe")
    return gen, grade, stt


import json
from .gen_utils import chat_json
from .prompts import SYSTEM_TEST_GEN, WRITING_TEMPLATE_MD
from .schemas import MCQQuiz, WritingTask, SpeakingTask
from .offline_bank import BANK

def _validated_load(content: str, model):
    data = json.loads(content)
    return model.model_validate(data)

def generate_mcq_quiz(level="B2", n_questions=10):
    user = f"""Crée un quiz **Grammaire & Lexique** en français (niveau {level}), {n_questions} QCM à 4 choix.
Retour JSON : {{"questions":[{{"question":"","options":["","","",""],"correct_answer":""}}]}}.
Couvre : temps (PC/imparfait/plus-que-parfait), conditionnel, subjonctif (il faut que…), pronoms (y, en, le/la/les, lui/leur), connecteurs."""
    for _ in range(3):
        content = chat_json(SYSTEM_TEST_GEN, user)
        try:
            quiz = _validated_load(content, MCQQuiz)
            return quiz.model_dump()
        except Exception:
            user += "\nIMPORTANT : Les options doivent être des propositions complètes en français (pas uniquement A/B/C/D)."
            continue
    # fallback
    return {"questions": BANK["grammar_mcq"][:n_questions]}

def generate_reading_quiz(level="B2", n_questions=8):
    user = f"""Crée un texte **original en français** (~180–250 mots) niveau {level} + {n_questions} QCM à 4 choix.
Retour JSON: {{
 "passage": "...",
 "questions":[{{"question":"...","options":["A","B","C","D"],"correct_answer":"A"}}]
}}"""
    for _ in range(3):
        content = chat_json(SYSTEM_TEST_GEN, user)
        try:
            quiz = _validated_load(content, MCQQuiz)
            if not quiz.passage:
                raise ValueError("passage manquant")
            return quiz.model_dump()
        except Exception:
            user += "\nIMPORTANT : Les options doivent être des propositions complètes en français (pas uniquement A/B/C/D) et le passage doit être présent."
            continue
    # fallback
    return {"passage": BANK["reading_passage"], "questions": BANK["reading_questions"][:n_questions]}

def generate_listening_quiz(level="B2", n_questions=6):
    user = f"""Rédige un **mini-script audio en français** (~120–180 mots) niveau {level} + {n_questions} QCM à 4 choix.
JSON : {{"script":"...", "questions":[{{"question":"...","options":["","","",""],"correct_answer":""}}]}}"""
    for _ in range(3):
        content = chat_json(SYSTEM_TEST_GEN, user)
        try:
            quiz = _validated_load(content, MCQQuiz)
            if not quiz.script:
                raise ValueError("script manquant")
            return quiz.model_dump()
        except Exception:
            user += "\nIMPORTANT : Les options doivent être des propositions complètes en français (pas uniquement A/B/C/D) et le script doit être présent."
            continue
    # fallback
    return {"script": BANK["listening_script"], "questions": BANK["listening_questions"][:n_questions]}

def generate_writing_task(level="B2"):
    user = f"""Crée une **tâche d’expression écrite en français** (B2, 200–250 mots attendus).
Retourne JSON avec : "instructions" (FR), "rubric" (FR, critères Contenu, Cohérence, Étendue, Exactitude, chacun 0–5), "template_md" (FR)."""
    content = chat_json(SYSTEM_TEST_GEN, user)
    try:
        task = _validated_load(content, WritingTask)
        return task.model_dump()
    except Exception:
        return {"instructions":"Rédigez un essai d’opinion sur l’usage du numérique dans les services publics (200–250 mots).",
                "rubric":{"criteria":["Contenu","Cohérence","Étendue","Exactitude"],"descriptors":"B2 : idées claires, organisation logique, variété lexicale et syntaxique, erreurs non bloquantes."},
                "template_md": WRITING_TEMPLATE_MD}

def generate_speaking_task(level="B2"):
    user = f"""Crée **3 invites d’expression orale en français** (B2) : mise en route, interaction, opinion.
Ajoute une "rubric" FR : Fluence, Étendue, Exactitude, Interaction (0–5). JSON : prompts[], rubric{{criteria[], descriptors}}."""
    content = chat_json(SYSTEM_TEST_GEN, user)
    try:
        task = _validated_load(content, SpeakingTask)
        return task.model_dump()
    except Exception:
        return {"prompts":[
                    "Parlez d’une habitude quotidienne qui vous aide à rester organisé(e).",
                    "Vous partagez un appartement : discutez d’un nouveau règlement pour réduire le bruit.",
                    "Êtes-vous pour ou contre le télétravail généralisé ? Justifiez votre opinion."],
                "rubric":{"criteria":["Fluence","Étendue","Exactitude","Interaction"],"descriptors":"B2 : discours relativement spontané, connecteurs variés, erreurs tolérées si sens clair."}}

def generate_full_mock(level="B2"):
    return {
        "reading": generate_reading_quiz(level=level, n_questions=8),
        "listening": generate_listening_quiz(level=level, n_questions=6),
        "writing": generate_writing_task(level=level),
        "speaking": generate_speaking_task(level=level),
    }

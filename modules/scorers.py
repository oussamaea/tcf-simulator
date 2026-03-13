
import json, time
from typing import Dict, Any
from .openai_client import get_client, get_models
from .tcf_levels import TCF_TO_NCLC_TABLE

def grade_mcq(quiz: Dict[str,Any], answers: Dict[str,str]):
    correct = 0
    total = len(quiz["questions"])
    details = []
    for idx, q in enumerate(quiz["questions"], start=1):
        user = answers.get(str(idx))
        gold = q["correct_answer"]
        ok = (user == gold)
        if ok: correct += 1
        details.append({"q": idx, "your": user, "correct": gold, "ok": ok})
    percent = round(100*correct/max(total,1))
    return {"correct": correct, "total": total, "percent": percent, "details": details}

def estimate_nclc_from_percent(percent: int):
    if percent >= 85: return 9
    if percent >= 75: return 8
    if percent >= 65: return 7
    if percent >= 55: return 6
    if percent >= 45: return 5
    return 4

def nclc_lookup_from_tcf(module: str, tcf_value: int|float):
    ranges = TCF_TO_NCLC_TABLE[module]
    for lo, hi, nclc in ranges:
        if lo <= tcf_value <= hi:
            return nclc
    return None

def predict_module_band(module: str, nclc: int):
    if nclc >= 9: return "C1–C2"
    if nclc >= 7: return "B2"
    if nclc >= 5: return "B1"
    return "A2 ou moins"

def _chat_grade(system, user, response_format="json_object"):
    client = get_client()
    _, grade_model, _ = get_models()
    delays = [0, 4, 8, 12, 16]
    last_err = None
    for d in delays:
        if d:
            time.sleep(d)
        try:
            resp = client.chat.completions.create(
                model=grade_model,
                response_format={"type": response_format},
                messages=[
                    {"role":"system","content": system},
                    {"role":"user","content": user}
                ]
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "rate limit" in msg or "429" in msg or "timeout" in msg:
                continue
            else:
                break
    raise last_err

def grade_writing(text: str, rubric: dict):
    if not text or len(text.strip()) < 50:
        return {"predicted_nclc": 4, "band":"A2/B1", "feedback":"Rédigez davantage (≥ 120 mots) pour une évaluation fiable."}
    user = f"""Rubrique:\n{json.dumps(rubric, ensure_ascii=False)}\n\nTexte du candidat :\n{text}\n\nRetour JSON : {{
 "scores": {{"Contenu":0-5,"Cohérence":0-5,"Étendue":0-5,"Exactitude":0-5}},
 "strengths": ["..."],
 "improvements": ["..."],
 "predicted_nclc": 4-10,
 "band": "A2/B1/B2/C1"
}}"""
    system = "Tu es examinateur·trice TCF Canada pour l’écrit. Sois strict·e mais juste; feedback concret en français."
    content = _chat_grade(system, user)
    data = json.loads(content)
    n = int(data.get("predicted_nclc", 7))
    data["predicted_nclc"] = max(4, min(10, n))
    if "band" not in data:
        data["band"] = "B2" if n >= 7 else ("B1" if n >=5 else "A2/B1")
    data["feedback"] = "✅ " + " | ".join(data.get("strengths", [])) + "\n\n🔧 " + " | ".join(data.get("improvements", []))
    return data

def grade_speaking(transcript: str, rubric: dict, *, raw_audio_path: str|None=None):
    if not transcript or len(transcript.strip()) < 30:
        return {"predicted_nclc": 4, "band":"A2/B1", "feedback":"Parlez plus longtemps et structurez votre réponse (début→développement→conclusion)."}
    user = f"""Rubrique:\n{json.dumps(rubric, ensure_ascii=False)}\n\nTranscription du candidat :\n{transcript}\n\nRetour JSON : {{
 "scores": {{"Fluence":0-5,"Étendue":0-5,"Exactitude":0-5,"Interaction":0-5}},
 "strengths": ["..."],
 "improvements": ["..."],
 "predicted_nclc": 4-10,
 "band": "A2/B1/B2/C1"
}}"""
    system = "Tu es examinateur·trice TCF Canada pour l’oral. Sois strict·e mais pratique; feedback clair en français."
    content = _chat_grade(system, user)
    data = json.loads(content)
    n = int(data.get("predicted_nclc", 7))
    data["predicted_nclc"] = max(4, min(10, n))
    if "band" not in data:
        data["band"] = "B2" if n >= 7 else ("B1" if n >=5 else "A2/B1")
    data["feedback"] = "🎙️ " + " | ".join(data.get("strengths", [])) + "\n\n🔧 " + " | ".join(data.get("improvements", []))
    return data

def transcribe_audio_and_grade_speaking(uploaded_file, rubric: dict):
    import tempfile
    suffix = "." + uploaded_file.name.split(".")[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    from .openai_client import get_client, get_models
    client = get_client()
    *_ , stt_model = get_models()
    transcript_text = ""
    try:
        model_name = stt_model or "whisper-1"
        tr = client.audio.transcriptions.create(model=model_name, file=open(tmp_path, "rb"))
        transcript_text = tr.text
    except Exception:
        try:
            tr = client.audio.transcriptions.create(model="whisper-1", file=open(tmp_path, "rb"))
            transcript_text = tr.text
        except Exception:
            transcript_text = ""

    return grade_speaking(transcript_text, rubric, raw_audio_path=tmp_path) | {"transcript": transcript_text}


import os, json, time
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st

from modules.openai_client import get_client, get_models
from modules.storage import load_history, save_history, new_session_record
from modules.prompts import SYSTEM_TEST_GEN, SYSTEM_GRADER, WRITING_TEMPLATE_MD
from modules.test_generators import (
    generate_mcq_quiz, generate_reading_quiz, generate_listening_quiz,
    generate_writing_task, generate_speaking_task, generate_full_mock
)
from modules.scorers import (
    grade_mcq, grade_writing, grade_speaking, estimate_nclc_from_percent,
    nclc_lookup_from_tcf, predict_module_band, transcribe_audio_and_grade_speaking
)
from modules.tcf_levels import TCF_TO_NCLC_TABLE, CEFR_BANDS_NOTE
from modules.srs import add_card, get_due_cards, review_card, all_cards
from modules.shortcuts_fr import CONNECTEURS, FILLERS, TOUR_DE_PAROLE

load_dotenv()
st.set_page_config(page_title="TCF Canada B2 Coach — Pro", page_icon="🇨🇦", layout="wide")

# Sidebar controls
st.sidebar.title("🇨🇦 TCF Canada B2 Coach — Pro")

# API key
st.sidebar.markdown("**Clé OpenAI (API)**")
api_key_input = st.sidebar.text_input("sk-… (local)", type="password")
if api_key_input:
    os.environ["OPENAI_API_KEY"] = api_key_input.strip()
    try:
        (Path("data")/".key").write_text(api_key_input.strip(), encoding="utf-8")
    except Exception:
        pass
    st.sidebar.success("Clé définie pour cette session.")
else:
    try:
        cached = (Path("data")/".key").read_text(encoding="utf-8").strip()
        if cached and "OPENAI_API_KEY" not in os.environ:
            os.environ["OPENAI_API_KEY"] = cached
            st.sidebar.caption("Clé chargée depuis data/.key")
    except Exception:
        pass

username = st.sidebar.text_input("Votre nom (optionnel)", value="Oussama")
target = st.sidebar.selectbox("Niveau visé", ["B1", "B2", "C1"], index=1)

gen_model, grade_model, stt_model = get_models()
st.sidebar.caption(f"Modèles → génération: `{gen_model}`, notation: `{grade_model}`, STT: `{stt_model or 'whisper-1'}`")

st.sidebar.markdown("**Mode chrono (mocks)**")
timer_minutes = st.sidebar.slider("Durée par épreuve (min)", 5, 40, 20)

tabs = st.tabs([
    "Tableau de bord",
    "Semaine 1: Diagnostic",
    "Grammaire & Lexique",
    "Lecture",
    "Écoute",
    "Écrit",
    "Oral",
    "Vocabulaire (SRS)",
    "Mock (sem.4–5)",
    "À propos"
])

history = load_history()

# Dashboard
with tabs[0]:
    st.header("Progression (aperçu)")
    if not history:
        st.info("Pas encore d’historique. Lancez un quiz pour commencer.")
    else:
        # Simple aggregation
        r = [h for h in history if h["type"] in ("reading","listening","writing","speaking","full_mock")]
        st.line_chart([h.get("predicted_nclc", 0) for h in r], height=200)
        st.caption("Courbe des NCLC prédits (ordre chronologique).")
        st.json(history[-5:])

# Diagnostic
with tabs[1]:
    st.header("Semaine 1 – Diagnostic (A2 → C1)")
    colA, colB = st.columns(2)
    with colA:
        if st.button("Générer diagnostic (Lecture + Grammaire)"):
            quiz = generate_reading_quiz(level=target, n_questions=8)
            st.session_state["diag_reading"] = quiz
        if "diag_reading" in st.session_state:
            st.subheader("Passage")
            st.write(st.session_state["diag_reading"].get("passage","(pas de passage — utilisez lecture)"))
            st.subheader("Questions")
            answers = {}
            for i, q in enumerate(st.session_state["diag_reading"]["questions"], start=1):
                st.markdown(f"**Q{i}.** {q['question']}")
                choice = st.radio("Choix :", q["options"], key=f"diag_r_{i}")
                answers[str(i)] = choice
                st.markdown("---")
            if st.button("Corriger la lecture/grammaire"):
                res = grade_mcq(st.session_state["diag_reading"], answers)
                st.success(f"Score: {res['percent']}% • {res['correct']}/{res['total']}")
                nclc = estimate_nclc_from_percent(res["percent"])
                st.write("NCLC estimé:", nclc)
                st.session_state["diag_r_result"] = res
    with colB:
        if st.button("Générer diagnostic (Écrit)"):
            st.session_state["diag_writing"] = generate_writing_task(level=target)
        if "diag_writing" in st.session_state:
            st.subheader("Écrit")
            st.caption(st.session_state["diag_writing"]["instructions"])
            text = st.text_area("Rédigez ici (10–15 min)", height=220, key="diag_w_text")
            if st.button("Évaluer l’écrit"):
                rub = st.session_state["diag_writing"]["rubric"]
                res = grade_writing(text, rub)
                st.success(f"NCLC prédit (écrit): {res['predicted_nclc']} • Bande: {res['band']}")
                st.write(res["feedback"])
                st.session_state["diag_w_result"] = res

# Grammaire & Lexique
with tabs[2]:
    st.header("Grammaire & Lexique (B1–B2)")
    n_q = st.slider("Nombre de questions", 5, 20, 10)
    if st.button("Générer quiz"):
        st.session_state["gram_quiz"] = generate_mcq_quiz(level=target, n_questions=n_q)
    if "gram_quiz" in st.session_state:
        answers = {}
        for i, q in enumerate(st.session_state["gram_quiz"]["questions"], start=1):
            st.markdown(f"**Q{i}.** {q['question']}")
            choice = st.radio("Choix :", q["options"], key=f"g_{i}")
            answers[str(i)] = choice
            st.markdown("---")
        if st.button("Corriger le quiz"):
            res = grade_mcq(st.session_state["gram_quiz"], answers)
            st.success(f"Score: {res['percent']}% • {res['correct']}/{res['total']}")
            st.write("NCLC estimé:", estimate_nclc_from_percent(res["percent"]))

# Lecture
with tabs[3]:
    st.header("Compréhension écrite (Lecture)")
    n_q = st.slider("Questions", 5, 15, 8, key="read_nq")
    if st.button("Générer un set de lecture"):
        st.session_state["reading"] = generate_reading_quiz(level=target, n_questions=n_q)
    if "reading" in st.session_state:
        st.subheader("Passage")
        st.write(st.session_state["reading"]["passage"])
        st.subheader("Questions")
        answers = {}
        for i, q in enumerate(st.session_state["reading"]["questions"], start=1):
            st.markdown(f"**Q{i}.** {q['question']}")
            choice = st.radio("Choix :", q["options"], key=f"r_{i}")
            answers[str(i)] = choice
            st.markdown("---")
        if st.button("Corriger la lecture"):
            res = grade_mcq(st.session_state["reading"], answers)
            nclc = estimate_nclc_from_percent(res["percent"])
            band = predict_module_band("reading", nclc)
            st.success(f"Score: {res['percent']}% • {res['correct']}/{res['total']} • NCLC: {nclc} ({band})")
            new_session_record("reading", res, nclc, band)

# Écoute
with tabs[4]:
    st.header("Compréhension orale (Écoute)")
    n_q = st.slider("Questions", 4, 10, 6, key="listen_nq")
    if st.button("Générer mini-script + QCM"):
        st.session_state["listening"] = generate_listening_quiz(level=target, n_questions=n_q)
    if "listening" in st.session_state:
        st.subheader("Script (à lire à voix haute ou via TTS externe)")
        st.write(st.session_state["listening"]["script"])
        st.subheader("Questions")
        answers = {}
        for i, q in enumerate(st.session_state["listening"]["questions"], start=1):
            st.markdown(f"**Q{i}.** {q['question']}")
            choice = st.radio("Choix :", q["options"], key=f"l_{i}")
            answers[str(i)] = choice
            st.markdown("---")
        if st.button("Corriger l’écoute"):
            res = grade_mcq(st.session_state["listening"], answers)
            nclc = estimate_nclc_from_percent(res["percent"])
            band = predict_module_band("listening", nclc)
            st.success(f"Score: {res['percent']}% • NCLC: {nclc} ({band})")
            new_session_record("listening", res, nclc, band)

# Écrit
with tabs[5]:
    st.header("Expression écrite (B2)")
    if st.button("Nouvelle tâche d’écrit"):
        st.session_state["writing_task"] = generate_writing_task(level=target)
    if "writing_task" in st.session_state:
        task = st.session_state["writing_task"]
        st.subheader("Consigne")
        st.write(task["instructions"])
        st.write("**Modèle B2 :**")
        st.markdown(task["template_md"])
        user_text = st.text_area("Votre production (20–30 min)", height=280)
        if st.button("Évaluer l’écrit"):
            res = grade_writing(user_text, task["rubric"])
            st.success(f"NCLC prédit: {res['predicted_nclc']} • Bande: {res['band']}")
            st.write(res["feedback"])
            new_session_record("writing", res, res["predicted_nclc"], res["band"])
        with st.expander("Banque de connecteurs (à utiliser)", expanded=False):
            st.write(", ".join(CONNECTEURS))

# Oral
with tabs[6]:
    st.header("Expression orale (B2)")
    if st.button("Nouvelles invites d’oral"):
        st.session_state["speaking"] = generate_speaking_task(level=target)
    if "speaking" in st.session_state:
        st.subheader("Invites")
        for p in st.session_state["speaking"]["prompts"]:
            st.markdown(f"- {p}")
        st.caption("Enregistrez sur votre téléphone puis importez ci-dessous.")
        audio = st.file_uploader("Audio (mp3/wav/m4a)", type=["mp3","wav","m4a"])
        if st.button("Évaluer l’oral (transcription + notation)"):
            if audio is None:
                st.error("Importez un fichier audio.")
            else:
                res = transcribe_audio_and_grade_speaking(audio, st.session_state["speaking"]["rubric"])
                st.success(f"NCLC prédit: {res['predicted_nclc']} • Bande: {res['band']}")
                st.write("Transcription :")
                st.write(res.get("transcript","(transcription indisponible)"))
                st.write(res["feedback"])
                new_session_record("speaking", res, res["predicted_nclc"], res["band"])
        with st.expander("Connecteurs & remplisseurs utiles"):
            st.write(", ".join(CONNECTEURS + FILLERS + TOUR_DE_PAROLE))

# Vocab SRS
with tabs[7]:
    st.header("Vocabulaire — Révisions espacées (SRS)")
    st.subheader("Ajouter une carte")
    with st.form("add_card"):
        front = st.text_input("Mot / expression (FR)")
        back = st.text_input("Définition / exemple (FR)")
        ok = st.form_submit_button("Ajouter")
        if ok and front and back:
            add_card(front, back)
            st.success("Carte ajoutée.")

    st.subheader("Réviser (cartes dues)")
    due = get_due_cards(limit=20)
    if not due:
        st.info("Aucune carte due pour le moment.")
    else:
        for c in due:
            st.markdown(f"**{c['front']}**")
            if st.button(f"Afficher la réponse #{c['id']}"):
                st.write(c["back"])
            col1, col2 = st.columns(2)
            if col1.button(f"J’ai bien su #{c['id']}"):
                review_card(c["id"], True)
                st.success("Bien ! Prochaine révision planifiée.")
            if col2.button(f"À revoir #{c['id']}"):
                review_card(c["id"], False)
                st.warning("Pas grave — on revoit plus tôt.")

    st.subheader("Toutes les cartes")
    st.json(all_cards())

# Mock
with tabs[8]:
    st.header("Mini-mock (semaines 4–5) — Mode chrono")
    if st.button("Générer le mock"):
        st.session_state["full_mock"] = generate_full_mock(level=target)
        st.session_state["end_time"] = time.time() + timer_minutes*60
        st.success("Mock prêt : répondez avant la fin du chrono !")
    if "full_mock" in st.session_state:
        remaining = int(max(0, st.session_state["end_time"] - time.time()))
        st.info(f"Temps restant : {remaining//60:02d}:{remaining%60:02d}")
        fm = st.session_state["full_mock"]
        st.subheader("Lecture")
        st.write(fm["reading"]["passage"])
        ans_r = {}
        for i,q in enumerate(fm["reading"]["questions"], start=1):
            ans_r[str(i)] = st.radio(f"R{i}. {q['question']}", q["options"], key=f"fm_r_{i}")
        st.subheader("Écoute")
        st.write(fm["listening"]["script"])
        ans_l = {}
        for i,q in enumerate(fm["listening"]["questions"], start=1):
            ans_l[str(i)] = st.radio(f"L{i}. {q['question']}", q["options"], key=f"fm_l_{i}")
        st.subheader("Écrit")
        w_text = st.text_area("Rédaction (~20 min)", height=220, key="fm_w")
        st.subheader("Oral")
        for p in fm["speaking"]["prompts"]:
            st.markdown(f"- {p}")
        sp_audio = st.file_uploader("Audio pour l’oral (mock)", type=["mp3","wav","m4a"], key="fm_audio")
        if st.button("Évaluer le mock"):
            r_res = grade_mcq(fm["reading"], ans_r)
            l_res = grade_mcq(fm["listening"], ans_l)
            w_res = grade_writing(w_text, fm["writing"]["rubric"])
            if sp_audio is not None:
                s_res = transcribe_audio_and_grade_speaking(sp_audio, fm["speaking"]["rubric"])
            else:
                s_res = grade_speaking("", fm["speaking"]["rubric"], transcript="")
            r_nclc = estimate_nclc_from_percent(r_res["percent"]); r_band = predict_module_band("reading", r_nclc)
            l_nclc = estimate_nclc_from_percent(l_res["percent"]); l_band = predict_module_band("listening", l_nclc)
            w_nclc = w_res["predicted_nclc"]; w_band = w_res["band"]
            s_nclc = s_res["predicted_nclc"]; s_band = s_res["band"]
            st.success(f"Lecture: NCLC {r_nclc} ({r_band}) • Écoute: NCLC {l_nclc} ({l_band}) • Écrit: NCLC {w_nclc} ({w_band}) • Oral: NCLC {s_nclc} ({s_band})")

# About
with tabs[9]:
    st.header("À propos")
    st.markdown("Entraînement **TCF Canada** (FR uniquement) avec prédictions **NCLC**. Les résultats ne sont pas officiels.")

from pathlib import Path
import time

import pandas as pd
import streamlit as st

st.set_page_config(page_title="TCF Simulator", page_icon="📘", layout="wide")

BASE_DIR = Path(__file__).resolve().parent
WRITTEN_CSV = Path("tcf_full_output/tcf_all_series.csv")
ORAL_CSV = Path("tcf_oral_output/tcf_all_series_oral.csv")


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)

    for col in ["series_index", "question_number", "points"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].fillna("").astype(str)

    if "series_index" in df.columns and "question_number" in df.columns:
        df = df.sort_values(["series_index", "question_number"]).reset_index(drop=True)

    return df


def normalize_media_path(path_value: str) -> str | None:
    if not path_value:
        return None

    p = Path(path_value)
    if p.is_file():
        return str(p)

    p2 = BASE_DIR / path_value
    if p2.is_file():
        return str(p2)

    return None


def get_df(section: str) -> pd.DataFrame:
    return load_csv(WRITTEN_CSV) if section == "Compréhension écrite" else load_csv(ORAL_CSV)


def get_duration_minutes(section: str) -> int:
    return 60 if section == "Compréhension écrite" else 30


def exam_key(section: str, series_index: int) -> str:
    return f"{section}__series_{series_index}"


def ensure_exam_state(section: str, series_index: int):
    if "exam_states" not in st.session_state:
        st.session_state.exam_states = {}

    key = exam_key(section, series_index)
    if key not in st.session_state.exam_states:
        st.session_state.exam_states[key] = {
            "answers": {},
            "started_at": None,
            "finished": False,
            "show_review": False,
        }


def get_exam_state(section: str, series_index: int) -> dict:
    ensure_exam_state(section, series_index)
    return st.session_state.exam_states[exam_key(section, series_index)]


def reset_exam_state(section: str, series_index: int):
    st.session_state.exam_states[exam_key(section, series_index)] = {
        "answers": {},
        "started_at": None,
        "finished": False,
        "show_review": False,
    }


def init_ui_state(df: pd.DataFrame):
    if df.empty:
        return

    series_ids = sorted(df["series_index"].unique().tolist())

    if "series_index" not in st.session_state or st.session_state.series_index not in series_ids:
        st.session_state.series_index = series_ids[0]

    series_df = df[df["series_index"] == st.session_state.series_index]
    qnums = series_df["question_number"].tolist()

    if "question_number" not in st.session_state or st.session_state.question_number not in qnums:
        st.session_state.question_number = qnums[0]

    if "show_answer" not in st.session_state:
        st.session_state.show_answer = False


def set_series(df: pd.DataFrame, series_index: int):
    st.session_state.series_index = series_index
    series_df = df[df["series_index"] == series_index]
    st.session_state.question_number = int(series_df["question_number"].min())
    st.session_state.show_answer = False


def set_question(question_number: int):
    st.session_state.question_number = question_number
    st.session_state.show_answer = False


def nav_question(series_df: pd.DataFrame, step: int):
    qnums = series_df["question_number"].tolist()
    current = st.session_state.question_number
    idx = qnums.index(current)
    new_idx = max(0, min(len(qnums) - 1, idx + step))
    st.session_state.question_number = qnums[new_idx]
    st.session_state.show_answer = False


def calculate_results(series_df: pd.DataFrame, answers: dict) -> dict:
    total_questions = len(series_df)
    total_points = int(series_df["points"].sum()) if "points" in series_df.columns else 0

    correct_questions = 0
    answered_questions = 0
    earned_points = 0
    rows = []

    for _, row in series_df.iterrows():
        qn = int(row["question_number"])
        pts = int(row.get("points", 0))
        correct_letter = str(row.get("correct_letter", "")).strip()
        user_answer = str(answers.get(qn, "")).strip()

        if user_answer:
            answered_questions += 1

        is_correct = user_answer == correct_letter
        if is_correct:
            correct_questions += 1
            earned_points += pts

        rows.append({
            "Question": qn,
            "Points": pts,
            "Your answer": user_answer,
            "Correct answer": correct_letter,
            "Earned points": pts if is_correct else 0,
            "Result": "✅" if is_correct else ("—" if not user_answer else "❌"),
        })

    return {
        "total_questions": total_questions,
        "answered_questions": answered_questions,
        "correct_questions": correct_questions,
        "total_points": total_points,
        "earned_points": earned_points,
        "point_percentage": (earned_points / total_points * 100) if total_points else 0,
        "question_percentage": (correct_questions / total_questions * 100) if total_questions else 0,
        "review_df": pd.DataFrame(rows),
    }


# ---------------- APP ----------------
st.title("📘 TCF Simulator")

section = st.sidebar.selectbox(
    "Section",
    ["Compréhension écrite", "Compréhension orale"]
)

mode = st.sidebar.selectbox(
    "Mode",
    ["Practice", "Exam"]
)

df = get_df(section)
if df.empty:
    st.error(f"No dataset found for {section}.")
    st.stop()

init_ui_state(df)

series_ids = sorted(df["series_index"].unique().tolist())
series_titles = {
    s: (
        df[df["series_index"] == s]["series_title"].iloc[0]
        if "series_title" in df.columns
        else f"Série {s}"
    )
    for s in series_ids
}

with st.sidebar:
    chosen_series = st.selectbox(
        "Choose a series",
        options=series_ids,
        index=series_ids.index(st.session_state.series_index),
        format_func=lambda x: series_titles.get(x, f"Série {x}")
    )
    if chosen_series != st.session_state.series_index:
        set_series(df, chosen_series)
        st.rerun()

series_df = df[df["series_index"] == st.session_state.series_index].copy()
qnums = series_df["question_number"].tolist()
current_row = series_df[series_df["question_number"] == st.session_state.question_number].iloc[0]

exam_state = get_exam_state(section, st.session_state.series_index)

# Sidebar question navigation
with st.sidebar:
    st.markdown("---")
    st.subheader("Questions")

    cols = st.columns(4)
    for i, q in enumerate(qnums):
        col = cols[i % 4]
        answered = int(q) in exam_state["answers"] and exam_state["answers"][int(q)] != ""
        label = f"{q}✓" if answered and mode == "Exam" else str(q)
        if col.button(label, use_container_width=True, key=f"{section}_{mode}_{q}"):
            set_question(int(q))
            st.rerun()

# Header
left, right = st.columns([3, 1])
with left:
    st.subheader(series_titles[st.session_state.series_index])
    st.caption(
        f"{section} • {mode} mode • "
        f"Question {current_row['question_number']} • "
        f"Niveau {current_row.get('level', '')} • "
        f"{current_row.get('points', 0)} points"
    )

with right:
    st.metric("Questions", len(series_df))

# Exam controls
if mode == "Exam":
    duration_minutes = get_duration_minutes(section)

    if exam_state["started_at"] is None:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Start exam", type="primary", use_container_width=True):
                reset_exam_state(section, st.session_state.series_index)
                exam_state = get_exam_state(section, st.session_state.series_index)
                exam_state["started_at"] = time.time()
                st.rerun()
        with c2:
            st.info(f"Timer: {duration_minutes} min")
        st.stop()

    elapsed = int(time.time() - exam_state["started_at"])
    remaining = max(0, duration_minutes * 60 - elapsed)
    mins = remaining // 60
    secs = remaining % 60

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"## ⏳ {mins:02d}:{secs:02d}")

    if remaining == 0 and not exam_state["finished"]:
        exam_state["finished"] = True
        exam_state["show_review"] = True

    st.caption(f"Time remaining: **{mins:02d}:{secs:02d}**")
    st.info("Timer updates when you click anything in the app.")

st.markdown("---")

# Main content
media_col, choice_col = st.columns([1.25, 1])

with media_col:
    st.subheader("Question")

    if section == "Compréhension écrite":
        img_path = normalize_media_path(current_row.get("local_image_path", ""))
        if img_path:
            st.image(img_path, use_container_width=True)
        elif current_row.get("image_url", ""):
            st.image(current_row["image_url"], use_container_width=True)
        else:
            st.warning("No image found.")
    else:
        prompt = str(current_row.get("prompt", "")).strip()
        if prompt:
            st.markdown(f"**{prompt}**")

        oral_img_path = normalize_media_path(current_row.get("image_local_path", ""))
        if oral_img_path:
            st.image(oral_img_path, use_container_width=True)
        elif current_row.get("image_url", ""):
            st.image(current_row["image_url"], use_container_width=True)

        audio_path = normalize_media_path(current_row.get("audio_local_path", ""))
        if audio_path:
            with open(audio_path, "rb") as f:
                st.audio(f.read())
        elif current_row.get("audio_url", ""):
            st.audio(current_row["audio_url"])
        else:
            st.warning("No audio found.")

with choice_col:
    st.subheader("Choices")

    correct_letter = str(current_row.get("correct_letter", "")).strip()
    correct_text = str(current_row.get("correct_answer_text", "")).strip()
    qn = int(current_row["question_number"])
    question_points = int(current_row.get("points", 0))

    if mode == "Practice":
        for letter in ["A", "B", "C", "D"]:
            value = str(current_row.get(letter, ""))
            if st.session_state.show_answer and letter == correct_letter:
                st.success(f"{letter}. {value}")
            else:
                st.info(f"{letter}. {value}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Show correction", use_container_width=True):
                st.session_state.show_answer = True
                st.rerun()
        with c2:
            if st.button("Hide correction", use_container_width=True):
                st.session_state.show_answer = False
                st.rerun()

        if st.session_state.show_answer:
            st.markdown("### Correction")
            st.write(f"**Correct answer:** {correct_letter}")
            st.write(f"**Text:** {correct_text}")
            st.write(f"**Points:** {question_points}")

    else:
        options = ["A", "B", "C", "D"]
        current_saved = exam_state["answers"].get(qn, "")

        selected = st.radio(
            "Select your answer",
            options,
            index=options.index(current_saved) if current_saved in options else 0,
            key=f"radio_{section}_{st.session_state.series_index}_{qn}"
        )

        exam_state["answers"][qn] = selected

        for letter in ["A", "B", "C", "D"]:
            value = str(current_row.get(letter, ""))
            if exam_state["finished"] and exam_state["show_review"] and letter == correct_letter:
                st.success(f"{letter}. {value}")
            else:
                st.info(f"{letter}. {value}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Finish exam", type="primary", use_container_width=True):
                exam_state["finished"] = True
                exam_state["show_review"] = True
                st.rerun()
        with c2:
            if st.button("Reset exam", use_container_width=True):
                reset_exam_state(section, st.session_state.series_index)
                st.rerun()

        if exam_state["finished"] and exam_state["show_review"]:
            st.markdown("### Correction")
            st.write(f"**Correct answer:** {correct_letter}")
            st.write(f"**Text:** {correct_text}")
            st.write(f"**Points for this question:** {question_points}")

st.markdown("---")

# Navigation
n1, n2, n3 = st.columns([1, 2, 1])

with n1:
    if st.button("⬅ Previous", use_container_width=True):
        nav_question(series_df, -1)
        st.rerun()

with n2:
    current_idx = qnums.index(st.session_state.question_number) + 1
    progress = int((current_idx / len(qnums)) * 100)
    st.progress(progress)
    st.caption(f"{current_idx} / {len(qnums)}")

with n3:
    if st.button("Next ➡", use_container_width=True):
        nav_question(series_df, 1)
        st.rerun()

# Result panel
if mode == "Exam" and exam_state["finished"]:
    st.markdown("---")
    st.subheader("Exam result")

    results = calculate_results(series_df, exam_state["answers"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Correct questions", f"{results['correct_questions']}/{results['total_questions']}")
    c2.metric("Answered", results["answered_questions"])
    c3.metric("Points", f"{results['earned_points']}/{results['total_points']}")
    c4.metric("Score", f"{results['point_percentage']:.1f}%")

    st.caption(
        f"Question accuracy: {results['question_percentage']:.1f}% • "
        f"Point score: {results['point_percentage']:.1f}%"
    )

    with st.expander("Review all answers", expanded=False):
        st.dataframe(results["review_df"], use_container_width=True)
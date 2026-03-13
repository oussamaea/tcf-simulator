import os
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="TCF Simulator",
    page_icon="📘",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "tcf_full_output" / "tcf_all_series.csv"


@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)

    # Clean numeric columns
    if "series_index" in df.columns:
        df["series_index"] = pd.to_numeric(df["series_index"], errors="coerce").fillna(0).astype(int)
    if "question_number" in df.columns:
        df["question_number"] = pd.to_numeric(df["question_number"], errors="coerce").fillna(0).astype(int)
    if "points" in df.columns:
        df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0).astype(int)

    # Normalize strings
    for col in [
        "series_title",
        "level",
        "image_url",
        "local_image_path",
        "A",
        "B",
        "C",
        "D",
        "correct_answer_text",
        "correct_letter",
    ]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    df = df.sort_values(["series_index", "question_number"]).reset_index(drop=True)
    return df


def resolve_image_path(path_value: str) -> str | None:
    if not path_value:
        return None

    p = Path(path_value)

    if p.is_file():
        return str(p)

    alt = BASE_DIR / path_value
    if alt.is_file():
        return str(alt)

    return None


def init_state(df: pd.DataFrame):
    series_ids = sorted(df["series_index"].unique().tolist())
    if "series_index" not in st.session_state:
        st.session_state.series_index = series_ids[0]

    current_series_df = df[df["series_index"] == st.session_state.series_index]
    question_numbers = current_series_df["question_number"].tolist()

    if "question_number" not in st.session_state or st.session_state.question_number not in question_numbers:
        st.session_state.question_number = question_numbers[0]

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
    questions = series_df["question_number"].tolist()
    current = st.session_state.question_number
    idx = questions.index(current)
    new_idx = max(0, min(len(questions) - 1, idx + step))
    st.session_state.question_number = questions[new_idx]
    st.session_state.show_answer = False


df = load_data()

if df.empty:
    st.error("No data found in tcf_all_series.csv")
    st.stop()

init_state(df)

series_ids = sorted(df["series_index"].unique().tolist())
series_titles = {
    s: df[df["series_index"] == s]["series_title"].iloc[0] or f"Série {s}"
    for s in series_ids
}

series_df = df[df["series_index"] == st.session_state.series_index].copy()
question_numbers = series_df["question_number"].tolist()
current_row = series_df[series_df["question_number"] == st.session_state.question_number].iloc[0]

# Sidebar
with st.sidebar:
    st.title("TCF Simulator")
    st.caption("Series + questions + correction")

    selected_series = st.selectbox(
        "Choose a series",
        options=series_ids,
        format_func=lambda x: series_titles.get(x, f"Série {x}"),
        index=series_ids.index(st.session_state.series_index),
    )

    if selected_series != st.session_state.series_index:
        set_series(df, selected_series)
        st.rerun()

    st.markdown("---")
    st.subheader("Questions")

    cols = st.columns(4)
    for i, qn in enumerate(question_numbers):
        col = cols[i % 4]
        label = f"{qn}"
        if col.button(label, use_container_width=True, key=f"qbtn_{qn}"):
            set_question(qn)
            st.rerun()

# Header
left, right = st.columns([3, 1])
with left:
    st.title(series_titles[st.session_state.series_index])
    st.caption(
        f"Question {current_row['question_number']} • "
        f"Niveau {current_row['level']} • "
        f"{current_row['points']} points"
    )

with right:
    st.metric("Questions", len(series_df))

st.markdown("---")

# Main layout
img_col, choice_col = st.columns([1.25, 1])

with img_col:
    st.subheader("Question")

    image_path = resolve_image_path(current_row.get("local_image_path", ""))
    if image_path:
        st.image(image_path, use_container_width=True)
    elif current_row.get("image_url", ""):
        st.image(current_row["image_url"], use_container_width=True)
    else:
        st.warning("No image found for this question.")

with choice_col:
    st.subheader("Choices")

    choice_map = {
        "A": current_row.get("A", ""),
        "B": current_row.get("B", ""),
        "C": current_row.get("C", ""),
        "D": current_row.get("D", ""),
    }

    correct_letter = current_row.get("correct_letter", "").strip()
    correct_text = current_row.get("correct_answer_text", "").strip()

    for letter in ["A", "B", "C", "D"]:
        text = choice_map[letter]

        if st.session_state.show_answer and letter == correct_letter:
            st.success(f"{letter}. {text}")
        else:
            st.info(f"{letter}. {text}")

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

st.markdown("---")

# Navigation
nav1, nav2, nav3 = st.columns([1, 2, 1])

with nav1:
    if st.button("⬅ Previous", use_container_width=True):
        nav_question(series_df, -1)
        st.rerun()

with nav2:
    st.progress(
        int(
            (question_numbers.index(st.session_state.question_number) + 1)
            / len(question_numbers)
            * 100
        )
    )
    st.caption(
        f"{question_numbers.index(st.session_state.question_number) + 1} / {len(question_numbers)}"
    )

with nav3:
    if st.button("Next ➡", use_container_width=True):
        nav_question(series_df, 1)
        st.rerun()
import os
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="TCF Simulator", page_icon="📘", layout="wide")

BASE_DIR = Path(__file__).resolve().parent

WRITTEN_CSV = BASE_DIR / "tcf_full_output" / "tcf_all_series.csv"
ORAL_CSV = BASE_DIR / "tcf_oral_output" / "tcf_all_series_oral.csv"


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


def init_state(df: pd.DataFrame):
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


written_df = load_csv(WRITTEN_CSV)
oral_df = load_csv(ORAL_CSV)

mode = st.sidebar.selectbox(
    "Section",
    ["Compréhension écrite", "Compréhension orale"]
)

df = written_df if mode == "Compréhension écrite" else oral_df

if df.empty:
    st.error(f"No dataset found for {mode}.")
    st.stop()

init_state(df)

series_ids = sorted(df["series_index"].unique().tolist())
series_titles = {
    s: (
        df[df["series_index"] == s]["series_title"].iloc[0]
        if "series_title" in df.columns
        else f"Série {s}"
    )
    for s in series_ids
}

series_df = df[df["series_index"] == st.session_state.series_index].copy()
qnums = series_df["question_number"].tolist()
current_row = series_df[series_df["question_number"] == st.session_state.question_number].iloc[0]

# Sidebar
with st.sidebar:
    st.title("TCF Simulator")
    st.caption("Series + media + correction")

    chosen_series = st.selectbox(
        "Choose a series",
        options=series_ids,
        index=series_ids.index(st.session_state.series_index),
        format_func=lambda x: series_titles.get(x, f"Série {x}")
    )

    if chosen_series != st.session_state.series_index:
        set_series(df, chosen_series)
        st.rerun()

    st.markdown("---")
    st.subheader("Questions")

    cols = st.columns(4)
    for i, q in enumerate(qnums):
        col = cols[i % 4]
        if col.button(str(q), use_container_width=True, key=f"q_{mode}_{q}"):
            set_question(q)
            st.rerun()

# Header
left, right = st.columns([3, 1])
with left:
    st.title(series_titles[st.session_state.series_index])
    level = current_row.get("level", "")
    points = current_row.get("points", "")
    st.caption(
        f"{mode} • Question {current_row['question_number']} • Niveau {level} • {points} points"
    )

with right:
    st.metric("Questions", len(series_df))

st.markdown("---")

media_col, choice_col = st.columns([1.25, 1])

with media_col:
    st.subheader("Question")

    # Written image
    if mode == "Compréhension écrite":
        img_path = normalize_media_path(current_row.get("local_image_path", ""))
        if img_path:
            st.image(img_path, use_container_width=True)
        elif current_row.get("image_url", ""):
            st.image(current_row["image_url"], use_container_width=True)
        else:
            st.warning("No image found.")

    # Oral prompt + optional image + audio
    else:
        prompt = current_row.get("prompt", "")
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

st.markdown("---")

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
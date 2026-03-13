# TCF Canada B2 Coach — Pro

A smarter local app to prepare TCF Canada **entièrement en français**, with dynamic test generation, strict validation, offline fallbacks, vocab SRS, timers, and NCLC predictions.

## Install
```
pip install -r requirements.txt
streamlit run app.py
```

## Highlights
- **FR-Only**: All content forced in French.
- **Robust generators**: Pydantic-validated JSON with auto-regeneration and rate-limit backoff.
- **Offline fallback**: Built-in B1–B2 MCQs, reading & listening mini-sets when API unavailable.
- **Vocab SRS**: spaced repetition notebook with due reviews.
- **Timer mode** for mocks; **Progress dashboard** with charts.
- **Per-skill NCLC estimates** per IRCC tables (non-official predictions).

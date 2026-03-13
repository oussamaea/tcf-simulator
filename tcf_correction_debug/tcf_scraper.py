from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import csv
import os
import re

BASE_URL = "https://app.formation-tcfcanada.com"
LOGIN_URL = "https://app.formation-tcfcanada.com"
TEST_URL = "https://app.formation-tcfcanada.com/epreuve/comprehension-ecrite/entrainement/comprehension-ecrite-test-1"

OUT_DIR = "tcf_series1_correction"
os.makedirs(OUT_DIR, exist_ok=True)

def click_first_that_works(page, selectors):
    for sel in selectors:
        try:
            page.locator(sel).first.click(timeout=4000)
            page.wait_for_timeout(2000)
            return True
        except Exception:
            pass
    return False

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=120)
    context = browser.new_context()
    page = context.new_page()

    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    input("Log in manually, then press ENTER... ")

    page.goto(TEST_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    # Start exam
    started = click_first_that_works(page, [
        'button:has-text("Commencer l\'épreuve")',
        'button:has-text("Commencer")',
        'text="Commencer l\'épreuve"',
        'text="Commencer"',
    ])
    if not started:
        input("Click 'Commencer' manually, then press ENTER... ")

    # Fill automatically
    filled = click_first_that_works(page, [
        'button:has-text("Remplir automatiquement")',
        'text="Remplir automatiquement"',
    ])
    if not filled:
        input("Click 'Remplir automatiquement' manually, then press ENTER... ")

    # Finish / submit
    finished = click_first_that_works(page, [
        'button:has-text("Terminer")',
        'button:has-text("Valider")',
        'button:has-text("Soumettre")',
        'button:has-text("Résultats")',
        'text="Terminer"',
        'text="Valider"',
        'text="Soumettre"',
        'text="Résultats"',
    ])
    if not finished:
        input("Finish/submit manually, then press ENTER... ")

    # Show detailed answers
    shown = click_first_that_works(page, [
        'button:has-text("Afficher les réponses")',
        'text="Afficher les réponses"',
        'button:has-text("Masquer les réponses")',  # if already visible
    ])
    if not shown:
        input("Open the correction/review page manually, then press ENTER... ")

    page.wait_for_timeout(3000)

    html = page.content()
    html_path = os.path.join(OUT_DIR, "correction_page.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    soup = BeautifulSoup(html, "html.parser")
    questions = []

    blocks = soup.select('div[id^="review-question-"]')

    for block in blocks:
        qnum = block.get("id", "").replace("review-question-", "").strip()

        # header info
        level = ""
        points = ""
        correct_text = ""

        header_button = block.find("button")
        if header_button:
            header_text = " ".join(header_button.stripped_strings)

            m_level = re.search(r"\b(A1|A2|B1|B2|C1|C2)\b", header_text)
            if m_level:
                level = m_level.group(1)

            m_points = re.search(r"\b(\d+)pt\b", header_text)
            if m_points:
                points = m_points.group(1)

            m_correct = re.search(r"✓\s*(.+)$", header_text)
            if m_correct:
                correct_text = m_correct.group(1).strip()

        # image extraction
        img_url = ""
        img = block.find("img")
        if img and img.get("src"):
            src = img["src"]
            if "url=" in src:
                parsed = parse_qs(urlparse(src).query)
                if "url" in parsed and parsed["url"]:
                    img_url = parsed["url"][0]
            else:
                img_url = src

        # choices
        choices = {"A": "", "B": "", "C": "", "D": ""}
        correct_letter = ""

        answer_divs = block.select("div.border.text-sm")
        for ans in answer_divs:
            text = " ".join(ans.stripped_strings)

            m = re.match(r"^([ABCD])\.\s*(.*)$", text)
            if not m:
                continue

            letter = m.group(1)
            choice_text = m.group(2).replace("Bonne réponse", "").strip()
            choices[letter] = choice_text

            if "Bonne réponse" in text:
                correct_letter = letter

        # fallback by matching text
        if not correct_letter and correct_text:
            norm_correct = " ".join(correct_text.split()).strip().lower()
            for letter in ["A", "B", "C", "D"]:
                norm_choice = " ".join(choices[letter].split()).strip().lower()
                if norm_choice == norm_correct:
                    correct_letter = letter
                    break

        questions.append({
            "question_number": qnum,
            "level": level,
            "points": points,
            "image": img_url,
            "A": choices["A"],
            "B": choices["B"],
            "C": choices["C"],
            "D": choices["D"],
            "correct_answer_text": correct_text,
            "correct_letter": correct_letter,
        })

    out_csv = os.path.join(OUT_DIR, "series1_dataset.csv")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "question_number",
                "level",
                "points",
                "image",
                "A", "B", "C", "D",
                "correct_answer_text",
                "correct_letter",
            ],
        )
        writer.writeheader()
        writer.writerows(questions)

    print("Questions scraped:", len(questions))
    print("Saved HTML:", html_path)
    print("Saved CSV:", out_csv)

    browser.close()
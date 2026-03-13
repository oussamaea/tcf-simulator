from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import csv
import os
import re
import html
import requests
from pathlib import Path

BASE_URL = "https://app.formation-tcfcanada.com"
LOGIN_URL = "https://app.formation-tcfcanada.com"
SERIES_URL = "https://app.formation-tcfcanada.com/epreuve/comprehension-ecrite/series"

OUT_DIR = Path("tcf_full_output")
IMAGES_DIR = OUT_DIR / "images"
HTML_DIR = OUT_DIR / "review_pages"
DEBUG_DIR = OUT_DIR / "debug"

for d in [OUT_DIR, IMAGES_DIR, HTML_DIR, DEBUG_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def click_text_any(page, texts, timeout=5000, wait_ms=1500):
    selectors = []
    for t in texts:
        escaped = t.replace('"', '\\"')
        selectors.extend([
            f'button:has-text("{escaped}")',
            f'a:has-text("{escaped}")',
            f'text="{escaped}"'
        ])

    for sel in selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(timeout=timeout)
            loc.click(timeout=timeout)
            page.wait_for_timeout(wait_ms)
            return True, sel
        except Exception:
            continue
    return False, ""


def auto_scroll(page, steps=25, pause_ms=300):
    for _ in range(steps):
        page.mouse.wheel(0, 2500)
        page.wait_for_timeout(pause_ms)


def get_series_links(page):
    cards = page.locator('a[href*="comprehension-ecrite-test-"]')
    count = cards.count()
    results = []

    for i in range(count):
        card = cards.nth(i)
        href = card.get_attribute("href") or ""
        full_url = urljoin(BASE_URL, href)

        title = f"Série {i + 1}"
        try:
            t = card.locator("div.text-sm.font-semibold.text-gray-900")
            if t.count() > 0:
                title = t.first.inner_text().strip()
        except Exception:
            pass

        results.append({
            "series_index": i + 1,
            "series_title": title,
            "series_url": full_url,
        })

    return results


def open_series_from_series_page(page, series_title):
    page.goto(SERIES_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    ok, _ = click_text_any(page, [series_title], timeout=4000, wait_ms=2000)
    if ok:
        return True

    m = re.search(r"(\d+)", series_title)
    if m:
        idx = m.group(1)
        try:
            page.locator(f'a[href*="comprehension-ecrite-test-{idx}"]').first.click(timeout=5000)
            page.wait_for_timeout(2000)
            return True
        except Exception:
            pass

    return False


def ensure_exam_started(page):
    for _ in range(3):
        ok, _ = click_text_any(page, [
            "Commencer l'épreuve",
            "Commencer l’epreuve",
            "Commencer",
        ], timeout=5000, wait_ms=2500)
        if ok:
            return True

        body = page.locator("body").inner_text()
        if "Temps restant" in body or "Navigation des questions" in body:
            return True

        page.wait_for_timeout(1000)
    return False


def ensure_auto_filled(page):
    for _ in range(3):
        ok, _ = click_text_any(page, [
            "Remplir automatiquement",
        ], timeout=5000, wait_ms=2500)
        if ok:
            return True

        body = page.locator("body").inner_text()
        if "Afficher les réponses" in body or "Revue détaillée" in body:
            return True

        page.wait_for_timeout(1000)
    return False


def ensure_answers_visible(page):
    for _ in range(5):
        body = page.locator("body").inner_text()

        if "Revue détaillée" in body and ("Masquer les réponses" in body or "Bonne réponse" in body):
            return True

        ok, _ = click_text_any(page, [
            "Afficher les réponses",
            "Voir les réponses",
            "Correction",
            "Corrigé",
            "Masquer les réponses",
        ], timeout=5000, wait_ms=2500)
        if ok:
            body2 = page.locator("body").inner_text()
            if "Revue détaillée" in body2:
                return True

        page.wait_for_timeout(1200)
    return False


def extract_original_image_url(src: str) -> str:
    if not src:
        return ""
    if "url=" in src:
        parsed = parse_qs(urlparse(src).query)
        if "url" in parsed and parsed["url"]:
            return parsed["url"][0]
    return urljoin(BASE_URL, src)


def download_image(url: str, out_path: Path) -> bool:
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        return True
    except Exception:
        return False


def parse_question_block(block):
    qid = block.get("id", "")
    qnum = qid.replace("review-question-", "").strip()

    header_btn = block.find("button")
    header_text = " ".join(header_btn.stripped_strings) if header_btn else ""

    level = ""
    points = ""
    correct_answer_text = ""

    m_level = re.search(r"\b(A1|A2|B1|B2|C1|C2)\b", header_text)
    if m_level:
        level = m_level.group(1)

    m_points = re.search(r"\b(\d+)pt\b", header_text)
    if m_points:
        points = m_points.group(1)

    m_correct = re.search(r"✓\s*(.+)$", header_text)
    if m_correct:
        correct_answer_text = m_correct.group(1).strip()

    image_url = ""
    img = block.find("img")
    if img and img.get("src"):
        image_url = extract_original_image_url(img["src"])

    choices = {"A": "", "B": "", "C": "", "D": ""}
    correct_letter = ""

    answer_blocks = block.select("div.px-3.py-2.rounded-lg.border.text-sm")
    for ans in answer_blocks:
        text = " ".join(ans.stripped_strings)
        m = re.match(r"^([ABCD])\.\s*(.*)$", text)
        if not m:
            continue

        letter = m.group(1)
        choice_text = m.group(2).replace("Bonne réponse", "").strip()
        choices[letter] = choice_text

        if "Bonne réponse" in text:
            correct_letter = letter

    if not correct_letter and correct_answer_text:
        norm_correct = " ".join(correct_answer_text.split()).strip().lower()
        for letter in ["A", "B", "C", "D"]:
            norm_choice = " ".join(choices[letter].split()).strip().lower()
            if norm_choice == norm_correct:
                correct_letter = letter
                break

    return {
        "question_number": qnum,
        "level": level,
        "points": points,
        "image_url": image_url,
        "A": choices["A"],
        "B": choices["B"],
        "C": choices["C"],
        "D": choices["D"],
        "correct_answer_text": correct_answer_text,
        "correct_letter": correct_letter,
    }


def build_series_review_html(series_title, questions):
    def option_html(letter, text, correct_letter):
        is_correct = letter == correct_letter
        style = (
            "border:2px solid #86efac;background:#f0fdf4;color:#14532d;font-weight:600;"
            if is_correct
            else
            "border:1px solid #d1d5db;background:#fff;color:#374151;"
        )
        badge = (
            '<span style="margin-left:10px;font-size:12px;background:#dcfce7;color:#166534;'
            'padding:3px 8px;border-radius:999px;">Bonne réponse</span>'
            if is_correct else ""
        )
        return f'''
        <div style="padding:12px 14px;border-radius:10px;{style}">
            <span>{html.escape(letter)}. {html.escape(text)}</span>{badge}
        </div>
        '''

    cards = []
    for q in questions:
        img_html = ""
        if q["local_image_rel"]:
            img_html = f'''
            <div style="margin:14px 0 18px;">
                <img src="{html.escape(q["local_image_rel"])}"
                     alt="Question {html.escape(str(q["question_number"]))}"
                     style="max-width:100%;height:auto;border-radius:12px;border:1px solid #d1d5db;">
            </div>
            '''

        cards.append(f'''
        <section style="background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:18px;margin:0 0 18px 0;box-shadow:0 1px 4px rgba(0,0,0,.05);">
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px;">
                <span style="background:#2563eb;color:#fff;padding:6px 10px;border-radius:999px;font-weight:700;">Q{html.escape(str(q["question_number"]))}</span>
                <span style="background:#ecfdf5;color:#065f46;padding:4px 8px;border-radius:999px;font-size:13px;">{html.escape(q["level"])}</span>
                <span style="color:#6b7280;font-size:14px;">{html.escape(str(q["points"]))} pt</span>
                <span style="margin-left:auto;color:#166534;font-weight:700;">Correction: {html.escape(q["correct_letter"])} — {html.escape(q["correct_answer_text"])}</span>
            </div>
            {img_html}
            <div style="display:grid;gap:10px;">
                {option_html("A", q["A"], q["correct_letter"])}
                {option_html("B", q["B"], q["correct_letter"])}
                {option_html("C", q["C"], q["correct_letter"])}
                {option_html("D", q["D"], q["correct_letter"])}
            </div>
        </section>
        ''')

    return f'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(series_title)}</title>
</head>
<body style="font-family:Arial,sans-serif;background:#f3f4f6;margin:0;padding:24px;">
    <div style="max-width:950px;margin:0 auto;">
        <h1 style="margin:0 0 18px 0;">{html.escape(series_title)}</h1>
        <p style="margin:0 0 24px 0;color:#4b5563;">Image de la question, choix, et correction.</p>
        {"".join(cards)}
    </div>
</body>
</html>'''


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=80)
    context = browser.new_context()
    page = context.new_page()

    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    input("Log in manually, then press ENTER here... ")

    page.goto(SERIES_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    series_list = get_series_links(page)
    print(f"Found {len(series_list)} series")

    master_rows = []

    for series in series_list:
        sidx = series["series_index"]
        stitle = series["series_title"]

        print(f"\n=== {stitle} ===")

        if not open_series_from_series_page(page, stitle):
            print(f"Could not open {stitle}")
            continue

        if not ensure_exam_started(page):
            print(f"Could not start exam for {stitle}")
            continue

        if not ensure_auto_filled(page):
            print(f"Could not auto-fill exam for {stitle}")
            continue

        if not ensure_answers_visible(page):
            print(f"Could not open detailed correction for {stitle}")
            continue

        auto_scroll(page, steps=30, pause_ms=300)
        page.wait_for_timeout(1500)

        html_content = page.content()
        (DEBUG_DIR / f"series_{sidx:02d}_correction.html").write_text(html_content, encoding="utf-8")

        soup = BeautifulSoup(html_content, "html.parser")
        blocks = soup.select('div[id^="review-question-"]')

        if not blocks:
            print(f"No question blocks found for {stitle}")
            continue

        series_rows = []

        for block in blocks:
            item = parse_question_block(block)

            qnum = str(item["question_number"]).zfill(2)
            local_image_rel = ""
            local_image_abs = ""

            if item["image_url"]:
                ext = os.path.splitext(urlparse(item["image_url"]).path)[1].lower() or ".png"
                if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
                    ext = ".png"

                local_image_abs = str(IMAGES_DIR / f"series_{sidx:02d}_q{qnum}{ext}")
                if download_image(item["image_url"], Path(local_image_abs)):
                    local_image_rel = os.path.relpath(local_image_abs, HTML_DIR).replace("\\", "/")

            row = {
                "series_index": sidx,
                "series_title": stitle,
                "question_number": item["question_number"],
                "level": item["level"],
                "points": item["points"],
                "image_url": item["image_url"],
                "local_image_path": local_image_abs,
                "A": item["A"],
                "B": item["B"],
                "C": item["C"],
                "D": item["D"],
                "correct_answer_text": item["correct_answer_text"],
                "correct_letter": item["correct_letter"],
                "local_image_rel": local_image_rel,
            }

            series_rows.append(row)
            master_rows.append({k: v for k, v in row.items() if k != "local_image_rel"})

        review_html = build_series_review_html(stitle, series_rows)
        review_path = HTML_DIR / f"series_{sidx:02d}_review.html"
        review_path.write_text(review_html, encoding="utf-8")

        print(f"Scraped {len(series_rows)} questions for {stitle}")

    browser.close()

csv_path = OUT_DIR / "tcf_all_series.csv"
with csv_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "series_index",
            "series_title",
            "question_number",
            "level",
            "points",
            "image_url",
            "local_image_path",
            "A",
            "B",
            "C",
            "D",
            "correct_answer_text",
            "correct_letter",
        ],
    )
    writer.writeheader()
    writer.writerows(master_rows)

print("\nDONE")
print(f"Master CSV: {csv_path}")
print(f"Images folder: {IMAGES_DIR}")
print(f"HTML review pages: {HTML_DIR}")
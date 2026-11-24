"""Drives the React UI (served by nginx in Docker) with Playwright and saves five screenshots
plus one collage.  usage: python screenshots.py OUT_DIR [BASE_URL]"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

OUT = sys.argv[1]
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://localhost"
os.makedirs(OUT, exist_ok=True)


def wait_idle(page):
    page.wait_for_timeout(300)
    page.wait_for_selector(".typing", state="detached", timeout=60000)
    page.wait_for_timeout(500)


def click(page, title):
    page.locator(".quick-replies button:not([disabled])", has_text=title).first.click()
    wait_idle(page)


def type_msg(page, msg):
    page.fill("#msg", msg)
    page.press("#msg", "Enter")
    wait_idle(page)


def shot(page, name):
    path = os.path.join(OUT, name)
    page.locator(".chat").screenshot(path=path)
    return path


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 520, "height": 900}, device_scale_factor=2)

    def fresh():
        pg = ctx.new_page()
        pg.goto(BASE)
        pg.wait_for_selector(".bubble.bot", timeout=60000)
        wait_idle(pg)
        return pg

    shots = []
    pg = fresh()
    shots.append(shot(pg, "1_karsilama.png"))
    click(pg, "I agree"); click(pg, "Check my symptoms")
    type_msg(pg, "I have a sore throat")
    click(pg, "No"); click(pg, "Yes"); click(pg, "3 to 7 days"); click(pg, "4-6 moderate")
    pg.locator(".card.triage").scroll_into_view_if_needed()
    shots.append(shot(pg, "2_triyaj_karti.png"))
    click(pg, "Book an appointment")
    pg.locator(".quick-replies button:not([disabled])").first.click(); wait_idle(pg)
    pg.locator(".card.appointment").scroll_into_view_if_needed()
    shots.append(shot(pg, "3_randevu_karti.png"))
    pg.close()

    pg = fresh(); click(pg, "I agree")
    type_msg(pg, "I have crushing chest pain")
    shots.append(shot(pg, "4_acil_serit.png")); pg.close()

    pg = fresh(); click(pg, "I agree"); click(pg, "Speak to a nurse")
    shots.append(shot(pg, "5_hemsire_devri.png")); pg.close()
    browser.close()

# collage: five panels in one row, each with a numbered caption
labels = ["(a) Karşılama ve onay", "(b) Triyaj sonucu kartı", "(c) Randevu onay kartı",
          "(d) Acil durum şeridi", "(e) Hemşireye devir şeridi"]
imgs = [Image.open(s).convert("RGB") for s in shots]
h = min(i.height for i in imgs)
imgs = [i.resize((int(i.width * h / i.height), h)) for i in imgs]
w = max(i.width for i in imgs)
pad, cap, cols = 24, 70, 3          # 3 + 2 grid, readable at A4 text width
rows = [imgs[:cols], imgs[cols:]]
W = cols * w + (cols + 1) * pad
canvas = Image.new("RGB", (W, len(rows) * (h + cap + pad) + pad), "white")
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
except OSError:
    font = ImageFont.load_default()
d = ImageDraw.Draw(canvas)
k = 0
for r, row in enumerate(rows):
    x = (W - (len(row) * w + (len(row) - 1) * pad)) // 2
    y = pad + r * (h + cap + pad)
    for im in row:
        canvas.paste(im, (x, y))
        tw = d.textlength(labels[k], font=font)
        d.text((x + (im.width - tw) / 2, y + h + 14), labels[k], fill="black", font=font)
        x += w + pad; k += 1
canvas.save(os.path.join(OUT, "ui_ekran.png"))
print("saved", len(shots), "screens + ui_ekran.png to", OUT)

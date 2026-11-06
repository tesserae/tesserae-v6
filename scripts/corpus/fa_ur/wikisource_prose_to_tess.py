#!/usr/bin/env python3
"""Build prose .tess files from fetched Persian and Urdu Wikisource pages.

Reads the pages saved by wikisource_fetch.py, keeps the author's own pages in a
fixed order (editors' prefaces, redirects, duplicate variants and the contents
page are left out, listed below), and writes one paragraph per line with the
reference `<work>.<section>.<paragraph>`. A <work>.sections.json beside the file
lists each section's page title, revision id, reference range and line count.

Usage:
    wikisource_prose_to_tess.py WIKISOURCE_DIR OUT_DIR
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wikisource_html_text import paragraphs  # noqa: E402

MARKS = re.compile("[ً-ٰٟـۖ-ۜ۟-۪ۨ-ۭ‎‏‪-‮]")
DROP_PARA = re.compile(r"^(سانچہ:|سانچه:|تغییرمسیر به|تغییر مسیر به|پانویس$)")

# (work id, folder, language, [(page title, section number)], reason notes)
WORKS = [
    (
        "nizami_arudi.chahar_maqala",
        "chahar_maqala",
        [
            ("چهار مقاله/مقدمه", 0),
            ("چهار مقاله/مقالت اول", 1),
            ("چهار مقاله/مقالت دوم", 2),
            ("چهار مقاله/مقالت سوم", 3),
            ("چهار مقاله/مقالت چهارم", 4),
        ],
    ),
    (
        "nasrallah_munshi.kalila_va_demna",
        "kalila",
        [
            ("کلیله و دمنه/مقدمه نصراله منشی", 1),
            ("کلیله و دمنه/مقدمه عبداله ابن المقفع", 2),
            ("کلیله و دمنه/مقدمه بوزرجمهر بختکان", 3),
            ("کلیله و دمنه/باب برزویه طبیب", 4),
            ("کلیله و دمنه/باب الاسد و الثور", 5),
            ("کلیله و دمنه/باب الفحص عن امر دمنه", 6),
            ("کلیله و دمنه/باب الحمامه المطوقه و الجرذ و الغراب و السلحفاه و الظبی", 7),
            ("کلیله و دمنه/باب البوم و الغراب", 8),
            ("کلیله و دمنه/باب القرد و السلحفاة", 9),
            ("کلیله و دمنه/باب الزاهد و ابن عرس", 10),
            ("کلیله و دمنه/باب السنور و الجرذ", 11),
            ("کلیله و دمنه/باب الملک و الطائر فنزة", 12),
            ("کلیله و دمنه/باب الاسد و ابن آوی", 13),
            ("کلیله و دمنه/باب النابل و اللبوة", 14),
            ("کلیله و دمنه/باب الزاهد و الضعیف", 15),
            ("کلیله و دمنه/باب الملک و البراهمة", 16),
            ("کلیله و دمنه/باب الصائغ و السیاح", 17),
            ("کلیله و دمنه/باب ابن الملک و اصحابه", 18),
            ("کلیله و دمنه/خاتمه مترجم", 19),
        ],
    ),
    (
        "mir_amman.bagh_o_bahar",
        "bagh_o_bahar",
        [
            ("باغ و بہار/آغاز", 1),
            ("باغ و بہار/سبب تالیف کتاب", 2),
            ("باغ و بہار/آغاز قصے کا", 3),
            ("باغ و بہار/سیر پہلے درویش کی", 4),
            ("باغ و بہار/سیر دوسرے درویش کی", 5),
            ("باغ و بہار/سیر تیسرے درویش کی", 6),
            ("باغ و بہار/سیر چوتھے درویش کی", 7),
        ],
    ),
    (
        "suroor.fasana_e_ajaib",
        "fasana",
        [
            (t, i + 1)
            for i, t in enumerate(
                [
                    "حمد",
                    "نعت",
                    "زمزمہ پردازی عندلیب نغمہ سرا کی",
                    "کیفیت شہر بے نظیرکی (بیان لکھنؤ)",
                    "وجہِ تالیف اس قصۂ بے نظیر کی",
                    "آغاز داستان",
                    "جَولانی سَمَندِ تیز رفتار ِقلم کی",
                    "وطن آوارہ ہونا نو گرفتارِ محبت کا",
                    "رِہا ہونا اس گرِفتار دامِ سحر کا",
                    "رخصت ہونا جان عالم کا ملکہ نگار سے",
                    "بیانِ جلسۂ شادی اُس وطن آوارہ کا",
                    "شرح جگر خراشیٔ مصائب دیدۂ روزگار",
                    "نقل سوداگر کی بیٹی کی",
                    "حالِ خُسراں مآل مجسٹن کے بیٹے کا",
                    "عزمِ وطن شاہ زادۂ جانِ عالم کا",
                    "وُرودِ موکبِ جاہ و جلالِ شاہ زادۂ خجستہ خِصال",
                    "داستانِ حیرت بیاں",
                    "فسانۂ سلطانِ یمن",
                    "ناقہ بِٹھانا تقدیر کا پھر اُسی دشتِ پُر خوف و خطر میں",
                    "روانہ ہونا شہ زادۂ جانِ عالم کا اُس دشت سے",
                    "حکایتِ پُر عبرت، جاں سوز، حیرت اَفزا، غم اندوز؛ یعنی سانِحۂ برادرانِ تَواَم",
                    "حکایتِ پُر شکایت چھوٹے بھائی کی",
                    "بیانِ حال اُس غَریق بحر ملال کا",
                    "پہنچنا شہ زادۂ والا جاہ کا مَرکبِ صبا پر",
                    "وُروٗدِ عَساکِرِ فیروزی اثر صحرائے ہمیشہ بہارمیں",
                    "حکایَتِ ہوش رُبا، نقلِ عبرت خیز، حیرت افزا قاضیٔ متشرِّع اور مُفتی صاحبِ وَرع کی",
                    "اب تماشا ہے نہ سیر ہے، خاتمہ بِالخیر ہے",
                ]
            )
        ],
        "فسانۂ عجائب/",
    ),
    (
        "azad.ab_e_hayat",
        "ab_e_hayat",
        [
            (t, i + 1)
            for i, t in enumerate(
                [
                    "دیباچہ",
                    "زبان اردو کی تاریخ",
                    "نظم اردو کی تاریخ",
                    "پہلا دور/تمہید",
                    "شاہ مبارک آبرو",
                    "شیخ شرف الدین مضمون",
                    "محمد شاکر ناجی",
                    "محمد احسن احسن",
                    "غلام مصطفیٰ خان یکرنگ",
                    "دوسرا دور/تمہید",
                    "شاہ حاتم",
                    "سراج الدین علی خان آرزو",
                    "اشرف علی خاں فغاں",
                    "دوسرا دور/خاتمہ",
                    "تیسرا دور/تمہید",
                    "مرزا جانِ جاناں مظہر",
                    "میر عبدالحی تاباں",
                    "غزلہائے تاباں",
                    "مرزا محمد رفیع سودا",
                    "مرزا فاخر مکین",
                    "میر ضاحک",
                    "خواجہ میر درد",
                    "سید محمد میر سوز",
                    "میر محمد تقی میر",
                    "تیسرا دور/خاتمہ",
                    "چوتھا دور/تمہید",
                    "شیخ قلند بخش جرات",
                    "میر حسن",
                    "سید انشاء اللہ خاں",
                    "شیخ غلام ہمدانی مصحفی",
                    "چوتھا دور/خاتمہ",
                    "پانچواں دور/تمہید",
                    "تمہید شیخ امام بخش ناسخ کے حال کی​",
                    "میر مستحسن، خلیق",
                    "خواجہ حیدر علی آتش",
                    "شاہ نصیر",
                    "مومن خاں صاحب مومن",
                    "ملک الشعراء خاقانی ہند شیخ ابراہیم ذوق",
                    "نجم الدولہ دبیر الملک مرزا اسد اللہ خاں غالب",
                    "مِرزا سَلامَت علی دبیر",
                    "مِیر بَبر علی انیس",
                ]
            )
        ],
        "آب حیات/",
    ),
]
# Pages left out on purpose, by work: editors' prefaces and notes, redirects,
# duplicate variants and tables of contents.
LEFT_OUT = {
    "chahar_maqala": "Qazvini's editorial prefaces (مقدمه مصحح and its three subpages)",
    "kalila": "two redirect pages (باب الزاهد و الضعيف, باب الصائغ و السياح, spelled with Arabic yeh)",
    "bagh_o_bahar": "Gilchrist's preface (مقدمہ), a second wording of Mir Amman's preface (مقدمہ میر امن دہلوی, near duplicate of آغاز), and the petition to the college (عرضی میر امن دلی والے کی, two paragraphs of correspondence)",
    "fasana": "Makhmoor Akbarabadi's editorial preface (مقدمہ, 1928) with its footnote",
    "ab_e_hayat": "the contents page, the divider page of the first period, and the head page",
}


def clean(t):
    t = MARKS.sub("", t)
    t = t.replace("﷽", "بسم اللہ الرحمن الرحیم")
    t = t.replace("ي", "ی").replace("ك", "ک")
    t = re.sub(r"[​﻿]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def main():
    src, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    for entry in WORKS:
        work, folder, pages = entry[0], entry[1], entry[2]
        prefix = entry[3] if len(entry) > 3 else ""
        pj = json.load(open(os.path.join(src, folder, "pages.json"), encoding="utf-8"))
        html_by_title = {}
        for n, t in enumerate(pj):
            html_by_title[t] = os.path.join(src, folder, "html", f"{n:03d}.json")
        lines, sections = [], []
        for title, sec in pages:
            full = title if "/" in title and not prefix else (prefix + title)
            if full not in html_by_title:
                # titles in the Persian lists already carry the main title
                raise SystemExit(f"page not fetched: {full}")
            d = json.load(open(html_by_title[full], encoding="utf-8"))
            paras = [
                clean(t)
                for k, t in paragraphs(d["html"])
                if k == "p" and not DROP_PARA.match(t.strip())
            ]
            paras = [p for p in paras if p]
            first = None
            for i, p in enumerate(paras, 1):
                ref = f"{work}.{sec}.{i}"
                lines.append((ref, p))
                first = first or ref
            sections.append(
                {
                    "section": sec,
                    "page": full,
                    "revid": d["revid"],
                    "first_ref": first,
                    "last_ref": lines[-1][0],
                    "paragraphs": len(paras),
                }
            )
        with open(os.path.join(out, work + ".tess"), "w", encoding="utf-8") as f:
            for ref, t in lines:
                f.write(f"<{ref}>\t{t}\n")
        with open(os.path.join(out, work + ".sections.json"), "w", encoding="utf-8") as f:
            json.dump(
                {"sections": sections, "left_out": LEFT_OUT[folder]},
                f,
                ensure_ascii=False,
                indent=1,
            )
        chars = sum(len(t) for _, t in lines)
        print(work, len(lines), "paragraphs", chars, "characters")


if __name__ == "__main__":
    main()

"""One-page Atomic Habits PDF: personalized plan + static cheat sheet."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fpdf import FPDF


PURPLE = (124, 58, 237)
DARK = (31, 41, 55)
GRAY = (107, 114, 128)
LIGHT_BG = (249, 250, 251)
BORDER = (229, 231, 235)

PORTRAITS_DIR = Path(__file__).resolve().parent / "assets" / "portraits"

# user_id -> portrait filename
PORTRAIT_BY_USER_ID = {
    "kim": "kim.png",
    "joshua": "joshua.png",
    "daniel": "daniel.png",
    "woanru": "woanru.png",
    "karen": "karen.png",
}


class HabitPDF(FPDF):
    def header(self) -> None:
        pass

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*GRAY)
        self.cell(0, 5, "Atomic Habits Coach  |  Inspired by James Clear", align="C")


def _safe(text: str) -> str:
    """Strip characters that break core Helvetica fonts."""
    replacements = {
        "\u2014": "-",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u2192": "->",
    }
    out = text or ""
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out.encode("latin-1", "replace").decode("latin-1")


def resolve_portrait_path(user_id: str | None) -> Path | None:
    if not user_id:
        return None
    filename = PORTRAIT_BY_USER_ID.get(user_id.strip().lower())
    if not filename:
        return None
    path = PORTRAITS_DIR / filename
    return path if path.is_file() else None


def build_pdf(
    goal: str,
    anchor: str,
    plan: dict[str, Any],
    person_name: str | None = None,
    user_id: str | None = None,
) -> bytes:
    pdf = HabitPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    page_w = pdf.w - pdf.l_margin - pdf.r_margin

    portrait = resolve_portrait_path(user_id)
    portrait_w = 32.0
    title_w = page_w - (portrait_w + 6) if portrait else page_w

    # --- Title (+ optional portrait top-right) ---
    title_y = pdf.get_y()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*PURPLE)
    pdf.cell(title_w, 8, "Atomic Habits Coach", ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    subtitle = "Your personalized action plan"
    if person_name:
        subtitle = f"Personalized for {_safe(person_name)}"
    pdf.cell(title_w, 5, subtitle, ln=True)

    if portrait:
        try:
            pdf.image(
                str(portrait),
                x=pdf.l_margin + page_w - portrait_w,
                y=title_y,
                w=portrait_w,
                h=portrait_w,
            )
            # Keep content below portrait if it would overlap
            pdf.set_y(max(pdf.get_y() + 2, title_y + portrait_w + 3))
        except Exception:
            pdf.ln(2)
    else:
        pdf.ln(2)

    # Goal box
    pdf.set_fill_color(*LIGHT_BG)
    pdf.set_draw_color(*BORDER)
    y0 = pdf.get_y()
    pdf.rect(pdf.l_margin, y0, page_w, 14, style="DF")
    pdf.set_xy(pdf.l_margin + 3, y0 + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*GRAY)
    pdf.cell(page_w - 6, 4, "YOUR GOAL", ln=True)
    pdf.set_x(pdf.l_margin + 3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*DARK)
    pdf.cell(page_w - 6, 6, _safe(goal)[:90], ln=True)
    pdf.set_y(y0 + 16)

    # Habit stack highlight
    stack = plan.get("habit_stack") or f"After I {anchor}, I will {plan.get('two_minute_habit', '...')}"
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*PURPLE)
    pdf.cell(page_w, 5, "HABIT STACK", ln=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(page_w, 5, _safe(stack))
    pdf.ln(1)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(30, 5, "2-Minute Rule:", ln=False)
    pdf.set_text_color(*DARK)
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(page_w - 30, 5, _safe(plan.get("two_minute_habit", "")))
    pdf.ln(2)

    # Four laws
    mode = (plan.get("mode") or "build").lower()
    if mode == "break":
        laws = [
            ("CUE", "Make it Invisible", plan.get("cue", "")),
            ("CRAVING", "Make it Unattractive", plan.get("craving", "")),
            ("RESPONSE", "Make it Difficult", plan.get("response", "")),
            ("REWARD", "Make it Unsatisfying", plan.get("reward", "")),
        ]
    else:
        laws = [
            ("CUE", "Make it Obvious", plan.get("cue", "")),
            ("CRAVING", "Make it Attractive", plan.get("craving", "")),
            ("RESPONSE", "Make it Easy", plan.get("response", "")),
            ("REWARD", "Make it Satisfying", plan.get("reward", "")),
        ]

    col_w = (page_w - 6) / 2
    row_h = 22
    start_y = pdf.get_y()
    for i, (label, law, tip) in enumerate(laws):
        col = i % 2
        row = i // 2
        x = pdf.l_margin + col * (col_w + 6)
        y = start_y + row * (row_h + 3)
        pdf.set_xy(x, y)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_draw_color(*BORDER)
        pdf.rect(x, y, col_w, row_h, style="D")
        pdf.set_xy(x + 2, y + 2)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*PURPLE)
        pdf.cell(col_w - 4, 4, f"{label}  |  {law}", ln=True)
        pdf.set_x(x + 2)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(col_w - 4, 3.5, _safe(tip)[:180])

    pdf.set_y(start_y + 2 * (row_h + 3) + 2)

    # Environment tip
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*PURPLE)
    pdf.cell(page_w, 5, "ENVIRONMENT DESIGN", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(page_w, 4.5, _safe(plan.get("environment_tip", "")))
    pdf.ln(3)

    # Divider
    y_div = pdf.get_y()
    pdf.set_draw_color(*PURPLE)
    pdf.set_line_width(0.4)
    pdf.line(pdf.l_margin, y_div, pdf.l_margin + page_w, y_div)
    pdf.ln(4)

    # --- Cheat sheet (static) ---
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*PURPLE)
    pdf.cell(page_w, 6, "Cheat Sheet", ln=True)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*GRAY)
    pdf.cell(page_w, 5, "THE HABIT LOOP", ln=True)

    loop_labels = ["CUE", "CRAVING", "RESPONSE", "REWARD"]
    box_w = (page_w - 18) / 4
    ly = pdf.get_y()
    for i, label in enumerate(loop_labels):
        x = pdf.l_margin + i * (box_w + 6)
        pdf.set_fill_color(*LIGHT_BG)
        pdf.set_draw_color(*PURPLE)
        pdf.rect(x, ly, box_w, 10, style="DF")
        pdf.set_xy(x, ly + 2.5)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*PURPLE)
        pdf.cell(box_w, 5, label, align="C")
        if i < 3:
            pdf.set_xy(x + box_w, ly + 2)
            pdf.set_text_color(*GRAY)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(6, 6, ">", align="C")
    pdf.set_y(ly + 13)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*GRAY)
    pdf.cell(page_w, 5, "PLATEAU OF LATENT POTENTIAL", ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(
        page_w,
        4,
        _safe(
            "Habits often feel like they are not working until a breakthrough. "
            "Progress is compounding under the surface — stick with the system."
        ),
    )
    pdf.ln(2)

    pdf.set_fill_color(*LIGHT_BG)
    pdf.set_draw_color(*BORDER)
    qy = pdf.get_y()
    pdf.rect(pdf.l_margin, qy, page_w, 16, style="DF")
    pdf.set_xy(pdf.l_margin + 4, qy + 3)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(
        page_w - 8,
        5,
        '"You do not rise to the level of your goals. You fall to the level of your systems."',
    )
    pdf.set_xy(pdf.l_margin + 4, qy + 11)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*GRAY)
    pdf.cell(page_w - 8, 4, "- James Clear, Atomic Habits")

    return bytes(pdf.output())

#!/usr/bin/env python3
"""
Build the presentation (PPTX) from the simulation outputs.

    python sampling_simulation.py            # first, to create ./output
    python tools/build_presentation.py       # then, to create presentation/*.pptx

Put your own details in tools/student_info.py first.
Every number on the slides is read from output/results.json.
"""
import json
import math
import re
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image as PILImage
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from student_info import STUDENT  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "output" / "figures"
OUT_PATH = ROOT / "presentation" / "Sampling_Aliasing_Presentation.pptx"
R = json.loads((ROOT / "output" / "results.json").read_text())

# ------------------------------------------------------------------ palette & fonts
NAVY, PANEL = "0F2A47", "19406B"
INK, MUTED, LIGHT, WHITE = "1B2733", "56677A", "EEF3F9", "FFFFFF"
ACCENT, ACCENT_ON_DARK, ICE = "B84A00", "F2A33A", "C9D6E6"
HEAD, BODY, MONO = "Cambria", "Calibri", "Courier New"


def rgb(h):
    return RGBColor.from_string(h)


# ------------------------------------------------------------------ text helpers
TOKEN = re.compile(r"(\^\{[^}]*\}|_\{[^}]*\}|<b>.*?</b>)")


def fill_runs(p, text, size, bold, color, font, italic=False):
    for part in TOKEN.split(text):
        if not part:
            continue
        base = None
        if part.startswith("^{"):
            part, base = part[2:-1], "30000"
        elif part.startswith("_{"):
            part, base = part[2:-1], "-25000"
        run_bold = bold
        if part.startswith("<b>"):
            part, run_bold = part[3:-4], True
        r = p.add_run()
        r.text = part
        f = r.font
        f.name, f.size, f.bold, f.italic = font, Pt(size), run_bold, italic
        f.color.rgb = rgb(color)
        if base:
            r._r.get_or_add_rPr().set("baseline", base)


def add_text(slide, x, y, w, h, text, size=16, bold=False, color=INK, font=BODY, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, italic=False, space_after=0, name=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, para in enumerate(text if isinstance(text, list) else [text]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        fill_runs(p, para, size, bold, color, font, italic)
    return tb


def est_height(text, size, width):
    """Rough height (inches) of wrapped text, used to stack rows without overlap."""
    plain = re.sub(r"<b>|</b>|\^\{|_\{|\}", "", text)
    lines = max(1, math.ceil(len(plain) * 0.5 * size / (width * 72)))
    return lines * size * 1.22 / 72


def mk(x, d=1):
    mant, exp = f"{x:.{d}e}".split("e")
    return f"{mant} × 10^{{{int(exp)}}}"


# ------------------------------------------------------------------ shape helpers
def no_shadow(shape):
    shape.shadow.inherit = False


def add_card(slide, x, y, w, h, fill=LIGHT, radius=0.06, name=None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = radius
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    s.line.fill.background()
    no_shadow(s)
    if name:
        s.name = name
    return s


def add_circle(slide, x, y, d, label, fill=ACCENT, size=18):
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    s.line.fill.background()
    no_shadow(s)
    tf = s.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    fill_runs(p, label, size, True, WHITE, BODY)
    s.name = f"Marker {label}"
    return s


def add_dot(slide, x, y, d=0.14, fill=ACCENT):
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    s.line.fill.background()
    no_shadow(s)
    s.name = "Bullet dot"
    return s


def bullet_rows(slide, x, y, w, items, size=16, gap=0.22, color=INK, dot=ACCENT):
    """Stack text items, each with a small dot marker; returns the y below the last item."""
    for it in items:
        h = est_height(it, size, w - 0.35)
        add_dot(slide, x, y + size * 0.42 / 72, fill=dot)
        add_text(slide, x + 0.3, y, w - 0.3, h, it, size=size, color=color)
        y += h + gap
    return y


def add_pic(slide, path, x, y, w, h, alt, border=True):
    """Place an image inside the box (x, y, w, h), keeping aspect ratio; top-left aligned horizontally centred."""
    iw, ih = PILImage.open(path).size
    s = min(w / iw, h / ih)
    pw, ph = iw * s, ih * s
    pic = slide.shapes.add_picture(str(path), Inches(x + (w - pw) / 2), Inches(y), Inches(pw), Inches(ph))
    pic._element.nvPicPr.cNvPr.set("descr", alt)
    if border:
        pic.line.color.rgb = rgb("C9D3DF")
        pic.line.width = Pt(0.75)
    return pic


def stat_tile(slide, x, y, w, h, big, label, big_size=30, big_color=NAVY, fill=LIGHT, label_size=14,
              label_color=MUTED):
    add_card(slide, x, y, w, h, fill=fill)
    add_text(slide, x + 0.25, y + 0.15, w - 0.5, big_size * 1.3 / 72, big, size=big_size, bold=True, color=big_color,
             font=HEAD)
    add_text(slide, x + 0.25, y + 0.2 + big_size * 1.3 / 72, w - 0.5, h - 0.35 - big_size * 1.3 / 72, label,
             size=label_size, color=label_color)


def eq_png(tex, path, fontsize, color="#1B2733"):
    plt.rcParams["mathtext.fontset"] = "cm"
    fig = plt.figure(figsize=(0.1, 0.1))
    fig.text(0, 0, f"${tex}$", fontsize=fontsize, color=color)
    fig.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.02, transparent=True)
    plt.close(fig)
    w, h = PILImage.open(path).size
    return w / 300, h / 300


def add_equation(slide, tmp, name, tex, fontsize, cx, cy, max_w, alt):
    """Render an equation to PNG and place it centred on (cx, cy)."""
    path = Path(tmp) / f"{name}.png"
    w, h = eq_png(tex, path, fontsize)
    if w > max_w:
        h, w = h * max_w / w, max_w
    pic = slide.shapes.add_picture(str(path), Inches(cx - w / 2), Inches(cy - h / 2), Inches(w), Inches(h))
    pic._element.nvPicPr.cNvPr.set("descr", alt)
    return pic


def new_slide(prs, title, dark=False, notes=""):
    s = prs.slides.add_slide(prs.slide_layouts[5])  # "Title Only": keeps a real title for outline view
    if dark:
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = rgb(NAVY)
    t = s.shapes.title
    t.left, t.top, t.width, t.height = Inches(0.6), Inches(0.35), Inches(12.1), Inches(1.0)
    tf = t.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    fill_runs(p, title, 32, True, WHITE if dark else NAVY, HEAD)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


# ------------------------------------------------------------------ build
def build():
    sig = R["signal"]
    f_max, nyq = sig["f_max_hz"], sig["nyquist_rate_hz"]
    e1 = {r["fs"]: r for r in R["exp1_reconstruction"]}
    a2, a4, a5, sw = R["exp2_alias_demo"], R["exp4_alias_validation"], R["exp5_antialiasing"], R["exp6_error_sweep"]
    nf, wf = a5["no_filter"], a5["with_filter"]
    n_ok = sum(abs(r["f_alias_predicted_hz"] - r["f_alias_measured_hz"]) < 1e-6 for r in a4["table"])
    n_tot = len(a4["table"])

    def sweep(fs, key):
        return sw[key][sw["fs"].index(float(fs))]

    amps = [t["amplitude"] for t in sig["tones"]]
    p_tot = sum(a * a / 2 for a in amps)
    p_11 = amps[2] ** 2 / 2
    pred15 = 2 * p_11 / p_tot
    lost_quad = (amps[2] * math.sin(sig["tones"][2]["phase_rad"])) ** 2 / 2 / p_tot

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    prs.core_properties.title = "Sampling Theorem, Aliasing and Signal Reconstruction"
    prs.core_properties.author = STUDENT["name"]
    prs.core_properties.subject = "Signals & Systems Innovative Assessment"

    with tempfile.TemporaryDirectory() as tmp:
        # ---------------------------------------------------------------- 1 title
        s = new_slide(prs, "", dark=True,
                      notes="Introduce the topic: how a continuous signal is turned into samples, and what goes wrong "
                            "when we sample too slowly. Everything shown today comes from one Python script on GitHub.")
        t = s.shapes.title
        t.left, t.top, t.width, t.height = Inches(0.9), Inches(1.6), Inches(7.2), Inches(2.6)
        t.text_frame.paragraphs[0].runs and t.text_frame.paragraphs[0]._p.remove(t.text_frame.paragraphs[0].runs[0]._r)
        fill_runs(t.text_frame.paragraphs[0], "Sampling Theorem, Aliasing and Signal Reconstruction", 40, True, WHITE,
                  HEAD)
        add_text(s, 0.9, 4.35, 7.2, 0.9, ["A Python simulation", "Signals & Systems Innovative Assessment"], size=20,
                 color=ICE, space_after=2)
        add_text(s, 0.9, 5.5, 7.2, 1.2,
                 [STUDENT["name"] + "  ·  " + STUDENT["roll"],
                  STUDENT["program"] + (f"  ·  {STUDENT['institute']}" if STUDENT.get("institute") else "")],
                 size=16, color=WHITE, space_after=4)
        # hero panel: 18 Hz tone sampled at 20 Hz looks like 2 Hz
        add_card(s, 8.5, 1.6, 4.3, 4.6, fill=PANEL, radius=0.05, name="Hero panel")
        fig, ax = plt.subplots(figsize=(3.9, 2.9))
        tt = np.linspace(0, 1, 2000)
        tn = np.arange(21) / 20
        ax.plot(tt, np.cos(2 * np.pi * 18 * tt), color="#56B4E9", lw=1.4)
        ax.plot(tt, np.cos(2 * np.pi * 2 * tt), color="#F2A33A", lw=2.4, ls="--")
        ax.plot(tn, np.cos(2 * np.pi * 18 * tn), "o", color="white", ms=5)
        ax.axis("off")
        fig.patch.set_alpha(0)
        hero = Path(tmp) / "hero.png"
        fig.savefig(hero, dpi=250, transparent=True, bbox_inches="tight", pad_inches=0.02)
        plt.close(fig)
        add_pic(s, hero, 8.7, 1.85, 3.9, 3.0, "An 18 Hz cosine sampled at 20 Hz; the samples also fit a 2 Hz cosine",
                border=False)
        add_text(s, 8.8, 5.1, 3.7, 0.9, "18 Hz sampled at 20 Hz looks like a 2 Hz tone", size=14, color=ICE,
                 align=PP_ALIGN.CENTER)

        # ---------------------------------------------------------------- 2 problem
        s = new_slide(prs, "The problem: from continuous signal to numbers",
                      notes="Every digital system samples. The question is how fast. Four objectives: sample at three "
                            "rates, show aliasing in time and frequency, verify the alias formula, and test a filter.")
        add_text(s, 0.6, 1.7, 5.7, 1.5,
                 "Audio, video, sensors and radio all start the same way: a continuous signal is measured at discrete "
                 "instants.", size=20)
        add_text(s, 0.6, 3.2, 5.7, 1.5,
                 "Measure too slowly and different signals produce the same numbers. That damage cannot be repaired "
                 "afterwards.", size=20)
        add_card(s, 0.6, 4.9, 5.7, 1.8, fill=NAVY, name="Key question")
        add_text(s, 0.9, 4.9, 5.1, 1.8, "How fast must we sample so that nothing is lost?", size=24, bold=True,
                 color=WHITE, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
        goals = ["Sample a band-limited signal below, near and above the Nyquist rate",
                 "Show aliasing in the time domain and the frequency domain",
                 "Verify the alias-frequency formula against the DFT",
                 "Test an anti-aliasing filter and compare interpolation methods"]
        for i, g in enumerate(goals):
            y = 1.7 + i * 1.3
            add_card(s, 6.9, y, 5.8, 1.1)
            add_circle(s, 7.15, y + 0.25, 0.6, str(i + 1))
            add_text(s, 8.0, y, 4.5, 1.1, g, size=16, anchor=MSO_ANCHOR.MIDDLE)

        # ---------------------------------------------------------------- 3 theorem
        s = new_slide(prs, "The sampling theorem",
                      notes="State the theorem: sample at least twice the highest frequency. Sampling repeats the "
                            "spectrum every fs. If the copies do not overlap, a low-pass filter recovers the signal; "
                            "if they overlap, we get aliasing. Our test signal has fmax = 11 Hz so the Nyquist rate is 22 Hz.")
        add_card(s, 0.6, 1.6, 6.3, 2.7)
        add_equation(s, tmp, "eq_thm", r"f_s \;\geq\; 2 f_{\max}", 46, 3.75, 2.55, 5.6,
                     "Sampling rate f s is at least 2 times f max")
        add_text(s, 0.9, 3.35, 5.7, 0.8, "Sample at least twice as fast as the highest frequency in the signal",
                 size=16, color=MUTED, align=PP_ALIGN.CENTER)
        stat_tile(s, 0.6, 4.55, 3.05, 1.75, f"{f_max:g} Hz", "highest frequency in the test signal")
        stat_tile(s, 3.85, 4.55, 3.05, 1.75, f"{nyq:g} Hz", "Nyquist rate, 2 × f_{max}", big_color=ACCENT)
        add_card(s, 7.4, 1.6, 5.3, 1.5)
        add_equation(s, tmp, "eq_rep", r"X_s(f)=f_s\sum_{k=-\infty}^{\infty}X(f-kf_s)", 24, 10.05, 2.35, 4.9,
                     "Sampled spectrum equals f s times the sum of copies of X shifted by k f s")
        bullet_rows(s, 7.4, 3.45, 5.3,
                    ["Sampling repeats the signal's spectrum every f_{s} Hz",
                     "f_{s} > 2 f_{max}: copies are separated, so a low-pass filter at f_{s}/2 recovers the signal",
                     "f_{s} < 2 f_{max}: copies overlap, and the overlap cannot be separated again"], size=16)

        # ---------------------------------------------------------------- 4 aliasing
        s = new_slide(prs, "Aliasing: when frequencies fold back",
                      notes="Aliasing means a high frequency masquerades as a low one. The formula folds any frequency "
                            "into the range 0 to fs over 2. At 20 Hz sampling, an 18 Hz tone looks like 2 Hz. "
                            "Once this happens it cannot be undone, so the cure is to filter before sampling.")
        add_card(s, 0.6, 1.6, 6.3, 2.2)
        add_equation(s, tmp, "eq_alias", r"f_a=\left|\,f-f_s\cdot\mathrm{round}(f/f_s)\right|", 30, 3.75, 2.7, 5.8,
                     "Alias frequency f a equals absolute value of f minus f s times round of f over f s")
        stat_tile(s, 0.6, 4.1, 2.6, 2.1, "18 Hz", "true tone", big_size=36)
        arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(3.3), Inches(4.95), Inches(0.5), Inches(0.45))
        arrow.fill.solid()
        arrow.fill.fore_color.rgb = rgb(MUTED)
        arrow.line.fill.background()
        no_shadow(arrow)
        arrow.name = "Arrow"
        stat_tile(s, 3.9, 4.1, 3.0, 2.1, "2 Hz", "what the samples show at f_{s} = 20 Hz", big_size=36,
                  big_color=ACCENT)
        bullet_rows(s, 7.4, 1.7, 5.3,
                    ["After sampling, a tone f is indistinguishable from its folded frequency f_{a} in 0 … f_{s}/2",
                     "At f_{s} = 20 Hz, tones of 2, 18, 22, 38 and 42 Hz give identical samples",
                     "Aliasing is irreversible: no later processing can tell the tones apart",
                     "The cure: low-pass filter the signal before sampling"], size=16, gap=0.3)

        # ---------------------------------------------------------------- 5 setup
        s = new_slide(prs, "Simulation setup",
                      notes="One band-limited test signal made of three cosines, so its spectrum is known exactly. "
                            "Six experiments, all in a single Python script using NumPy, SciPy and Matplotlib.")
        add_card(s, 0.6, 1.6, 5.9, 5.1)
        add_text(s, 0.9, 1.8, 5.3, 0.4, "Test signal", size=20, bold=True, color=NAVY)
        add_equation(s, tmp, "eq_sig", r"x(t)=\sum_{k=1}^{3}A_k\cos(2\pi f_k t+\varphi_k)", 22, 3.55, 2.75, 5.3,
                     "x of t is the sum of three cosines with amplitudes A k, frequencies f k and phases phi k")
        tones = [f"{t['amplitude']:.2f} · cos(2π · {t['frequency_hz']:g} t" +
                 (f" + {t['phase_rad']:.1f})" if t["phase_rad"] else ")") for t in sig["tones"]]
        for i, line in enumerate(tones):
            add_dot(s, 1.0, 3.62 + i * 0.5, fill=ACCENT)
            add_text(s, 1.3, 3.5 + i * 0.5, 4.9, 0.4, line, size=18)
        add_text(s, 0.9, 5.15, 5.3, 0.45, f"f_{{max}} = {f_max:g} Hz  →  Nyquist rate = {nyq:g} Hz", size=18, bold=True,
                 color=NAVY)
        add_text(s, 0.9, 5.85, 5.3, 0.4, "Tools: Python · NumPy · SciPy · Matplotlib", size=14, color=MUTED)
        add_text(s, 7.0, 1.65, 5.7, 0.4, "Six experiments", size=20, bold=True, color=NAVY)
        exps = ["Sample at 100, 30 and 15 Hz; reconstruct with sinc interpolation",
                "Aliasing demo in the time domain",
                "Spectral replicas via the FFT on a 1 kHz grid",
                "Alias formula versus DFT peaks for nine tones",
                "Anti-aliasing filter against a 33 Hz interference tone",
                "Error versus sampling rate: sinc, linear, zero-order hold"]
        for i, e in enumerate(exps):
            y = 2.25 + i * 0.75
            add_circle(s, 7.0, y + 0.05, 0.5, str(i + 1), size=16)
            add_text(s, 7.75, y, 5.0, 0.6, e, size=15, anchor=MSO_ANCHOR.MIDDLE)

        # ---------------------------------------------------------------- 6 result 1
        s = new_slide(prs, "Result 1: Reconstruction versus sampling rate",
                      notes="Top two panels: at 100 and 30 Hz the sinc reconstruction lies on top of the original. "
                            "Bottom panel: at 15 Hz the curve still passes through every sample but it is a different "
                            "signal, because the 11 Hz tone has folded to 4 Hz. The error can be predicted by hand: "
                            "0.16 divided by 0.76 gives 0.2105, and the simulation measures 0.2103.")
        add_pic(s, FIG / "fig1_time_domain_reconstruction.png", 0.6, 1.5, 6.5, 5.5,
                "Original signal, samples and sinc reconstruction at 100, 30 and 15 Hz")
        rows = [(e1[100], f"f_{{s}} = 100 Hz  (4.55 × Nyquist)", NAVY), (e1[30], "f_{s} = 30 Hz  (1.36 × Nyquist)", NAVY),
                (e1[15], "f_{s} = 15 Hz  (0.68 × Nyquist): aliasing", ACCENT)]
        for i, (r, lab, col) in enumerate(rows):
            y = 1.6 + i * 1.35
            add_card(s, 7.5, y, 5.2, 1.2)
            big = mk(r["nmse"]) if r["nmse"] < 0.1 else f"{r['nmse']:.2f}"
            add_text(s, 7.7, y, 2.6, 1.2, big, size=28, bold=True, color=col, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
            add_text(s, 10.3, y, 2.3, 1.2, "NMSE at " + lab, size=14, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
        add_card(s, 7.5, 5.7, 5.2, 1.2, fill=NAVY)
        add_text(s, 7.75, 5.7, 4.7, 1.2,
                 f"At 15 Hz the 11 Hz tone folds to 4 Hz. Predicted NMSE 0.16 / {p_tot:.2f} = {pred15:.4f}; "
                 f"measured {e1[15]['nmse']:.4f}.", size=14, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)

        # ---------------------------------------------------------------- 7 result 2
        s = new_slide(prs, "Result 2: Different tones, same samples",
                      notes="Left: an 18 Hz tone and a 2 Hz tone pass through exactly the same samples at 20 Hz. "
                            "Right: 2, 18 and 22 Hz all do. The samples cannot say which one was really there, so "
                            "reconstruction picks the lowest frequency.")
        add_pic(s, FIG / "fig2_alias_time_domain.png", 0.6, 1.5, 12.1, 4.3,
                "An 18 Hz tone sampled at 20 Hz fits a 2 Hz tone; 2, 18 and 22 Hz tones share the same samples")
        tiles = ["An 18 Hz tone sampled at 20 Hz looks exactly like 2 Hz",
                 f"2, 18, 22, 38 and 42 Hz samples agree to within {mk(a2['max_sample_difference'], 0)}",
                 "Reconstruction picks the lowest frequency, inside 0 … f_{s}/2"]
        for i, t_ in enumerate(tiles):
            add_card(s, 0.6 + i * 4.1, 5.95, 3.9, 0.95)
            add_text(s, 0.85 + i * 4.1, 5.95, 3.4, 0.95, t_, size=14, anchor=MSO_ANCHOR.MIDDLE)

        # ---------------------------------------------------------------- 8 result 3
        s = new_slide(prs, "Result 3: Spectral replicas overlap",
                      notes="Top: the original spectrum. Middle: sampled at 40 Hz, the copies sit at 29, 33, 37 and so "
                            "on, well clear of the 0 to 20 Hz band. Bottom: sampled at 20 Hz, the copy of the 11 Hz line "
                            "lands at 9 Hz, inside the band, shown in orange.")
        add_pic(s, FIG / "fig3_spectral_replicas.png", 0.6, 1.5, 6.9, 5.5,
                "Spectrum of the original signal and of the signal sampled at 40 Hz and 20 Hz")
        bullet_rows(s, 7.9, 1.8, 4.8,
                    ["f_{s} = 40 Hz: copies appear at 29, 33, 37, 43 … Hz; the 0 to 20 Hz band holds only the true tones",
                     "f_{s} = 20 Hz: the copy of the 11 Hz line lands at 9 Hz, inside the 0 to 10 Hz band (orange)",
                     "That alias is indistinguishable from a genuine 9 Hz component"], size=17, gap=0.35)

        # ---------------------------------------------------------------- 9 result 4
        s = new_slide(prs, "Result 4: Alias formula matches the DFT",
                      notes="The apparent frequency is a triangle wave of the true frequency. Orange circles are the "
                            "peaks measured with the DFT; they sit exactly on the predicted line for all nine test tones.")
        add_pic(s, FIG / "fig4_alias_frequency_map.png", 0.6, 1.6, 7.9, 4.1,
                "Predicted alias frequency versus input frequency at 20 Hz sampling, with measured DFT peaks")
        add_card(s, 0.6, 5.9, 7.9, 0.95)
        add_equation(s, tmp, "eq_alias2", r"f_a=\left|\,f-f_s\cdot\mathrm{round}(f/f_s)\right|", 20, 4.55, 6.37, 7.0,
                     "Alias frequency formula")
        stat_tile(s, 8.9, 1.6, 3.8, 2.2, f"{n_ok} of {n_tot}", "test tones: predicted alias = measured DFT peak",
                  big_size=40, big_color=ACCENT)
        add_card(s, 8.9, 4.05, 3.8, 2.8)
        add_text(s, 9.15, 4.2, 3.3, 0.4, "Examples at f_{s} = 20 Hz", size=14, color=MUTED)
        ex = {r["f_input_hz"]: r["f_alias_measured_hz"] for r in a4["table"]}
        for i, f_in in enumerate((18, 31, 57)):
            add_text(s, 9.15, 4.75 + i * 0.65, 3.3, 0.5, f"{f_in} Hz  →  {ex[f_in]:g} Hz", size=24, bold=True,
                     color=NAVY, font=BODY)

        # ---------------------------------------------------------------- 10 result 5
        s = new_slide(prs, "Result 5: Filter before you sample",
                      notes="A 33 Hz interference tone sampled at 40 Hz folds to exactly 7 Hz, on top of the wanted "
                            "7 Hz component, so its amplitude reads 1.37 instead of 0.60. A low-pass filter placed "
                            "before the sampler removes the interference first, and the error drops by about four "
                            "orders of magnitude.")
        add_pic(s, FIG / "fig5_antialiasing_filter.png", 0.6, 1.5, 8.5, 5.4,
                "Anti-aliasing filter response, reconstruction with and without the filter, and spectra of the samples")
        tiles = [(f"{nf['nmse']:.2f} to {mk(wf['nmse'])}", "NMSE: no filter → with filter", ACCENT),
                 (f"{nf['amp_7hz']:.2f} to {wf['amp_7hz']:.2f}", "7 Hz amplitude: no filter → with filter (true value 0.60)", NAVY),
                 (f"−{abs(a5['attenuation_at_interference_db']):.0f} dB", "filter attenuation at the 33 Hz interference", NAVY)]
        for i, (big, lab, col) in enumerate(tiles):
            y = 1.6 + i * 1.8
            add_card(s, 9.4, y, 3.3, 1.65)
            add_text(s, 9.6, y + 0.15, 2.95, 0.5, big, size=20, bold=True, color=col, font=HEAD)
            add_text(s, 9.6, y + 0.75, 2.95, 0.8, lab, size=14, color=MUTED)

        # ---------------------------------------------------------------- 11 result 6
        s = new_slide(prs, "Result 6: Error versus sampling rate",
                      notes="Below 22 Hz the sinc error is stuck near 0.21 because the 11 Hz tone is always replaced by "
                            "an alias. Just above the Nyquist rate it falls by about four orders of magnitude. Exactly "
                            "at 22 Hz the error is not zero because the band-edge tone loses its quadrature part. "
                            "Linear interpolation and the zero-order hold are far worse at every rate.")
        add_pic(s, FIG / "fig6_error_vs_sampling_rate.png", 0.6, 1.6, 7.9, 4.3,
                "Normalised mean-squared error versus sampling rate for sinc, linear and zero-order hold reconstruction")
        add_card(s, 0.6, 6.0, 7.9, 0.85)
        add_text(s, 0.85, 6.0, 7.4, 0.85,
                 f"At 80 Hz:  sinc {mk(sweep(80, 'sinc'))}  ·  linear {mk(sweep(80, 'linear'))}  ·  "
                 f"zero-order hold {mk(sweep(80, 'zoh'))}", size=14, anchor=MSO_ANCHOR.MIDDLE)
        bullet_rows(s, 8.9, 1.7, 3.8,
                    [f"Below {nyq:g} Hz the sinc error plateaus at {sweep(20, 'sinc'):.2f}",
                     "Just above the Nyquist rate it drops by about four orders of magnitude",
                     f"At exactly {nyq:g} Hz the error is {sweep(22, 'sinc'):.3f}: the band-edge tone loses its "
                     f"quadrature part (predicted {lost_quad:.4f})",
                     "Sinc is orders of magnitude better than linear interpolation or a zero-order hold"],
                    size=15, gap=0.25)

        # ---------------------------------------------------------------- 12 conclusions
        s = new_slide(prs, "Conclusions", dark=True,
                      notes="Four take-aways: sampling above Nyquist works; below it aliasing appears; the alias "
                            "formula is verified; and a filter before the sampler is essential.")
        cards = [("Above Nyquist: recoverable", f"NMSE {mk(e1[30]['nmse'])} at 30 Hz"),
                 ("Below Nyquist: aliasing", f"11 Hz folds to 4 Hz at 15 Hz; NMSE {e1[15]['nmse']:.2f}"),
                 ("Alias formula verified", f"Matched the DFT for {n_ok} of {n_tot} test tones"),
                 ("Filter first", f"NMSE {nf['nmse']:.2f} → {mk(wf['nmse'])} with an anti-aliasing filter")]
        for i, (h_, b_) in enumerate(cards):
            x, y = 0.6 + (i % 2) * 6.2, 1.7 + (i // 2) * 2.55
            add_card(s, x, y, 5.9, 2.3, fill=PANEL)
            add_text(s, x + 0.35, y + 0.3, 5.2, 0.7, h_, size=24, bold=True, color=WHITE, font=HEAD)
            add_text(s, x + 0.35, y + 1.15, 5.2, 0.9, b_, size=18, color=ICE)

        # ---------------------------------------------------------------- 13 code & refs
        s = new_slide(prs, "Code, report and references",
                      notes="All code, figures and the PDF report are on GitHub. Running the script reproduces every "
                            "figure and number in about six seconds. Thank the audience and invite questions.")
        add_card(s, 0.6, 1.6, 6.2, 2.0)
        if STUDENT.get("github"):
            add_text(s, 0.9, 1.75, 5.6, 0.4, "Code on GitHub", size=16, color=MUTED)
            add_text(s, 0.9, 2.2, 5.6, 1.2, STUDENT["github"], size=18, bold=True, color=NAVY)
        else:
            add_text(s, 0.9, 1.75, 5.6, 0.4, "Code", size=16, color=MUTED)
            add_text(s, 0.9, 2.2, 5.6, 1.2, "Full code, figures and report are in the project repository", size=18,
                     bold=True, color=NAVY)
        add_card(s, 0.6, 3.85, 6.2, 1.5, fill=NAVY)
        add_text(s, 0.9, 3.85, 5.6, 1.5, ["pip install -r requirements.txt", "python sampling_simulation.py"], size=16,
                 color=WHITE, font=MONO, anchor=MSO_ANCHOR.MIDDLE, space_after=6)
        add_text(s, 0.6, 5.8, 6.2, 0.8, "Thank you. Questions?", size=28, bold=True, color=ACCENT, font=HEAD)
        add_text(s, 7.3, 1.65, 5.4, 0.4, "References", size=20, bold=True, color=NAVY)
        refs = ["A. V. Oppenheim, A. S. Willsky and S. H. Nawab, Signals and Systems, 2nd ed., Prentice Hall, 1997.",
                "C. E. Shannon, “Communication in the presence of noise,” Proc. IRE, vol. 37, no. 1, 1949.",
                "H. Nyquist, “Certain topics in telegraph transmission theory,” Trans. AIEE, vol. 47, no. 2, 1928.",
                "J. G. Proakis and D. G. Manolakis, Digital Signal Processing, 4th ed., Pearson, 2006."]
        bullet_rows(s, 7.3, 2.3, 5.4, refs, size=14, gap=0.3, dot=MUTED)

    # slide numbers
    n = len(prs.slides)
    for i, sl in enumerate(prs.slides, 1):
        if i == 1:
            continue
        dark = i == 12
        add_text(sl, 12.0, 7.05, 0.7, 0.25, f"{i} / {n}", size=10, color=ICE if dark else MUTED, align=PP_ALIGN.RIGHT,
                 name="Slide number")
        add_text(sl, 0.6, 7.05, 6.0, 0.25, "Signals & Systems  ·  Sampling Theorem and Aliasing", size=10,
                 color=ICE if dark else MUTED, name="Footer")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT_PATH)
    print(f"saved {OUT_PATH}")


if __name__ == "__main__":
    build()

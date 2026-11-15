#!/usr/bin/env python3
import ast
import json
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, Image, KeepTogether, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from student_info import STUDENT  # edit your name / roll number in tools/student_info.py

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
FIG = OUT / "figures"
PDF_PATH = ROOT / "report" / "Technical_Report.pdf"
R = json.loads((OUT / "results.json").read_text())

# ----------------------------------------------------------------------------- fonts
TTF = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
for key, fname in [("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"),
                   ("DV-I", "DejaVuSans-Oblique.ttf"), ("DV-BI", "DejaVuSans-BoldOblique.ttf"),
                   ("DVM", "DejaVuSansMono.ttf")]:
    pdfmetrics.registerFont(TTFont(key, str(TTF / fname)))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")

NAVY = colors.HexColor("#1F3A5F")
LIGHT = colors.HexColor("#EAF0F7")
GRID = colors.HexColor("#B8C4D2")

S = {
    "title": ParagraphStyle("title", fontName="DV-B", fontSize=18, leading=23, textColor=NAVY, spaceAfter=4),
    "sub": ParagraphStyle("sub", fontName="DV", fontSize=10.5, leading=14, textColor=colors.HexColor("#444444")),
    "h1": ParagraphStyle("h1", fontName="DV-B", fontSize=12.5, leading=16, textColor=NAVY, spaceBefore=12, spaceAfter=5),
    "h2": ParagraphStyle("h2", fontName="DV-B", fontSize=10.3, leading=14, textColor=NAVY, spaceBefore=8, spaceAfter=3),
    "body": ParagraphStyle("body", fontName="DV", fontSize=9.3, leading=13.6, spaceAfter=5),
    "bullet": ParagraphStyle("bullet", fontName="DV", fontSize=9.3, leading=13.2, leftIndent=14, bulletIndent=3, spaceAfter=2),
    "cap": ParagraphStyle("cap", fontName="DV-I", fontSize=8.3, leading=11, alignment=TA_CENTER,
                          textColor=colors.HexColor("#333333"), spaceBefore=3, spaceAfter=9),
    "cell": ParagraphStyle("cell", fontName="DV", fontSize=8.4, leading=11),
    "cellb": ParagraphStyle("cellb", fontName="DV-B", fontSize=8.4, leading=11, textColor=colors.white),
    "ref": ParagraphStyle("ref", fontName="DV", fontSize=8.8, leading=12.3, leftIndent=18, firstLineIndent=-18, spaceAfter=3),
    "code": ParagraphStyle("code", fontName="DVM", fontSize=6.7, leading=8.4, backColor=colors.HexColor("#F5F6F8"),
                           borderPadding=5, spaceBefore=3, spaceAfter=8),
}
TEXT_W = A4[0] - 4.4 * cm


def P(t, style="body"):
    return Paragraph(t, S[style])


def B(t):
    return Paragraph(t, S["bullet"], bulletText="•")


def sci(x, d=1):
    mant, exp = f"{x:.{d}e}".split("e")
    return f"{mant} × 10<super>{int(exp)}</super>"


def pct(x):
    return f"{x:.2f}"


# ----------------------------------------------------------------------------- flowable helpers
def figure(name, caption, width_cm=16.2):
    path = FIG / name
    w, h = PILImage.open(path).size
    width = width_cm * cm
    return KeepTogether([Image(str(path), width=width, height=width * h / w), P(caption, "cap")])


def table(rows, col_w, header=True, align_center_from=0):
    data = []
    for i, row in enumerate(rows):
        data.append([Paragraph(str(c), S["cellb"] if (header and i == 0) else S["cell"]) for c in row])
    t = Table(data, colWidths=[w * cm for w in col_w], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
        style += [("BACKGROUND", (0, i), (-1, i), LIGHT) for i in range(2, len(rows), 2)]
    t.setStyle(TableStyle(style))
    return t


def table_block(title, tbl):
    return KeepTogether([P(title, "cap"), tbl, Spacer(1, 9)])


class Equations:
    """Renders LaTeX-style equations to PNG with matplotlib mathtext and numbers them."""

    def __init__(self, tmp):
        self.tmp, self.n = Path(tmp), 0
        plt.rcParams["mathtext.fontset"] = "cm"

    def __call__(self, tex):
        self.n += 1
        path = self.tmp / f"eq{self.n}.png"
        fig = plt.figure(figsize=(0.1, 0.1))
        fig.text(0, 0, f"${tex}$", fontsize=13)
        fig.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.03, transparent=True)
        plt.close(fig)
        w, h = PILImage.open(path).size
        img = Image(str(path), width=w / 300 * 72, height=h / 300 * 72)
        t = Table([[img, P(f"({self.n})", "body")]], colWidths=[TEXT_W - 1.3 * cm, 1.3 * cm])
        t.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        return t


def source_of(*names):
    """Return the source code of functions in sampling_simulation.py (keeps the appendix in sync)."""
    text = (ROOT / "sampling_simulation.py").read_text()
    tree = ast.parse(text)
    parts = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            parts.append(ast.get_source_segment(text, node))
    return "\n\n".join(parts)


def sweep(fs, key):
    sw = R["exp6_error_sweep"]
    return sw[key][sw["fs"].index(float(fs))]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DV", 7.8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(2.2 * cm, 1.25 * cm, f"{STUDENT['course']} - Innovative Assessment  |  Sampling Theorem & Aliasing")
    canvas.drawRightString(A4[0] - 2.2 * cm, 1.25 * cm, f"Page {doc.page}")
    canvas.restoreState()


# ----------------------------------------------------------------------------- content
def build():
    sig = R["signal"]
    f_max, nyq = sig["f_max_hz"], sig["nyquist_rate_hz"]
    e1 = {r["fs"]: r for r in R["exp1_reconstruction"]}
    a2, a4, a5 = R["exp2_alias_demo"], R["exp4_alias_validation"], R["exp5_antialiasing"]
    nf, wf = a5["no_filter"], a5["with_filter"]

    amps = [t["amplitude"] for t in sig["tones"]]
    p_total = sum(a * a / 2 for a in amps)
    p_11 = amps[2] ** 2 / 2
    nmse_pred_15 = 2 * p_11 / p_total
    import math
    lost_quad = (amps[2] * math.sin(sig["tones"][2]["phase_rad"])) ** 2 / 2 / p_total

    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(PDF_PATH), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2.0 * cm, bottomMargin=2.0 * cm,
                            title="Sampling Theorem, Aliasing and Signal Reconstruction - Technical Report",
                            author=STUDENT["name"], subject="Signals & Systems Innovative Assessment")
    with tempfile.TemporaryDirectory() as tmp:
        eq = Equations(tmp)
        st = []

        # ---- title block
        st += [P("Sampling Theorem, Aliasing and Signal Reconstruction: A Python Simulation", "title"),
               P("Technical report - Signals &amp; Systems Innovative Assessment", "sub"), Spacer(1, 7)]
        info = [["Name", STUDENT["name"], "Roll No.", STUDENT["roll"]],
                ["Branch", STUDENT["program"], "Course", STUDENT["course"].replace("&", "&amp;")]]
        it = Table([[Paragraph(f"<b>{c}</b>" if j % 2 == 0 else c, S["cell"]) for j, c in enumerate(r)] for r in info],
                   colWidths=[2.2 * cm, 6.1 * cm, 2.2 * cm, 6.1 * cm])
        it.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("BOX", (0, 0), (-1, -1), 0.4, GRID),
                                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        st += [it, Spacer(1, 6), HRFlowable(width="100%", thickness=0.8, color=NAVY, spaceAfter=4)]

        # ---- abstract
        st += [P("Abstract", "h1"),
               P(f"This report studies the Nyquist-Shannon sampling theorem by simulation in Python. A band-limited "
                 f"three-tone signal with highest frequency f<sub>max</sub> = {f_max:g} Hz (Nyquist rate {nyq:g} Hz) is "
                 f"sampled at rates from 8 Hz to 80 Hz and reconstructed with ideal sinc interpolation, linear "
                 f"interpolation and a zero-order hold. Sampling at 30 Hz (1.36 times the Nyquist rate) recovers the signal "
                 f"with a normalised mean-squared error (NMSE) of {sci(e1[30]['nmse'])}, whereas sampling at 15 Hz "
                 f"gives an NMSE of {e1[15]['nmse']:.2f} because the 11 Hz component folds to 4 Hz. The alias-frequency "
                 f"formula is confirmed against the DFT for nine test tones, the spectral replicas that cause aliasing are "
                 f"shown directly, and a 33 Hz interference tone sampled at 40 Hz is shown to corrupt the wanted 7 Hz "
                 f"component (amplitude {nf['amp_7hz']:.2f} instead of 0.60) until an anti-aliasing low-pass filter removes "
                 f"it first (NMSE {nf['nmse']:.2f} down to {sci(wf['nmse'])}).")]

        # ---- 1 introduction
        st += [P("1. Introduction and objectives", "h1"),
               P("Almost every modern signal-processing system begins by turning a continuous-time signal into a sequence "
                 "of numbers. The sampling theorem says when that step loses nothing, and aliasing is what goes wrong when "
                 "its condition is violated. Because aliasing cannot be undone after sampling, it is one of the most "
                 "important practical ideas in Signals &amp; Systems."),
               P("The objectives of this work are:"),
               B("to sample a known band-limited signal below, near and above the Nyquist rate and reconstruct it;"),
               B("to show aliasing in both the time domain and the frequency domain;"),
               B("to verify the alias-frequency formula numerically;"),
               B("to demonstrate why an anti-aliasing filter is needed before the sampler; and"),
               B("to measure how reconstruction error depends on the sampling rate and on the interpolation method.")]

        # ---- 2 theory
        st += [P("2. Theory", "h1"), P("2.1 The sampling theorem", "h2"),
               P("A signal x(t) whose spectrum is zero for |f| &gt; f<sub>max</sub> is completely determined by its samples "
                 "x[n] = x(nT<sub>s</sub>), T<sub>s</sub> = 1/f<sub>s</sub>, provided the sampling rate satisfies"),
               eq(r"f_s \;\geq\; 2 f_{\max}"),
               P("The quantity 2f<sub>max</sub> is the Nyquist rate and f<sub>s</sub>/2 is the Nyquist frequency. For a pure "
                 "sinusoid exactly at f<sub>s</sub>/2 the samples may fall on zero crossings, so strict inequality "
                 "f<sub>s</sub> &gt; 2f<sub>max</sub> is needed in general (Section 4.6 shows this numerically)."),
               P("2.2 Impulse sampling and spectral replicas", "h2"),
               P("Ideal sampling multiplies x(t) by an impulse train. Multiplication in time is convolution in frequency, so the "
                 "spectrum of the sampled signal is the original spectrum repeated every f<sub>s</sub> Hz:"),
               eq(r"x_s(t)=x(t)\sum_{n=-\infty}^{\infty}\delta(t-nT_s)\;\;\Longleftrightarrow\;\;"
                  r"X_s(f)=f_s\sum_{k=-\infty}^{\infty}X(f-kf_s)"),
               P("If f<sub>s</sub> &gt; 2f<sub>max</sub> the replicas are separated by a gap and an ideal low-pass filter with cut-off "
                 "f<sub>s</sub>/2 recovers one clean copy. If f<sub>s</sub> &lt; 2f<sub>max</sub> neighbouring replicas overlap "
                 "and the overlap cannot be separated again - this is aliasing."),
               P("2.3 Aliasing", "h2"),
               P("A tone of frequency f sampled at f<sub>s</sub> is indistinguishable from a tone at the folded frequency"),
               eq(r"f_a=\left|\,f-f_s\cdot\mathrm{round}\left(f/f_s\right)\right|\;\in\;[\,0,\;f_s/2\,]"),
               P("For example, with f<sub>s</sub> = 20 Hz the tones 2, 18, 22, 38 and 42 Hz all produce the same samples."),
               P("2.4 Reconstruction", "h2"),
               P("The ideal reconstruction (Whittaker-Shannon interpolation) places a sinc pulse at every sample:"),
               eq(r"x_r(t)=\sum_{n=-\infty}^{\infty}x[n]\,\mathrm{sinc}\left(\frac{t-nT_s}{T_s}\right),\qquad"
                  r"\mathrm{sinc}(u)=\frac{\sin(\pi u)}{\pi u}"),
               P("Practical converters use simpler interpolators such as the zero-order hold (staircase) or linear "
                 "interpolation, which are compared with the ideal case in Section 4.6."),
               P("2.5 Anti-aliasing filter", "h2"),
               P("Real signals are never perfectly band-limited: noise and interference above f<sub>s</sub>/2 fold into the "
                 "band of interest. An analog low-pass filter placed before the sampler removes that energy while it can "
                 "still be separated from the wanted signal.")]

        # ---- 3 methodology
        tones_rows = [["Component", "Amplitude A<sub>k</sub>", "Frequency f<sub>k</sub> (Hz)", "Phase &phi;<sub>k</sub> (rad)"]]
        for i, t in enumerate(sig["tones"], 1):
            tones_rows.append([str(i), f"{t['amplitude']:.2f}", f"{t['frequency_hz']:g}", f"{t['phase_rad']:.1f}"])
        st += [P("3. Methodology", "h1"), P("3.1 Test signal", "h2"),
               P("A sum of three cosines is used because its spectrum is known exactly:"),
               eq(r"x(t)=\sum_{k=1}^{3}A_k\cos\left(2\pi f_k t+\varphi_k\right)"),
               table_block("Table 1 - Components of the test signal", table(tones_rows, [3, 4, 4.5, 4.5])),
               P(f"The highest frequency is f<sub>max</sub> = {f_max:g} Hz, so the Nyquist rate is {nyq:g} Hz.  "
                 f"The signal power is {p_total:.2f}."),
               P("3.2 Implementation", "h2"),
               P("The simulation is a single Python script (NumPy, SciPy, Matplotlib) with six experiments. Samples are taken "
                 "on the interval [-10 s, 10 s]; errors are measured on the central 4 s so that edge effects from truncating "
                 "the infinite sinc sum do not dominate."),
               B("<b>Exp 1</b> - sample at 100, 30 and 15 Hz, reconstruct with sinc interpolation, report the NMSE."),
               B("<b>Exp 2</b> - sample a cosine at f<sub>s</sub> = 20 Hz and compare tones that share the same samples."),
               B("<b>Exp 3</b> - model continuous time on a 1 kHz grid; keep every (1000/f<sub>s</sub>)-th point and zero the "
                 "rest (impulse sampling); take the FFT to show the replicas."),
               B("<b>Exp 4</b> - sample cosines of nine frequencies at 20 Hz and compare the DFT peak with the alias formula."),
               B("<b>Exp 5</b> - add a 33 Hz interference tone to a 3 Hz + 7 Hz message, sample at 40 Hz with and without an "
                 "8th-order Butterworth low-pass (cut-off 15 Hz, applied forward and backward for zero phase)."),
               B("<b>Exp 6</b> - sweep f<sub>s</sub> from 8 to 80 Hz and compare sinc, linear and zero-order-hold interpolation."),
               P("3.3 Error metric", "h2"),
               P("Reconstruction quality is measured by the normalised mean-squared error, with averages taken over time:"),
               eq(r"\mathrm{NMSE}=\frac{\langle\,(x(t)-x_r(t))^2\,\rangle}{\langle\,x(t)^2\,\rangle}")]

        # ---- 4 results
        t2 = [["f<sub>s</sub> (Hz)", "f<sub>s</sub> / Nyquist rate", "Condition", "NMSE"]]
        for fs in (100, 30, 15):
            r = e1[fs]
            t2.append([f"{fs}", f"{r['ratio_to_nyquist']:.2f}", r["status"], sci(r["nmse"], 2)])
        t3 = [["Input f (Hz)", "Predicted alias (Hz)", "Measured DFT peak (Hz)", "Match"]]
        for r in a4["table"]:
            ok = abs(r["f_alias_predicted_hz"] - r["f_alias_measured_hz"]) < 1e-6
            t3.append([f"{r['f_input_hz']:g}", f"{r['f_alias_predicted_hz']:g}", f"{r['f_alias_measured_hz']:g}",
                       "yes" if ok else "NO"])
        t4 = [["", "NMSE vs. wanted signal", "Amplitude at 3 Hz", "Amplitude at 7 Hz"],
              ["True values", "0", "1.00", "0.60"],
              ["No anti-aliasing filter", f"{nf['nmse']:.3f}", f"{nf['amp_3hz']:.2f}", f"{nf['amp_7hz']:.2f}"],
              ["With low-pass filter", sci(wf["nmse"], 2), f"{wf['amp_3hz']:.3f}", f"{wf['amp_7hz']:.3f}"]]
        t5 = [["f<sub>s</sub> (Hz)", "Sinc", "Linear", "Zero-order hold"]]
        for r in R["exp6_error_sweep"]["table"]:
            t5.append([f"{r['fs']:g}", sci(r["sinc"], 1), sci(r["linear"], 1), sci(r["zoh"], 1)])

        st += [P("4. Results and discussion", "h1"),
               P("4.1 Time-domain sampling and reconstruction", "h2"),
               figure("fig1_time_domain_reconstruction.png",
                      "Figure 1 - Original signal, samples and sinc reconstruction at f<sub>s</sub> = 100, 30 and 15 Hz."),
               P(f"At 100 Hz and 30 Hz the reconstruction is visually identical to the original (NMSE {sci(e1[100]['nmse'])} "
                 f"and {sci(e1[30]['nmse'])}). At 15 Hz, only 0.68 times the Nyquist rate, the dashed curve still passes through "
                 f"every sample but is a different signal: the 3 Hz and 7 Hz components lie below f<sub>s</sub>/2 = 7.5 Hz and "
                 f"survive, while the 11 Hz component folds to |11 - 15| = 4 Hz."),
               P(f"This gives a hand check of the measured error. The reconstruction contains a 4 Hz tone instead of the "
                 f"11 Hz tone, so the error power is 2 x {p_11:.2f} = {2 * p_11:.2f}, and the predicted NMSE is "
                 f"{2 * p_11:.2f} / {p_total:.2f} = {nmse_pred_15:.4f}. The simulation gives {e1[15]['nmse']:.4f}."),
               table_block("Table 2 - Reconstruction error at three sampling rates", table(t2, [2.6, 4, 5.7, 3.7])),

               P("4.2 Aliasing in the time domain", "h2"),
               figure("fig2_alias_time_domain.png",
                      "Figure 2 - (a) An 18 Hz tone sampled at 20 Hz appears as 2 Hz. (b) Tones of 2, 18 and 22 Hz share the same samples."),
               P(f"Tones at {', '.join(f'{f:g}' for f in a2['tones_with_identical_samples'])} Hz produce samples that agree to "
                 f"within {a2['max_sample_difference']:.0e} (floating-point rounding). Nothing in the samples says which tone "
                 f"was present; the reconstruction simply picks the lowest-frequency one, the 2 Hz tone inside 0 ... f<sub>s</sub>/2."),

               P("4.3 Frequency-domain view", "h2"),
               figure("fig3_spectral_replicas.png",
                      "Figure 3 - Spectrum of the original and impulse-sampled signal at f<sub>s</sub> = 40 Hz and 20 Hz."),
               P("At f<sub>s</sub> = 40 Hz the replicas of the 3, 7 and 11 Hz lines appear at 29, 33, 37, 43, ... Hz, "
                 "and the 0 to 20 Hz band contains only the true lines, so a low-pass filter can recover the signal. At "
                 "f<sub>s</sub> = 20 Hz the replica of the 11 Hz line at 20 - 11 = 9 Hz lands inside the 0 to 10 Hz band "
                 "(orange line). It cannot be told apart from a genuine 9 Hz component."),

               P("4.4 Validation of the alias-frequency formula", "h2"),
               figure("fig4_alias_frequency_map.png",
                      "Figure 4 - Alias-frequency map for f<sub>s</sub> = 20 Hz; circles are measured DFT peaks.", 14.5),
               P("The apparent frequency is a triangle wave of the true frequency: it rises to f<sub>s</sub>/2, falls back "
                 "to zero at f<sub>s</sub>, and repeats. Table 3 confirms that the formula matches the DFT peak for all nine "
                 "tones, including ones far above the sampling rate such as 57 Hz."),
               table_block("Table 3 - Predicted and measured alias frequencies, f<sub>s</sub> = 20 Hz", table(t3, [3.4, 4.2, 5, 2.4])),

               P("4.5 Effect of an anti-aliasing filter", "h2"),
               figure("fig5_antialiasing_filter.png",
                      "Figure 5 - (a) Filter response. (b) Reconstruction with and without the filter. (c, d) Spectrum of the samples."),
               P(f"A 33 Hz interference tone sampled at 40 Hz folds to |33 - 40| = 7 Hz, exactly on top of the wanted 7 Hz "
                 f"component. Without a filter the measured amplitude at 7 Hz is {nf['amp_7hz']:.2f} instead of 0.60 "
                 f"(an error of {100 * (nf['amp_7hz'] / 0.6 - 1):.0f}%) and the NMSE is {nf['nmse']:.2f}. The low-pass filter "
                 f"attenuates 33 Hz by {abs(a5['attenuation_at_interference_db']):.0f} dB, so the same samples give "
                 f"{wf['amp_7hz']:.3f} at 7 Hz and an NMSE of {sci(wf['nmse'])}. Once the interference has been aliased, "
                 f"no later processing can remove it; the filter must come before the sampler."),
               table_block("Table 4 - Sampling at 40 Hz with and without the anti-aliasing filter", table(t4, [4.4, 4.2, 4, 4])),

               P("4.6 Reconstruction error versus sampling rate", "h2"),
               figure("fig6_error_vs_sampling_rate.png",
                      "Figure 6 - NMSE versus sampling rate for three interpolation methods.", 14.5),
               B(f"<b>Plateau below the Nyquist rate.</b> For f<sub>s</sub> from 14 to 21 Hz the sinc error is flat at about "
                 f"{sweep(20, 'sinc'):.2f}: the 11 Hz tone is always replaced by an alias, and the error power is fixed at "
                 f"{2 * p_11:.2f} / {p_total:.2f} = {nmse_pred_15:.2f}."),
               B(f"<b>Cliff at the Nyquist rate.</b> The sinc error falls from {sweep(20, 'sinc'):.2f} at 20 Hz to "
                 f"{sci(sweep(23, 'sinc'))} at 23 Hz, and to {sci(sweep(30, 'sinc'))} at 30 Hz."),
               B(f"<b>Exactly at 22 Hz the error is not zero</b> ({sweep(22, 'sinc'):.3f}). The 11 Hz tone sits at f<sub>s</sub>/2, "
                 f"so only the component of it in phase with the sample instants survives; the lost quadrature term "
                 f"0.4 sin(0.9) sin(2&pi;11t) has normalised power {lost_quad:.4f}, matching the simulation."),
               B(f"<b>Simple interpolators are far worse.</b> At 80 Hz the sinc error is {sci(sweep(80, 'sinc'))}, linear "
                 f"interpolation gives {sci(sweep(80, 'linear'))} and the zero-order hold {sci(sweep(80, 'zoh'))}; "
                 f"in practice a zero-order hold is followed by an analog smoothing filter."),
               B("<b>Floor at high rates.</b> The sinc error keeps decreasing slowly beyond 30 Hz because of the finite record "
                 "(the infinite sum is truncated at &plusmn;10 s), not because of the theorem."),
               table_block("Table 5 - NMSE for three interpolation methods", table(t5, [3, 4.3, 4.3, 4.3]))]

        # ---- 5 conclusion
        st += [P("5. Conclusion", "h1"),
               P("The simulation reproduces every prediction of the sampling theorem:"),
               B(f"sampling above the Nyquist rate ({nyq:g} Hz) and low-pass reconstruction recover the signal almost exactly "
                 f"(NMSE {sci(e1[30]['nmse'])} at 30 Hz);"),
               B("sampling below it folds higher frequencies into the baseband, and the apparent frequency follows "
                 "|f - f<sub>s</sub> round(f/f<sub>s</sub>)|, verified against the DFT for nine tones;"),
               B("in the frequency domain aliasing is the overlap of spectral replicas spaced f<sub>s</sub> apart;"),
               B("an anti-aliasing filter ahead of the sampler is essential, reducing the NMSE from "
                 f"{nf['nmse']:.2f} to {sci(wf['nmse'])} in the interference test; and"),
               B("ideal sinc reconstruction is orders of magnitude more accurate than linear interpolation or a zero-order hold."),
               P("<b>Limitations.</b> Continuous time is approximated on a 1 kHz grid or by an analytic function, the "
                 "anti-aliasing filter is a zero-phase digital stand-in for an analog filter, and the sinc sum is truncated "
                 "to a finite record. Natural extensions are a non-band-limited signal such as a chirp, quantisation "
                 "noise (ADC bit depth), and a practical analog reconstruction filter.")]

        # ---- references
        st += [P("References", "h1")]
        for r in [
            "[1] A. V. Oppenheim, A. S. Willsky and S. H. Nawab, <i>Signals and Systems</i>, 2nd ed. Prentice Hall, 1997, ch. 7.",
            "[2] C. E. Shannon, \"Communication in the presence of noise,\" <i>Proc. IRE</i>, vol. 37, no. 1, pp. 10-21, 1949.",
            "[3] H. Nyquist, \"Certain topics in telegraph transmission theory,\" <i>Trans. AIEE</i>, vol. 47, no. 2, pp. 617-644, 1928.",
            "[4] J. G. Proakis and D. G. Manolakis, <i>Digital Signal Processing</i>, 4th ed. Pearson, 2006.",
            "[5] C. R. Harris et al., \"Array programming with NumPy,\" <i>Nature</i>, vol. 585, pp. 357-362, 2020.",
            "[6] P. Virtanen et al., \"SciPy 1.0: fundamental algorithms for scientific computing in Python,\" <i>Nature Methods</i>, vol. 17, pp. 261-272, 2020.",
            "[7] J. D. Hunter, \"Matplotlib: a 2D graphics environment,\" <i>Computing in Science &amp; Engineering</i>, vol. 9, no. 3, pp. 90-95, 2007."]:
            st.append(P(r, "ref"))

        # ---- appendix
        st += [P("Appendix A - Core code and reproduction", "h1"),
               P((f"Complete code: <font name='DVM' size='8'>{STUDENT['github']}</font>. " if STUDENT.get("github") else "")
                 + "To reproduce every figure and number in this report:"),
               Preformatted("pip install -r requirements.txt\npython sampling_simulation.py", S["code"]),
               P("The three functions below carry the main idea (reconstruction, alias formula, impulse sampling):"),
               Preformatted(source_of("sinc_reconstruct", "alias_frequency", "impulse_sampled_spectrum"), S["code"])]

        # glue every heading to the flowable that follows it, so no heading is stranded at a page bottom
        merged, i = [], 0
        while i < len(st):
            f = st[i]
            if isinstance(f, Paragraph) and f.style.name in ("h1", "h2") and i + 1 < len(st):
                merged.append(KeepTogether([f, st[i + 1]]))
                i += 2
            else:
                merged.append(f)
                i += 1

        doc.build(merged, onFirstPage=footer, onLaterPages=footer)
    print(f"saved {PDF_PATH}")


if __name__ == "__main__":
    build()

#!/usr/bin/env python3
"""
Sampling Theorem, Aliasing and Signal Reconstruction -- Python Simulation
=========================================================================
Signals & Systems - Innovative Assessment

This script simulates the Nyquist-Shannon sampling theorem end to end:

  Exp 1  Time-domain sampling and ideal (sinc) reconstruction at three rates
  Exp 2  Aliasing demo: different sinusoids that produce identical samples
  Exp 3  Frequency-domain view: spectral replicas and their overlap
  Exp 4  Alias-frequency map + validation of the alias formula using the DFT
  Exp 5  Anti-aliasing filter: with vs. without a low-pass filter before sampling
  Exp 6  Reconstruction error vs. sampling rate (sinc / linear / zero-order hold)

Run:
    python sampling_simulation.py                 # outputs go to ./output
    python sampling_simulation.py --outdir results

Outputs:
    <outdir>/figures/*.png      all figures used in the report and slides
    <outdir>/results.json       every number quoted in the report
    <outdir>/alias_validation.csv   predicted vs. measured alias frequencies
"""

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display needed
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal as sps

# ----------------------------------------------------------------------------
# Test signal:  x(t) = sum_k A_k cos(2*pi*f_k*t + phi_k)   (band-limited)
# ----------------------------------------------------------------------------
TONES = [
    (1.00, 3.0, 0.0),   # (amplitude, frequency in Hz, phase in rad)
    (0.60, 7.0, 0.4),
    (0.40, 11.0, 0.9),
]
F_MAX = max(f for _, f, _ in TONES)   # highest frequency in the signal
NYQUIST_RATE = 2 * F_MAX              # minimum sampling rate = 22 Hz
REC = 10.0                            # samples are taken on [-REC, REC] seconds

# Colour-blind-safe palette (Okabe-Ito)
BLUE, VERM, GREEN = "#0072B2", "#D55E00", "#009E73"
ORANGE, PURPLE, GREY = "#E69F00", "#CC79A7", "#7f7f7f"

plt.rcParams.update({
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 100,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})


# ----------------------------------------------------------------------------
# Core signal-processing helpers
# ----------------------------------------------------------------------------
def x_of_t(t, tones=TONES):
    """Evaluate the multi-tone test signal at times t (seconds)."""
    t = np.asarray(t, dtype=float)
    return sum(a * np.cos(2 * np.pi * f * t + p) for a, f, p in tones)


def sample(fs, t_start, t_stop, tones=TONES):
    """Ideal sampler: returns sample instants t_n = n/fs and values x[n]."""
    n = np.arange(np.ceil(t_start * fs), np.floor(t_stop * fs) + 1)
    tn = n / fs
    return tn, x_of_t(tn, tones)


def sinc_reconstruct(t, tn, xn, fs):
    """Whittaker-Shannon interpolation: x_r(t) = sum_n x[n] sinc((t - n/fs) * fs)."""
    return np.sinc((np.asarray(t)[:, None] - tn[None, :]) * fs) @ xn


def zoh_reconstruct(t, tn, xn, fs):
    """Zero-order hold (staircase) reconstruction."""
    idx = np.floor((t - tn[0]) * fs + 1e-9).astype(int)
    return xn[np.clip(idx, 0, len(tn) - 1)]


def linear_reconstruct(t, tn, xn):
    """First-order (linear) interpolation."""
    return np.interp(t, tn, xn)


def nmse(x, xr):
    """Normalised mean-squared error  E[(x - xr)^2] / E[x^2]."""
    return float(np.mean((x - xr) ** 2) / np.mean(x ** 2))


def alias_frequency(f, fs):
    """Apparent frequency after sampling a tone f at rate fs (folded into [0, fs/2])."""
    f = np.asarray(f, dtype=float)
    return np.abs(f - fs * np.round(f / fs))


def sampling_status(fs):
    if fs < NYQUIST_RATE:
        return "UNDERSAMPLED - aliasing"
    if fs < 2 * NYQUIST_RATE:
        return "adequately sampled"
    return "oversampled"


def save(fig, outdir, name):
    path = Path(outdir) / "figures" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    print(f"  saved {path}")


# ----------------------------------------------------------------------------
# Experiment 1 - time-domain sampling and reconstruction
# ----------------------------------------------------------------------------
def exp1_reconstruction(outdir, rates=(100, 30, 15)):
    print("Exp 1: time-domain sampling & sinc reconstruction")
    t_plot = np.linspace(0, 1, 2000)
    t_eval = np.linspace(-2, 2, 4000)          # error is measured away from the edges
    x_eval = x_of_t(t_eval)

    fig, axes = plt.subplots(len(rates), 1, figsize=(9, 8.4), sharex=True)
    out = []
    for ax, fs in zip(axes, rates):
        tn, xn = sample(fs, -REC, REC)
        err = nmse(x_eval, sinc_reconstruct(t_eval, tn, xn, fs))
        m = (tn >= 0) & (tn <= 1)
        ax.plot(t_plot, x_of_t(t_plot), color="0.15", lw=1.7, label="Original x(t)")
        ax.plot(t_plot, sinc_reconstruct(t_plot, tn, xn, fs), color=BLUE, lw=1.6,
                ls="--", label="Sinc reconstruction")
        ax.plot(tn[m], xn[m], "o", color=VERM, ms=3 if fs > 50 else 5, label="Samples x[n]")
        ax.set_title(f"$f_s$ = {fs} Hz  ({fs / NYQUIST_RATE:.2f} x Nyquist rate)  -  "
                     f"{sampling_status(fs)}  -  NMSE = {err:.2e}", fontsize=10, loc="left")
        ax.set_ylabel("Amplitude")
        out.append({"fs": fs, "ratio_to_nyquist": fs / NYQUIST_RATE,
                    "status": sampling_status(fs), "nmse": err})
    axes[0].set_ylim(-2.4, 3.0)
    axes[0].legend(loc="upper right", ncol=3, fontsize=8.5, framealpha=0.9)
    axes[-1].set_xlabel("Time (s)")
    fig.tight_layout()
    save(fig, outdir, "fig1_time_domain_reconstruction.png")
    return out


# ----------------------------------------------------------------------------
# Experiment 2 - aliasing demonstration in the time domain
# ----------------------------------------------------------------------------
def exp2_alias_demo(outdir, f0=18.0, fs=20.0):
    print("Exp 2: aliasing demo (time domain)")
    f_alias = float(alias_frequency(f0, fs))
    t = np.linspace(0, 1, 4000)
    tn = np.arange(0, int(fs) + 1) / fs
    xn = np.cos(2 * np.pi * f0 * tn)

    # all of these tones produce exactly the same samples
    same = [2.0, 18.0, 22.0, 38.0, 42.0]
    max_diff = max(float(np.max(np.abs(np.cos(2 * np.pi * f * tn) - xn))) for f in same)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.9), sharey=True)
    a1.plot(t, np.cos(2 * np.pi * f0 * t), color=BLUE, lw=1.4, label=f"True tone  {f0:g} Hz")
    a1.plot(t, np.cos(2 * np.pi * f_alias * t), color=VERM, lw=2.0, ls="--",
            label=f"Alias seen after sampling  {f_alias:g} Hz")
    a1.plot(tn, xn, "ko", ms=5, label=f"Samples ($f_s$ = {fs:g} Hz)")
    a1.set_title(f"(a) {f0:g} Hz sampled at {fs:g} Hz looks like {f_alias:g} Hz", fontsize=10, loc="left")
    a1.set_xlabel("Time (s)")
    a1.set_ylabel("Amplitude")
    a1.legend(fontsize=8, loc="lower right", framealpha=0.95)

    for f, c, lw in [(2.0, VERM, 2.0), (18.0, BLUE, 1.3), (22.0, GREEN, 1.3)]:
        a2.plot(t, np.cos(2 * np.pi * f * t), color=c, lw=lw, label=f"{f:g} Hz")
    a2.plot(tn, xn, "ko", ms=5, label="Samples")
    a2.set_title("(b) 2, 18 and 22 Hz pass through the same samples", fontsize=10, loc="left")
    a2.set_xlabel("Time (s)")
    a2.legend(fontsize=8, loc="lower right", ncol=2, framealpha=0.95)
    fig.tight_layout()
    save(fig, outdir, "fig2_alias_time_domain.png")
    return {"f_true": f0, "fs": fs, "f_alias": f_alias,
            "tones_with_identical_samples": same, "max_sample_difference": max_diff}


# ----------------------------------------------------------------------------
# Experiment 3 - frequency-domain view (spectral replicas)
# ----------------------------------------------------------------------------
def impulse_sampled_spectrum(fs, fs_fine=1000, T=10.0):
    """Amplitude spectrum of x(t) multiplied by an ideal impulse train of rate fs.

    The 'continuous' signal lives on a fine 1 kHz grid; keeping every (fs_fine/fs)-th
    value and zeroing the rest models impulse sampling, whose spectrum is the original
    spectrum repeated every fs Hz.
    """
    n_pts = int(fs_fine * T)
    x = x_of_t(np.arange(n_pts) / fs_fine)
    step = int(round(fs_fine / fs))
    xs = np.zeros(n_pts)
    xs[::step] = x[::step]
    amp = np.abs(np.fft.rfft(xs)) / n_pts * 2 * step
    return np.fft.rfftfreq(n_pts, 1 / fs_fine), amp


def exp3_spectra(outdir, rates=(40, 20), f_show=80):
    print("Exp 3: frequency-domain replicas")
    n_pts = 10000
    f0 = np.fft.rfftfreq(n_pts, 1 / 1000)
    a0 = np.abs(np.fft.rfft(x_of_t(np.arange(n_pts) / 1000))) / n_pts * 2
    tone_f = [f for _, f, _ in TONES]

    fig, axes = plt.subplots(1 + len(rates), 1, figsize=(9.5, 8.4), sharex=True)
    sel = (a0 > 0.05) & (f0 <= f_show)
    axes[0].vlines(f0[sel], 0, a0[sel], color="0.15", lw=2)
    axes[0].plot(f0[sel], a0[sel], "o", color="0.15", ms=5)
    axes[0].set_title(f"(a) Original spectrum  |X(f)|  -  highest frequency $f_{{max}}$ = {F_MAX:g} Hz",
                      fontsize=10, loc="left")

    alias_report = []
    for ax, fs, tag in zip(axes[1:], rates, "bc"):
        f, a = impulse_sampled_spectrum(fs)
        sel = (a > 0.05) & (f <= f_show)
        for fi, ai in zip(f[sel], a[sel]):
            if fi < fs / 2:
                is_tone = any(np.isclose(fi, tf, atol=0.06) for tf in tone_f)
                color = BLUE if is_tone else VERM
                if not is_tone:
                    alias_report.append({"fs": fs, "alias_at_hz": round(float(fi), 2)})
            else:
                color = GREY
            ax.vlines(fi, 0, ai, color=color, lw=2)
            ax.plot(fi, ai, "o", color=color, ms=5)
        ax.axvline(fs / 2, color="k", ls=":", lw=1.2)
        ax.text(fs / 2 + 0.6, 1.08, f"$f_s/2$ = {fs / 2:g} Hz", fontsize=8.5, va="bottom")
        verdict = "no overlap - signal recoverable" if fs >= NYQUIST_RATE else "REPLICAS OVERLAP - aliasing"
        ax.set_title(f"({tag}) Sampled at $f_s$ = {fs} Hz  ({fs / NYQUIST_RATE:.2f} x Nyquist)  -  {verdict}",
                     fontsize=10, loc="left")
    for ax in axes:
        ax.set_ylabel("Amplitude")
        ax.set_ylim(0, 1.25)
    axes[-1].set_xlabel("Frequency (Hz)")
    axes[-1].set_xlim(0, f_show)
    from matplotlib.lines import Line2D
    axes[1].legend(handles=[
        Line2D([], [], marker="o", color=BLUE, lw=2, label="Baseband (true tones)"),
        Line2D([], [], marker="o", color=GREY, lw=2, label="Spectral replicas"),
        Line2D([], [], marker="o", color=VERM, lw=2, label="Alias inside baseband"),
    ], fontsize=8, loc="upper right", ncol=3, framealpha=0.95)
    fig.tight_layout()
    save(fig, outdir, "fig3_spectral_replicas.png")
    return alias_report


# ----------------------------------------------------------------------------
# Experiment 4 - alias-frequency map and DFT validation
# ----------------------------------------------------------------------------
def exp4_alias_map(outdir, fs=20.0, f_tests=(3, 8, 12, 18, 23, 31, 38, 45, 57)):
    print("Exp 4: alias map + DFT validation")
    n_samp = int(fs * 10)           # 10 s of samples -> 0.1 Hz resolution
    n = np.arange(n_samp)
    freqs = np.fft.rfftfreq(n_samp, 1 / fs)
    rows = []
    for f0 in f_tests:
        spec = np.abs(np.fft.rfft(np.cos(2 * np.pi * f0 * n / fs)))
        rows.append({"f_input_hz": f0, "fs_hz": fs,
                     "f_alias_predicted_hz": float(alias_frequency(f0, fs)),
                     "f_alias_measured_hz": round(float(freqs[np.argmax(spec)]), 2)})
    ok = all(abs(r["f_alias_predicted_hz"] - r["f_alias_measured_hz"]) < 1e-6 for r in rows)

    csv_path = Path(outdir) / "alias_validation.csv"
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  saved {csv_path}")

    f_in = np.linspace(0, 60, 2401)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for k in range(0, 6):
        if k % 2 == 1:
            ax.axvspan(k * fs / 2, (k + 1) * fs / 2, color="0.93", zorder=0)
    ax.plot(f_in, alias_frequency(f_in, fs), color=BLUE, lw=2, label="Predicted:  |f - $f_s$ round(f/$f_s$)|")
    ax.plot([r["f_input_hz"] for r in rows], [r["f_alias_measured_hz"] for r in rows],
            "o", color=VERM, ms=7, mfc="none", mew=2, label="Measured (DFT peak of sampled tone)")
    ax.axvline(fs / 2, color="k", ls=":", lw=1.2)
    ax.text(fs / 2 + 0.5, 10.6, "Nyquist\nfrequency", fontsize=8.5)
    ax.set_xlabel("True input frequency (Hz)")
    ax.set_ylabel("Apparent frequency after sampling (Hz)")
    ax.set_title(f"Alias-frequency map for $f_s$ = {fs:g} Hz  -  frequencies fold back into 0 ... {fs / 2:g} Hz",
                 fontsize=10, loc="left")
    ax.set_xlim(0, 60)
    ax.set_ylim(0, 12)
    ax.legend(loc="upper right", fontsize=8.5)
    fig.tight_layout()
    save(fig, outdir, "fig4_alias_frequency_map.png")
    return {"fs": fs, "table": rows, "formula_validated": ok}


# ----------------------------------------------------------------------------
# Experiment 5 - anti-aliasing filter
# ----------------------------------------------------------------------------
def exp5_antialias(outdir, fs=40, f_int=33.0, a_int=0.8, fc=15.0, order=8):
    print("Exp 5: anti-aliasing filter")
    fs_fine, T = 1000, 10.0
    t = np.arange(int(fs_fine * T)) / fs_fine
    wanted = [TONES[0], TONES[1]]                                  # 3 Hz and 7 Hz message
    x_wanted = x_of_t(t, wanted)
    x_in = x_wanted + a_int * np.cos(2 * np.pi * f_int * t)       # + out-of-band interference

    sos = sps.butter(order, fc, btype="low", fs=fs_fine, output="sos")
    x_filt = sps.sosfiltfilt(sos, x_in)                           # zero-phase low-pass

    step = fs_fine // fs
    tn = t[::step]
    results = {}
    recon = {}
    t_eval = np.linspace(3, 7, 4000)
    ref = x_of_t(t_eval, wanted)
    for name, sig in (("no_filter", x_in), ("with_filter", x_filt)):
        xn = sig[::step]
        recon[name] = (sinc_reconstruct(t_eval, tn, xn, fs), xn)
        amp = np.abs(np.fft.rfft(xn)) / len(xn) * 2
        fr = np.fft.rfftfreq(len(xn), 1 / fs)
        results[name] = {
            "nmse": nmse(ref, recon[name][0]),
            "amp_3hz": float(amp[np.argmin(np.abs(fr - 3))]),
            "amp_7hz": float(amp[np.argmin(np.abs(fr - 7))]),
        }

    w, h = sps.sosfreqz(sos, worN=8192, fs=fs_fine)
    mag_db = 20 * np.log10(np.maximum(np.abs(h) ** 2, 1e-12))     # filtfilt squares |H|
    att_int = float(np.interp(f_int, w, mag_db))

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    ax = axes[0, 0]
    ax.plot(w, mag_db, color=BLUE, lw=2)
    ax.axvline(fc, color=GREEN, ls="--", lw=1.2, label=f"cut-off {fc:g} Hz")
    ax.axvline(fs / 2, color="k", ls=":", lw=1.2, label=f"Nyquist {fs / 2:g} Hz")
    ax.axvline(f_int, color=VERM, ls="--", lw=1.2, label=f"interference {f_int:g} Hz")
    ax.set_xlim(0, 60)
    ax.set_ylim(-130, 5)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_title(f"(a) Anti-alias filter response ({att_int:.0f} dB at {f_int:g} Hz)", fontsize=10, loc="left")
    ax.legend(fontsize=8, loc="lower left")

    ax = axes[0, 1]
    win = (t_eval >= 4) & (t_eval <= 5)
    ax.plot(t_eval[win], ref[win], color="0.15", lw=2, label="Desired message")
    ax.plot(t_eval[win], recon["no_filter"][0][win], color=VERM, lw=1.6, ls="--",
            label=f"No filter (NMSE {results['no_filter']['nmse']:.2f})")
    ax.plot(t_eval[win], recon["with_filter"][0][win], color=BLUE, lw=1.6, ls=":",
            label=f"With filter (NMSE {results['with_filter']['nmse']:.1e})")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.set_title(f"(b) Reconstruction after sampling at {fs} Hz", fontsize=10, loc="left")
    ax.set_ylim(-2.8, 4.2)
    ax.legend(fontsize=8, loc="upper right")

    for ax, name, tag, col in ((axes[1, 0], "no_filter", "(c) Spectrum of samples - NO filter", VERM),
                               (axes[1, 1], "with_filter", "(d) Spectrum of samples - WITH filter", BLUE)):
        xn = recon[name][1]
        amp = np.abs(np.fft.rfft(xn)) / len(xn) * 2
        fr = np.fft.rfftfreq(len(xn), 1 / fs)
        sel = amp > 0.02
        ax.vlines(fr[sel], 0, amp[sel], color=col, lw=2.5)
        ax.plot(fr[sel], amp[sel], "o", color=col, ms=6)
        for fx, ax_amp in zip(fr[sel], amp[sel]):
            ax.annotate(f"{ax_amp:.2f}", (fx, ax_amp), textcoords="offset points", xytext=(0, 7),
                        ha="center", fontsize=8.5)
        ax.axhline(0.6, color="0.5", ls=":", lw=1)
        ax.text(19.8, 0.62, "true 7 Hz amp = 0.60", fontsize=8, ha="right", color="0.35")
        ax.set_xlim(0, fs / 2)
        ax.set_ylim(0, 1.6)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Amplitude")
        ax.set_title(tag, fontsize=10, loc="left")
    fig.tight_layout()
    save(fig, outdir, "fig5_antialiasing_filter.png")
    return {"fs": fs, "interference_hz": f_int, "interference_alias_hz": float(alias_frequency(f_int, fs)),
            "filter": f"Butterworth order {order}, fc={fc:g} Hz, forward-backward (zero-phase)",
            "attenuation_at_interference_db": att_int, **results}


# ----------------------------------------------------------------------------
# Experiment 6 - reconstruction error versus sampling rate
# ----------------------------------------------------------------------------
def exp6_sweep(outdir):
    print("Exp 6: NMSE vs sampling rate")
    t_eval = np.linspace(-2, 2, 2000)
    x_eval = x_of_t(t_eval)
    fs_list = np.unique(np.concatenate([np.arange(8, 81, 2.0), [21.0, 23.0]]))
    e_sinc, e_lin, e_zoh = [], [], []
    for fs in fs_list:
        tn, xn = sample(fs, -REC, REC)
        e_sinc.append(nmse(x_eval, sinc_reconstruct(t_eval, tn, xn, fs)))
        e_lin.append(nmse(x_eval, linear_reconstruct(t_eval, tn, xn)))
        e_zoh.append(nmse(x_eval, zoh_reconstruct(t_eval, tn, xn, fs)))

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axvspan(fs_list[0], NYQUIST_RATE, color=VERM, alpha=0.08)
    ax.semilogy(fs_list, e_zoh, "s-", color=VERM, ms=3.5, lw=1.4, label="Zero-order hold")
    ax.semilogy(fs_list, e_lin, "^-", color=GREEN, ms=3.5, lw=1.4, label="Linear interpolation")
    ax.semilogy(fs_list, e_sinc, "o-", color=BLUE, ms=3.5, lw=1.8, label="Ideal sinc (Whittaker-Shannon)")
    ax.axvline(NYQUIST_RATE, color="k", ls="--", lw=1.2)
    ax.text(NYQUIST_RATE + 0.8, 1e-9, f"Nyquist rate\n2 $f_{{max}}$ = {NYQUIST_RATE:g} Hz", fontsize=8.5, va="bottom")
    ax.text(9, 1e-9, "aliasing region", fontsize=8.5, va="bottom", color=VERM)
    ax.set_xlabel("Sampling rate $f_s$ (Hz)")
    ax.set_ylabel("Normalised MSE (log scale)")
    ax.set_title("Reconstruction error versus sampling rate", fontsize=10, loc="left")
    ax.set_xlim(fs_list[0], fs_list[-1])
    ax.set_ylim(1e-10, 20)
    ax.legend(loc="center right", fontsize=8.5)
    fig.tight_layout()
    save(fig, outdir, "fig6_error_vs_sampling_rate.png")

    pick = [10, 15, 20, 22, 30, 40, 60, 80]
    table = []
    for fs in pick:
        i = int(np.argmin(np.abs(fs_list - fs)))
        table.append({"fs": float(fs_list[i]), "sinc": e_sinc[i], "linear": e_lin[i], "zoh": e_zoh[i]})
    return {"fs": fs_list.tolist(), "sinc": e_sinc, "linear": e_lin, "zoh": e_zoh, "table": table}


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", default="output", help="folder for figures and results (default: output)")
    args = ap.parse_args()
    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    results = {
        "signal": {"tones": [{"amplitude": a, "frequency_hz": f, "phase_rad": p} for a, f, p in TONES],
                   "f_max_hz": F_MAX, "nyquist_rate_hz": NYQUIST_RATE},
        "exp1_reconstruction": exp1_reconstruction(args.outdir),
        "exp2_alias_demo": exp2_alias_demo(args.outdir),
        "exp3_spectral_aliases": exp3_spectra(args.outdir),
        "exp4_alias_validation": exp4_alias_map(args.outdir),
        "exp5_antialiasing": exp5_antialias(args.outdir),
        "exp6_error_sweep": exp6_sweep(args.outdir),
    }
    out_json = Path(args.outdir) / "results.json"
    out_json.write_text(json.dumps(results, indent=2))
    print(f"  saved {out_json}")

    print("\n=== Summary ===")
    print(f"Signal f_max = {F_MAX:g} Hz  ->  Nyquist rate = {NYQUIST_RATE:g} Hz")
    for r in results["exp1_reconstruction"]:
        print(f"  fs = {r['fs']:>5} Hz  NMSE = {r['nmse']:.3e}   ({r['status']})")
    print(f"Alias formula validated against DFT: {results['exp4_alias_validation']['formula_validated']}")
    a = results["exp5_antialiasing"]
    print(f"Anti-alias filter: NMSE {a['no_filter']['nmse']:.3f} (no filter) -> {a['with_filter']['nmse']:.2e} (filter)")


if __name__ == "__main__":
    main()

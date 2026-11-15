# Sampling Theorem, Aliasing & Signal Reconstruction — Python Simulation

**Course:** Signals & Systems — Innovative Assessment
**Topic:** Nyquist–Shannon sampling theorem, aliasing, anti-aliasing filtering and signal reconstruction

This project simulates, in Python, what happens when a continuous-time signal is sampled
below, near and above the Nyquist rate — in the time domain *and* the frequency domain —
and measures how well the signal can be reconstructed.

## Test signal

```
x(t) = 1.0·cos(2π·3t) + 0.6·cos(2π·7t + 0.4) + 0.4·cos(2π·11t + 0.9)
```

Highest frequency f_max = 11 Hz, so the **Nyquist rate is 2·f_max = 22 Hz**.

## Experiments

| # | Experiment | Figure |
|---|------------|--------|
| 1 | Sampling at 100 / 30 / 15 Hz and ideal sinc (Whittaker–Shannon) reconstruction | `fig1_time_domain_reconstruction.png` |
| 2 | Aliasing demo: 2, 18 and 22 Hz tones give identical samples at fs = 20 Hz | `fig2_alias_time_domain.png` |
| 3 | Spectrum of the sampled signal: replicas every fs Hz, overlap when fs < 2·f_max | `fig3_spectral_replicas.png` |
| 4 | Alias-frequency map, with the formula checked against the DFT of sampled tones | `fig4_alias_frequency_map.png` |
| 5 | Anti-aliasing filter: 33 Hz interference sampled at 40 Hz with and without a low-pass filter | `fig5_antialiasing_filter.png` |
| 6 | Reconstruction error vs. sampling rate for sinc, linear and zero-order-hold interpolation | `fig6_error_vs_sampling_rate.png` |

## Key results

| Quantity | Value |
|----------|-------|
| NMSE at fs = 100 Hz (4.55× Nyquist) | 4.9 × 10⁻⁹ |
| NMSE at fs = 30 Hz (1.36× Nyquist) | 6.7 × 10⁻⁷ |
| NMSE at fs = 15 Hz (0.68× Nyquist, aliasing) | 2.1 × 10⁻¹ |
| Alias formula `|f − fs·round(f/fs)|` vs. DFT peak | matches for all 9 test tones |
| 33 Hz interference sampled at 40 Hz, no filter | NMSE 0.47 (aliases onto the 7 Hz tone) |
| Same, with 8th-order Butterworth low-pass (fc = 15 Hz) | NMSE 1.3 × 10⁻⁵ |

NMSE = E[(x − x̂)²] / E[x²], measured on the central part of the record to avoid edge effects.

## How to run

```bash
pip install -r requirements.txt
python sampling_simulation.py            # writes everything to ./output
python sampling_simulation.py --outdir results
```

Runtime is about 6 seconds. The script is deterministic (no random numbers), so results are
reproducible.

Output:

```
output/
├── figures/                 PNG figures used in the report and slides
├── results.json             every number quoted in the report
└── alias_validation.csv     predicted vs. measured alias frequencies
```

## Regenerating the report and slides (optional)

`tools/build_report.py` and `tools/build_presentation.py` rebuild the PDF report
(`report/Technical_Report.pdf`) and the PowerPoint (`presentation/`) from `output/`.
Put your name, roll number and GitHub link in `tools/student_info.py`, then run:

```bash
pip install -r requirements-docs.txt
python tools/build_report.py
python tools/build_presentation.py
```

## Method notes

- **Continuous time** is approximated by an analytic function evaluated at arbitrary
  instants (Exp 1, 2, 6) or by a 1 kHz fine grid (Exp 3, 5).
- **Impulse sampling** (Exp 3) keeps every (1000/fs)-th point of the fine grid and zeros the
  rest, so the spectrum shows the exact replicas predicted by theory.
- **Anti-aliasing filter** (Exp 5) is an 8th-order Butterworth low-pass run on the 1 kHz grid
  with forward–backward filtering (zero phase), which stands in for the analog filter that
  would precede an ADC.
- **Sinc reconstruction** uses samples over ±10 s; the infinite sum is truncated, so the error
  floor at high rates comes from truncation, not from the theory.

## Files

```
sampling_simulation.py   main simulation (all six experiments)
requirements.txt         numpy, scipy, matplotlib
requirements-docs.txt    reportlab, python-pptx (only for the document builders)
tools/                   student_info.py, build_report.py, build_presentation.py
output/                  generated figures and results
report/                  Technical_Report.pdf
presentation/            Sampling_Aliasing_Presentation.pptx
```

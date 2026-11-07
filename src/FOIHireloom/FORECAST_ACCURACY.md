# Forecast accuracy

`foihireloom-forecast-accuracy` evaluates Chronos forecasts of the DZS monthly
registered unemployment rate. It reads the database and writes an optional JSON
report; it does not import data, train the model or change stored values.

```bash
uv sync --locked --extra forecast

# All 20 counties and Grad Zagreb: three origins, six months per forecast.
uv run --locked --extra forecast foihireloom-forecast-accuracy --out accuracy.json

# One county, ending the final test window in September 2026.
uv run --locked --extra forecast foihireloom-forecast-accuracy \
  --county varazdinska --horizon 6 --windows 3 --end-period 2026-09 \
  --out accuracy-varazdinska.json
```

Repeat `--county` for several counties, using codes or names from `list_regions`.
`--sex total|women|men` selects the DZS series. The model and device come from
`CHRONOS_MODEL` and `CHRONOS_DEVICE`, just as for live forecasts. The first run
downloads the model. Keeping the `forecast` extra enabled in `uv run` retains
Chronos and PyTorch in the environment.

## Method

The last test month defaults to the latest month known for every selected
county. With `--end-period 2026-09 --horizon 6 --windows 3`, the training cutoffs
are January, February and March 2026. Their test windows are February–July,
March–August and April–September. Each origin receives only values dated at or
before its cutoff, with at most 120 monthly periods and at least 24 known values.
Missing interior training values remain NaN, as in live forecasts.

The horizon is 1–12 months; the number of monthly origins is 1–12. These bounds
keep the run finite and ensure that every seasonal baseline value is already
in the training period. The baseline predicts the same value as the same month
one year earlier. Every scored window requires a known final training value,
complete actual test values and complete seasonal baseline values. Otherwise,
the window records a reason and neither method receives a score for it.

Chronos predictions use the same 0–100 bounds and one-decimal precision as the
user-facing unemployment-rate forecast. Invalid, unordered, nonfinite or
incomplete model output aborts the run rather than generating accuracy scores.

The procedure follows rolling-origin evaluation and the seasonal-naive baseline
described in [Forecasting: Principles and Practice](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation).

## Report

The full report includes each cutoff, training range and count, every predicted
and observed value, provisional flags, skip reasons, per-county metrics, and
metrics for each forecast step. Aggregate metrics use the underlying scored
pairs, rather than averages of already rounded county scores:

- `mae_pp`: mean absolute error of the Chronos median, in percentage points.
- `seasonal_naive_mae_pp`: the baseline's MAE on exactly the same pairs.
- `mae_skill`: `1 - mae_pp / seasonal_naive_mae_pp`; positive means improvement.
  It is null when the baseline MAE is zero.
- `interval_coverage`: the fraction of actuals inside the inclusive 80% interval.
  This is interval coverage, not an "accuracy percentage".
- `mean_interval_width_pp`: average upper minus lower interval boundary.
- `observations`: scored origin/target pairs; `provisional_observations` identifies
  how many of those actuals DZS may revise.

With no scored pairs, metrics are null and status is `unavailable`, never a
perfect zero error. Report metadata retains the request, source import,
generation time, model ID, installed package versions and a SHA-256 of the data
snapshot. Without `--out`, stdout contains the full JSON report; with it, stdout
contains a compact summary. Exit codes are 0 for an evaluated report, 2 when no
window can be scored, and 1 for model, database or file errors. Invalid command
arguments also exit 2. A worse-than-baseline result is a valid measurement and
does not make the command fail.

This is retrospective evaluation against the **latest stored, possibly revised
DZS values**. It does not reconstruct historical publication dates or earlier
data vintages, and cannot audit the pretrained model's training data. Test
windows can overlap: scored pairs are not independent observations. Small
samples, or good aggregate coverage, do not establish accuracy for every county.
The report therefore includes per-county and per-horizon results and imposes no
quality threshold chosen after inspecting the scores.

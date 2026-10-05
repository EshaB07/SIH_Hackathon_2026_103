# PAIMANA Predictive Risk Monitoring System

A predictive and prescriptive layer on top of the PAIMANA portal that forecasts cost overruns and schedule delays three months in advance, produces an interpretable risk score for every project, and shows the specific factors driving each prediction.

Built for Smart India Hackathon – Problem Statement 103 (SIH26103), issued by the Infrastructure & Project Monitoring Division (IPMD) and the Ministry of Statistics and Programme Implementation (MoSPI).

## Live Demo
Click here to view the website: [Live Website Link](https://sih-eta-peach.vercel.app/)

## 1. Project Overview

The PAIMANA portal currently works as a descriptive monitoring system for Central Sector Infrastructure Projects. It records cost, timeline, and progress data but does not predict future outcomes.

This project adds a predictive and prescriptive layer on top of that data. It:

- Forecasts cost overruns and schedule delays three months in advance
- Generates an interpretable risk score per project
- Surfaces the specific factors driving each prediction

## 2. Problem Statement Recap

The problem statement explicitly asks for:

- (a) Predictive models that forecast cost/time overruns using open-source tools
- (b) An assessment of whether ML provides meaningful gains over conventional statistical methods
- (c) Models built on existing Common Upload Form (CUF) fields, with an evaluation of how much predictive power comes from CUF fields versus additional variables

This system addresses all three requirements, as detailed in the sections below.

## 3. Data Source

- Website: https://paimana-proj.mospi.gov.in
- Coverage: All 28 states and 8 union territories
- Collection: Data was obtained directly through the public dashboard of the PAIMANA website

## 4. Data Cleaning and Preprocessing

The cleaning script applies the following rules:

- **Cost overrun fallback:** Falls back to the original cost if the revised cost is zero or missing/blank (`NaN`), so blank fields do not break the calculation.
- **Missing text preservation:** Genuine missing values in text columns are kept as `NaN` rather than converted into the literal string `"nan"`.
- **Flexible date parsing:** If a date fails the strict `DD/MM/YYYY` format, a flexible parser is used instead of silently producing a missing value (`NaT`).
- **Accurate project status labeling:** Missing progress values are labeled `Unknown`, separate from projects explicitly at 0% (`Not Started`) or `In Progress`.
- **Preservation of delay metrics:** Missing delay metrics stay `NaN` instead of collapsing to 0, and projects completed ahead of schedule keep their actual negative delay values.
- **Agency name normalisation:** Implementing agency names are standardised by removing trailing bracket abbreviations, punctuation, dashes, and roman numerals, and construction-office codes are mapped to their corresponding zonal railway names.

### Expected input structure

The modeling pipeline expects a CSV with one row per project per reporting month, with columns including:

`Sector Name`, `Line Ministry`, `Implementing Agency`, `Project Code`, `Project Name`, `Original Cost`, `Revised Cost`, `Expenditure`, `Physical Progress`, `Original/Revised Date of Commissioning`, `Sanction Date`, `Cost Overrun`, `Delay`

### Data-quality issues handled

- **Day-first dates:** Source dates are in `DD-MM-YYYY` format, which pandas' default parser misreads by silently swapping day and month. All date columns are parsed with an explicit `format="%d-%m-%Y"`.
- **"No revision filed yet":** A `Revised Cost` of exactly 0 and a blank `Revised Date of Commissioning` both mean no revision has been filed. They are treated as equal to the original cost/date, not as nulls or zeros.

## 5. Project Identity and Multi-State Handling

- `Project_UID` uniquely identifies a project by combining State and Project Code (e.g. `Maharashtra_617212`).
- `Project_Group` is the bare Project Code. Some projects, particularly Railways and other national infrastructure, span multiple states and are logged once per state with identical underlying data. `Project_Group` recognises these as the same project.
- `State_Group` marks any project appearing in more than one state as `"Multi-state"`, which is used as a categorical feature.

This distinction is used in two places:

| Stage | Behaviour |
|---|---|
| Training | Rows are deduplicated by `Project_Group`, so a multi-state project is not counted multiple times and does not inflate validation accuracy. |
| Final output | Every state's listing is kept and scored, since a project's presence in multiple states is worth surfacing per state in the dashboard. |

## 6. Feature Engineering

Beyond the raw CUF fields, 18 additional variables are engineered from the data already present. No external data sources are used at this stage.

| Category | What it captures | Features |
|---|---|---|
| Momentum | How fast a project is currently moving | `progress_velocity`, `expenditure_velocity`, `stagnant_flag` |
| History of Slipping | Whether the situation is worsening and how often it has been revised | `delay_change`, `cost_overrun_change`, `n_date_revisions`, `n_cost_revisions` |
| Deadline Pressure | How much runway remains and whether the project is on pace | `months_to_commission`, `months_since_sanction`, `pct_time_elapsed`, `required_velocity`, `velocity_gap` |
| Money vs. Work | Whether spending is outpacing actual construction | `expenditure_ratio`, `spend_progress_gap` |

### Feature definitions

- `progress_velocity`: average physical progress gained per month
- `expenditure_velocity`: average spend per month
- `stagnant_flag`: binary flag for zero progress across the observed window
- `delay_change` / `cost_overrun_change`: how much delay or overrun shifted across the observed window
- `n_date_revisions` / `n_cost_revisions`: number of times the commissioning date or cost was revised
- `pct_time_elapsed`: share of total project duration already used
- `required_velocity`: pace of progress needed to finish on schedule
- `velocity_gap`: required pace minus actual pace, the most direct "on track or not" signal
- `expenditure_ratio`: share of budget spent
- `spend_progress_gap`: mismatch between financial and physical progress, a strong indicator of potential mismanagement

**Missing-data flags:** `Sanction_Date_Missing` and `Revised_Date_Missing` mark rows where a date could not be determined even after cross-month recovery. This lets the model treat missingness as its own signal instead of silently imputing a value.

Together with the raw CUF fields, this gives a final feature array of 26 variables feeding both models.

## 7. Modeling Approach

Two independent XGBoost classifiers are trained:

- `cost_escalated`: will the project's cost overrun worsen over the next three months?
- `time_escalated`: will the project's schedule delay worsen over the next three months?

XGBoost was chosen over simpler alternatives because gradient-boosted trees can capture conditional interactions (for example, "a high spend-progress mismatch matters more in some sectors than others") that a linear model cannot represent.

### Experiment grid

- Two feature sets per target: numeric features only, versus numeric plus categorical (`Sector`, `Implementing Agency`, `State_Group`)
- Three model configurations varying tree depth, learning rate, and regularization strength

**Baseline:** A plain logistic regression using only one or two of the most obvious raw fields is trained alongside, directly answering the PS requirement to assess whether ML gives a meaningful gain over conventional statistics.

**Validation:** Group-aware, repeated stratified k-fold cross-validation (`StratifiedGroupKFold`), grouped by `Project_Group` instead of individual row. No project's data leaks between training and validation folds. A naive random split could let the model see a project in training and be tested on that same project's later months, artificially inflating accuracy.

## 8. Labels and the Rolling Prediction Window

A project's label is not based on its final completion. It is based on a rolling comparison:

- For each anchor month, features are built from the preceding `LOOKBACK` months (4).
- The label compares the project's cost overrun / delay at the anchor month against its state `HORIZON` months later (3).
- If the overrun or delay worsened beyond a small margin (1.0 percentage point for cost, 0.5 months for delay), the project is labeled as escalated.

This tests the system's practical purpose, whether it could have flagged a problem before it materialised, using only data available at the time.

**Scoring eligibility:** A project is scored for a given month only if it has at least one snapshot within the four-month lookback window and its most recent snapshot is no more than one month behind the scoring month (`MAX_STALE`). Otherwise the model declines to score it rather than guess from stale data.

## 9. Explainability

Every prediction is paired with SHAP values computed via `TreeExplainer`. Two forms of explanation are produced:

- **Global driver ranking:** mean absolute SHAP value across the full training portfolio, saved per model as a CSV and a chart.
- **Per-project, per-month top-2 drivers:** attached directly to each row of the final output.

No risk score is presented as an unexplained number. Every flag comes with the features that produced it.

## 10. Risk Scoring

- Each model outputs a probability between 0 and 1, rescaled to 0–100 for display.
- A percentile rank within the scoring month (`cost_risk_pct`, `time_risk_pct`) is computed so risk is assessed relative to that month's cohort rather than on an absolute, possibly skewed scale.
- A combined risk score blends the two: 70% time-risk, 30% cost-risk. The time model is weighted higher because it is better validated (a much larger positive class and stronger PR-AUC than the cost model, given how rare true cost escalation events are in the available data).
- The combined score is banded into Low / Medium / High risk.

## 11. Handling Missing Scores

No project is silently dropped. Every `Project_UID`, for every month it appears in, is retained in the final CSV. Where a real score could not be computed, the `no_score_reason` column explains why:

- The project lacked four months of prior history
- Its most recent report is too stale relative to the scoring month
- It falls within the first three months of the entire dataset, before any project could have accumulated enough history

## 12. Backtesting

The dataset spans enough months for some earlier predictions' three-month horizons to have already passed, so the system includes a backtest. For every project/month where the actual outcome three months later is available, the earlier prediction is compared against what actually happened.

Each project receives a plain verdict:

- Correctly flagged
- Correctly stable
- False alarm
- Missed escalation

Real cost overrun and delay figures recorded at the later point are included alongside. Where three months have not yet elapsed, or the project stopped reporting during that window, a `backtest_reason` explains why no verdict is available.

## 13. Output Schema

The final CSV, `paimana_project_risk_scores_monthly.csv`, has one row per `Project_UID` per scored month, matching the row count of the source dataset exactly.

| Group | Columns |
|---|---|
| Identity and descriptive | `Project_UID`, `Project_Group`, `State`, `Project Name`, `Sector` |
| Risk outputs (0–100 scale) | `cost_risk`, `time_risk`, `cost_risk_pct`, `time_risk_pct`, `combined_risk`, `risk_band` |
| Explainability | `cost_driver_1/2_name` and `_impact`, `time_driver_1/2_name` and `_impact` (impacts are raw SHAP contributions, not percentages, and are unscaled) |
| Status | `no_score_reason`, `used_in_training` |
| Backtest | now/actual cost overrun and delay, predicted flags, verdicts, error percentages, `backtest_reason` |

## 14. Dashboard / UI

- **Framework:** [React]
- **Page structure:** [Home, AI Risk Intelligence, Dashboard]
- **Data source:** All risk scores, driver names, and portfolio statistics are read directly from `paimana_project_risk_scores_monthly.csv`. No placeholder or randomly generated values appear in the interface.

### Key UI principles

- Any project without a real score shows its `no_score_reason` in plain language, never a blank or a fabricated zero.
- Predicted-risk figures and actual-recorded-overrun figures are always labeled distinctly and are never implied to be directly comparable magnitudes.
- Each project detail view has a "Predicted vs. Actual" section showing the backtest verdict once resolved, or a clear "not yet resolved" state otherwise.

## 15. Known Limitations

- The cost escalation model has a lower PR-AUC than the time model, because true cost escalation events are rare in the available window compared to time delays.
- Output should be read as a relative risk ranking, not a precise probability, at small sample sizes.
- The dataset's history currently spans a limited number of months and states. Broader historical coverage and the planned Layer 3 external variables (commodity price indices, wage indices, monsoon exposure, financing rates) are expected to improve both accuracy and the CUF-vs-external-variable comparison the PS requests.

## 16. Installation and Setup

**Requirements:** Python [3.10.x], plus `xgboost`, `scikit-learn`, `shap`, `pandas`, `numpy`, and your dashboard framework.

## 17. Repository Structure

```
├── data/           # Raw and cleaned input data
├── src/            # Cleaning, feature engineering, modeling scripts
├── outputs/        # Risk score CSV, SHAP driver CSVs and charts
├── dashboard/      # Dashboard code
└── README.md
```

## 18. References

1. Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. KDD '16.
2. Lundberg, S. M., & Lee, S.-I. (2017). A Unified Approach to Interpreting Model Predictions. NeurIPS 30.
3. Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python. JMLR.

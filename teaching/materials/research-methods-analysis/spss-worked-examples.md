---
layout: teaching-document
title: "SPSS worked examples: independent and paired t-tests"
description: "SPSS worked examples: independent and paired t-tests using synthetic RSCH650 teaching data."
document_type: Software lab
material_title: Research Methods and Analysis
material_path: /teaching/materials/research-methods-analysis/
updated: October 2026
---

# SPSS worked examples: independent and paired t-tests

Use this lab after the animation, or as a 25–35 minute class exercise. The first analysis reproduces the animation's baseline Welch test. The second uses a **new, separate synthetic study** to explain a paired test. Both use seconds to correctly report a simulated ramp hazard; lower times mean faster correct reporting. All workers in these examples report correctly within the observation period.

These are invented teaching observations, not aviation performance evidence or operational benchmarks. The tables below are independently calculated expected values, **not screenshots or exports of SPSS output**. Small differences in displayed decimal places are normal. Numerical references and a verification script are supplied alongside the lab.

## Files and study designs

| Study | Data layout | Syntax with inline data | CSV for other software |
| --- | --- | --- | --- |
| Independent training groups | 40 different workers, one row per worker, 20 in each group | [ramp_hazard_training.sps](ramp_hazard_training.sps) | [ramp_hazard_training.csv](ramp_hazard_training.csv) |
| Before and after practice | 20 new workers, one row per worker, two measurements per row | [ramp_hazard_paired.sps](ramp_hazard_paired.sps) | [ramp_hazard_paired.csv](ramp_hazard_paired.csv) |

The paired file uses IDs 301–320. Its workers are unrelated to IDs 101–120 and 201–220 in the independent example. Equal row positions in two independent groups do not create matched workers.

## 1. Reproduce the independent Welch example

1. In SPSS Statistics, save any current work, then choose **File > Open > Syntax** and open `ramp_hazard_training.sps` from the parent folder.
2. Read its comments, then choose **Run > All**. Run the full syntax so the correct data are loaded. No CSV import or path editing is needed.
3. In Data View, confirm 40 rows. In Variable View, `training` is nominal and `report_seconds` is scale. Code 1 means standard briefing; code 2 means scenario practice.
4. In the Output Viewer, read **Group Statistics**, then **Independent Samples Test**. Use the **Equal variances not assumed** row for the prespecified Welch analysis and the **Two-Sided p** column, sometimes labeled **Sig. (2-tailed)**.

The essential command is:

```spss
T-TEST GROUPS=training(1 2)
 /VARIABLES=report_seconds
 /MISSING=ANALYSIS
 /CRITERIA=CI(.95).
```

For the menu equivalent, open **Independent-Samples T Test** under Analyze's comparison-of-means submenu. Choose `report_seconds` as the test variable and `training` as the grouping variable. Define groups as 1 and 2, retain a 95% interval, and use **Paste** to inspect the syntax. Submenu wording varies by SPSS version.

### Expected Group Statistics

| Training group | N | Mean (s) | Std. Deviation (s) | Std. Error Mean (s) |
| --- | ---: | ---: | ---: | ---: |
| Standard briefing | 20 | 48.000000 | 8.000000 | 1.788854 |
| Scenario practice | 20 | 42.000000 | 8.000000 | 1.788854 |

### Expected Welch row in Independent Samples Test

The difference is **standard briefing minus scenario practice**.

| t | df | Two-sided p | Mean difference (s) | Std. error difference (s) | 95% CI lower (s) | 95% CI upper (s) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2.371708 | 38.000000 | .0228758 | 6.000000 | 2.529822 | 0.878643 | 11.121357 |

Check the arithmetic: `SE = sqrt(8²/20 + 8²/20) = 2.529822`, and `t = 6/2.529822 = 2.371708`. Welch–Satterthwaite degrees of freedom happen to equal 38 because both groups have the same sample size and SD. The pooled and Welch results therefore coincide here. Their coincidence does not make the groups paired, and a Levene-test p-value is not needed to switch away from the prespecified Welch analysis.

**Example report:** In the synthetic independent-group study, workers receiving the standard briefing had a longer mean reporting time (M = 48.00 s, SD = 8.00) than workers receiving scenario practice (M = 42.00 s, SD = 8.00). Welch's t(38) = 2.37, p = .023, mean difference = 6.00 s, 95% CI [0.88, 11.12].

The p-value describes how unusual a statistic this extreme in either direction would be under equal population means and the model assumptions. It is not the probability that the null hypothesis is true. The interval concerns the population mean difference, not individual reporting times. If 5 s were a prespecified minimum worthwhile difference, this interval would not establish a difference of at least 5 s.

## 2. Analyze a genuinely paired study

Imagine measuring the same 20 workers once before practice and once afterward using comparable simulator tasks. Each row preserves a worker's two measurements. There is no randomized comparison group in this constructed study: time, repeated testing, task familiarity, or other changes could account for some or all of the observed before/after difference.

### Data dictionary

| Variable | Meaning |
| --- | --- |
| `worker_id` | Unique synthetic worker ID, 301–320; nominal, not a score |
| `before_seconds` | Correct hazard-reporting time before practice, in seconds |
| `after_seconds` | Correct hazard-reporting time after practice, in seconds |
| `reduction_seconds` | Computed in SPSS as before minus after; positive = faster afterward |

The CSV contains the first three columns. The syntax creates the fourth. There are 20 complete matched cases, 40 measurements, no missing values, and no censored or failed reports. The integer observations were fixed deliberately for this exercise; the syntax does not draw a fresh random sample.

1. Open `ramp_hazard_paired.sps` through **File > Open > Syntax**, and choose **Run > All**. It supplies its own inline data and needs no local file paths.
2. Confirm 20 rows in Data View. Worker 301 has before = 35, after = 37, and reduction = −2 s. Worker 302 has 43, 33, and +10 s. Worker 309 has 48, 48, and 0 s. These checks establish the subtraction direction.
3. Read the descriptives and the boxplot, histogram, and normal Q–Q plots for `reduction_seconds`. Inspect the distribution of **within-worker differences** for extreme observations and substantial non-normality.
4. Read **Paired Samples Statistics**, **Paired Samples Correlations**, and **Paired Samples Test**, using the expected values below. In the last table, use the two-sided p-value for the mean difference.
5. Compare the final **One-Sample Test** on `reduction_seconds` against zero. It should reproduce the paired t statistic, df, p-value, and interval. It is an arithmetic demonstration of the same test, not additional independent evidence.

The central syntax is:

```spss
COMPUTE reduction_seconds=before_seconds-after_seconds.
EXECUTE.
T-TEST PAIRS=before_seconds WITH after_seconds (PAIRED)
 /CRITERIA=CI(.95)
 /MISSING=ANALYSIS.
```

For the menu equivalent, open **Paired-Samples T Test** under Analyze's comparison-of-means submenu. Place `before_seconds` in Variable 1 and `after_seconds` in Variable 2, as a single pair. Retain a 95% interval. **Paste** shows how the variable order sets the sign. IBM documents the [`PAIRS ... WITH ... (PAIRED)` syntax](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=test-pairs-subcommand-t-command).

### Expected Paired Samples Statistics

| Measure | Mean (s) | N | Std. Deviation (s) | Std. Error Mean (s) |
| --- | ---: | ---: | ---: | ---: |
| Before practice | 48.000000 | 20 | 7.874008 | 1.760682 |
| After practice | 42.000000 | 20 | 8.547083 | 1.911186 |

In **Paired Samples Correlations**, expect N = 20, Pearson r = **.850085**, two-sided p ≈ **.0000020804**. This correlation describes the association between the workers' two measurements. Its p-value tests a different null hypothesis from the paired mean test and does not answer whether the mean changed.

### Expected Paired Samples Test

The pair is **before minus after**.

| Quantity | Expected value |
| --- | ---: |
| Mean difference | 6.000000 s |
| Std. Deviation of differences | 4.542200 s |
| Std. Error Mean of differences | 1.015667 s |
| 95% CI, lower | 3.874185 s |
| 95% CI, upper | 8.125815 s |
| t | 5.907449 |
| df | 19 |
| Two-sided p | .0000109344 |

SPSS may display the p-value as `< .001` or, in some output formats, `.000`. Report **p < .001**, never p = .000. The 20 workers supply 20 differences, so df = 20 − 1 = 19. There are not 40 independent observations.

SPSS 29 also supplies effect-size tables. In this paired example, its default Cohen's d uses the **SD of differences**, giving `d_z = 6/4.542200 = 1.321`. The original independent example's Cohen's d uses a pooled within-group SD, giving `6/8 = 0.750`. These standardizers answer different questions; do not compare the two numbers as if they measured the same study effect. The raw difference and its interval retain their useful seconds scale.

### Why the pairing matters

The paired analysis uses the SD of differences, not either occasion's SD:

```text
d_i = before_i − after_i
mean(d) = 6.000000 s
s_d = 4.542200 s
SE(mean(d)) = s_d / sqrt(20) = 1.015667 s
t = 6 / 1.015667 = 5.907449
95% CI = 6 ± 2.093024 × 1.015667 = [3.874185, 8.125815] s
```

Workers who are relatively slow before practice tend also to be relatively slow afterward. The sample covariance explains why the variation in changes is smaller than the variation in either occasion's times:

```text
s_d² = s_before² + s_after² − 2r × s_before × s_after
     = 7.874008² + 8.547083² − 2 × .850085 × 7.874008 × 8.547083
     = 20.631579 s²
```

Omitting the covariance term would give an SE of 2.598583 s for these numbers. That independent-observations calculation is inappropriate for these matched observations. The positive correlation reduces the paired SE here; the design, rather than whichever test produces a smaller p-value, determines the analysis. The original independent example and this paired example are separate constructed studies, so their p-values do not prove that one training method or study design is superior.

**Example report:** In this synthetic 20-worker before/after study, mean correct-reporting time was 48.00 s before practice (SD = 7.87) and 42.00 s afterward (SD = 8.55). The mean within-worker reduction was 6.00 s (SD of differences = 4.54), 95% CI [3.87, 8.13], paired t(19) = 5.91, p < .001. This illustrates a mean change over time in the constructed data. An uncontrolled before/after comparison cannot establish that practice caused the change.

Seventeen workers were faster afterward, two were slower, and one was unchanged. A mean reduction does not imply that every worker improved. The interval still includes reductions smaller than a hypothetical 5 s minimum worthwhile change.

## Assumptions and missing data

For the independent example, workers must contribute independent observations across and within groups. For the paired example, the two measurements within a worker may be dependent, while different workers' differences should be independent. The outcome is quantitative. A paired t-test assumes an approximately normal population distribution of differences for exact small-sample inference and is sensitive to severe outliers. It does not require equal before/after variances. Study design and measurement quality need assessment in addition to plots. See IBM's [paired-test data considerations](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=tests-paired-samples-t-test).

The supplied `EXAMINE` command requests difference-score diagnostics using IBM's [documented plot options](https://www.ibm.com/docs/en/spss-statistics/31.0.0?topic=reference-examine). A non-significant normality test does not prove normality, especially with only 20 differences. Examine the plots and the substantive measurement process; do not use a normality-test p-value as an automatic permission rule for the analysis.

Both syntax files use `/MISSING=ANALYSIS`. In an independent analysis, a row missing its group or outcome is excluded for that outcome. In a paired analysis, a worker missing either measurement is excluded from that pair. With multiple pairs, analysis-by-analysis exclusion can produce different Ns. `/MISSING=LISTWISE` would exclude a worker missing any variable among all requested pairs. These rules follow IBM's [T-TEST missing-value documentation](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=test-missing-subcommand-t-command).

The supplied files are complete. Do not code a missing or failed report as zero seconds. If you edit a disposable copy to introduce missing data, inspect each procedure's N: separate descriptives can use different available cases, whereas the paired test needs both observations. Investigate missingness and explain exclusions before interpreting a result. More than two occasions, repeated trials, clustered crews, censored times, or failed detections need additional modeling decisions.

Preserve each worker's measurements on the same row. Sorting just one column destroys matching. Never create pairs by aligning two independent groups after sorting their scores.

## Exercises

1. State the null hypothesis and the unit of analysis for each study. Why would pairing worker 101 with worker 201 be unjustified?
2. Calculate the independent SE and t from the group summaries. Explain why its two SPSS variance rows coincide here.
3. Calculate the paired SE, t, and df. Which SD belongs in the paired-test denominator?
4. If the paired order were reversed to after minus before, what would happen to the mean difference, t, interval, and two-sided p-value?
5. Does either 95% interval establish a mean reduction of at least 5 s? Does a significant paired test show that everyone improved or that practice caused improvement?
6. In a disposable copy only, replace worker 301's after value with SPSS system-missing (`.` in inline data), then rerun the entire file. Predict the paired N and df. Would replacing the missing value with zero be acceptable?

### Answer key

1. Independent H₀: the population mean time under standard briefing equals the population mean time under scenario practice; one worker is the unit. Paired H₀: the population mean within-worker before-minus-after difference is zero; one worker supplies one difference. IDs 101 and 201 identify different independently assigned workers with no designed match.
2. `sqrt(64/20 + 64/20) = 2.529822 s`; `6/2.529822 = 2.371708`. Equal group sizes and sample SDs make the pooled and Welch results coincide in this special dataset.
3. `4.542200/sqrt(20) = 1.015667 s`; `6/1.015667 = 5.907449`; df = 19. Use the SD of the 20 within-worker differences, 4.542200 s.
4. Mean = −6.00 s, t = −5.907449, 95% CI [−8.125815, −3.874185] s. The two-sided p-value is unchanged. The substantive direction must be interpreted using the new subtraction order.
5. Neither interval's lower bound reaches 5 s. The paired data include two slower workers and one unchanged worker. There is no randomized concurrent comparison group, so a causal claim is unsupported.
6. Paired N = 19 and df = 18; worker 301 contributes no difference. The complete-case before and after means in the paired analysis also change. Zero would falsely record instantaneous correct reporting, not missingness. Restore the original copy after the exercise.

## Numerical verification

[expected_results.json](https://github.com/stephenlewandowski/research-methods-analysis/blob/87c593ba3e9240b1f4ec4d4fa290daa1d3da9e54/projects/t-test-teaching-package/spss-worked-example/expected_results.json) stores full-precision independently calculated reference values. To verify them with Python 3.10 or later, run [verify_expected_results.py](https://github.com/stephenlewandowski/research-methods-analysis/blob/87c593ba3e9240b1f4ec4d4fa290daa1d3da9e54/projects/t-test-teaching-package/spss-worked-example/verify_expected_results.py) from the repository root:

```powershell
python projects/t-test-teaching-package/spss-worked-example/verify_expected_results.py
```

The command above assumes a terminal at the repository root; otherwise supply the script's absolute path. It needs only the Python standard library. It compares both CSVs to their syntax files' inline observations, checks unique worker IDs and complete pairs, recomputes both tests and confidence intervals, checks the paired variance identity, and compares them with the JSON reference. Student-t probabilities use a regularized incomplete-beta calculation; critical values use bisection. The `--write` flag is for maintainers intentionally updating the reference after a dataset change.

Both full syntax files were also executed successfully in **IBM SPSS Statistics 29.0.2.0** on 16 October 2026 using IBM's external Python integration. The native mean differences, standard errors, t statistics, degrees of freedom, two-sided probabilities, and confidence intervals agree with the independent numerical references. The paired difference diagnostics and the equivalent one-sample test also ran. The [native output snapshots](https://github.com/stephenlewandowski/research-methods-analysis/blob/87c593ba3e9240b1f4ec4d4fa290daa1d3da9e54/projects/t-test-teaching-package/spss-worked-example/native-output/README.md) contain SPSS-produced text and full-precision OMS XML, including the original `.000` display for the very small paired-test p-value. The expected tables above remain independently reconstructed teaching references.

See [source/validate_spss.py](https://github.com/stephenlewandowski/research-methods-analysis/blob/87c593ba3e9240b1f4ec4d4fa290daa1d3da9e54/projects/t-test-teaching-package/source/validate_spss.py) for the native validation runner and the package's [build instructions](https://github.com/stephenlewandowski/research-methods-analysis/blob/87c593ba3e9240b1f4ec4d4fa290daa1d3da9e54/projects/t-test-teaching-package/BUILD.md) for the SPSS launcher command. SPSS is required to regenerate native exports; the standard-library verification command above is available without it.

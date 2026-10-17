---
layout: teaching-document
title: "The t-test on the airport ramp: Instructor notes"
description: "The t-test on the airport ramp: Instructor notes using synthetic RSCH650 teaching data."
document_type: Instructor notes
material_title: Research Methods and Analysis
material_path: /teaching/materials/research-methods-analysis/
updated: October 2026
---

# The t-test on the airport ramp

RSCH 650 — Research Methods and Analysis | Prepared 15 October 2026

## Use in class

The 2 minute, 6 second animation introduces a two-sided Welch independent-samples t-test using a hypothetical airport ground-personnel training study. It has on-screen captions and no audio, allowing the instructor to narrate, pause, and discuss. Open `RSCH650_T_Test_Classroom.html` in a browser for offline playback and chapter navigation, or insert the MP4 into a presentation or course page.

The HTML contains its own video and poster. It requires no internet connection or installation. Select a chapter to pause at its start, then use the video controls to play. A text transcript is included beneath the player. The MP4 is H.264, 1280 × 720 pixels, 15 frames per second. The matching caption files are included for platforms that accept SRT or WebVTT uploads.

## Learning objectives

After viewing, students should be able to identify when an independent two-sample t-test fits a study, explain how the mean difference is scaled by its standard error, distinguish individual variability from uncertainty in the difference, interpret a two-sided p-value, and connect statistical evidence with effect size and operational importance.

## Scenario and boundaries

Imagine randomly assigning 40 ground personnel individually to a standard safety briefing or scenario-based practice, with 20 workers in each group. Each worker completes one identical simulated ramp-hazard reporting task. The outcome is the number of seconds until the worker correctly reports the hazard. Lower is faster. This constructed example assumes everyone correctly reports the hazard within the observation period.

All observations are synthetic, deliberately scaled to exact teaching means and sample standard deviations. They are not real aviation performance data, an actual experiment, an operational benchmark, or evidence for the effectiveness of a particular training method. The two groups contain different workers; one response is used per worker. The example concerns a continuous time outcome, not a count of accidents or a proportion of missed hazards.

Welch's test does not require equal population variances. The examples intentionally use equal sample SDs and sizes for easier arithmetic; the Welch and pooled-test results therefore coincide in these examples. The method should still be chosen to fit the actual research design.

## Numerical checks

The difference is always standard briefing minus scenario practice. All p-values are two-sided. The alpha level for the baseline demonstration is .05.

| Illustration | n per group | Briefing mean | Practice mean | SD in each group | Difference | SE of difference | t | df | p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 20 | 48 s | 42 s | 8 s | 6 s | 2.529822 s | 2.371708 | 38 | .0228758 |
| Larger mean gap | 20 | 48 s | 36 s | 8 s | 12 s | 2.529822 s | 4.743416 | 38 | .00002949 |
| More variability | 20 | 48 s | 42 s | 14 s | 6 s | 4.427189 s | 1.355262 | 38 | .1833358 |
| Larger planned sample | 80 | 48 s | 42 s | 14 s | 6 s | 2.213594 s | 2.710524 | 158 | .0074604 |

Baseline 95% confidence interval: **0.878643 to 11.121357 seconds**. A positive value favors scenario practice on this particular time measure. The interval is for the population mean difference, not for individual workers' times.

The statistics were computed directly from the synthetic observations and checked against SciPy's independent-samples t-test with `equal_var=False`. The confidence interval uses the Welch standard error and t critical value. The independent syntax and the supplementary paired example have now been executed in IBM SPSS Statistics 29.0.2.0. Native t statistics, degrees of freedom, two-sided p-values, and confidence intervals agree with independent calculations; see the [worked example and native output](spss-worked-examples.html).

The larger-sample and other sensitivity illustrations are separate constructed studies, not additional observations added to the original study until a p-value crosses .05. They hold selected sample summaries fixed to isolate statistical relationships. In actual repeat samples, the observed means and SDs would vary.

## Suggested discussion stops

| Time | Teaching point | Prompt and instructor answer |
| --- | --- | --- |
| 0:00 | Study question | What is the unit of analysis? One worker. What differs between groups? Assigned training method. |
| 0:14 | Difference in means | Do overlapping individual times rule out a difference in population means? No. The t-test compares the estimated mean difference with its uncertainty. |
| 0:27 | Standard error | What does 8 s describe, and what does 2.53 s describe? The former is individual sample variability within each group; the latter estimates uncertainty in the difference between sample means. |
| 0:42 | Conditional probability | Does p = .023 mean there is a 2.3% chance that the methods are equal? No. Under the null model, it is the probability of a t statistic at least this extreme in either direction. |
| 0:59 | Larger effect | Why does t double? The mean difference doubles while the standard error stays fixed. |
| 1:10 | More scatter | Does p = .183 establish equivalent training outcomes? No. It is insufficient evidence against equal means at .05, not an equivalence result. |
| 1:23 | Larger sample | Does adding participants make individual workers less variable? No. At the same individual SD, a larger independent sample estimates the mean difference more precisely. |
| 1:36 | Practical meaning | If a team had prespecified a minimum worthwhile improvement of 5 s, does this interval establish an improvement of at least 5 s? No; the interval includes improvements smaller than 5 s. The 5 s threshold is only a discussion example. |
| 1:52 | Study design | What changes if the same workers are tested before and after? Measurements are paired; analyze within-worker differences with an appropriate paired method. |

## Assumptions and interpretation

Check independence, the sampling or assignment process, a continuous outcome, and distributions/outliers. For small samples, pronounced skew or extreme observations can undermine the usual t-based inference. Welch's unequal-variance accommodation does not solve dependence, selection bias, measurement problems, or severe distributional issues. In a real task, missed detections, censored times, repeated trials, and accuracy-speed tradeoffs require attention; simply discarding missed detections can bias a comparison.

Random assignment supports a causal interpretation for the study participants when the design is implemented properly. Generalization to other crews, conditions, or airports requires a separate judgment. Faster correct reporting in a simulator does not by itself establish fewer real-world incidents.

The 95% confidence level describes the long-run coverage of the interval procedure under its assumptions. Avoid saying that 95% of individual workers improve by an amount inside the interval or that there is a 95% frequentist probability that this fixed population parameter lies in this particular computed interval.

## Reproduce the baseline in SPSS

Open `ramp_hazard_training.sps` and run the full file. It contains its own data, so no local path changes are necessary. Training is coded 1 = standard briefing and 2 = scenario practice. `report_seconds` is the continuous outcome. Read the **Equal variances not assumed** row for the Welch result, using the two-sided p-value and 95% confidence interval. The CSV contains the same 40 baseline observations for use in R, Stata, or SPSS.

Expected report: In this synthetic example, the standard-briefing group had a longer mean reporting time (M = 48.00 s, SD = 8.00) than the scenario-practice group (M = 42.00 s, SD = 8.00). Welch's t(38) = 2.37, p = .023, mean difference = 6.00 s, 95% CI [0.88, 11.12].

## Supplementary SPSS worked examples

The [SPSS lab](spss-worked-examples.html) walks through the original independent comparison and a separate matched before/after study of 20 synthetic workers. The latter uses one row per worker, two measurements per row, and the within-worker difference before minus after. Its mean reduction is 6.00 s, SD of the differences is 4.5422 s, and SE is 1.0157 s: paired t(19) = 5.9074, p < .001, 95% CI [3.8742, 8.1258].

The examples illustrate different study designs, not a comparison of the effectiveness of their training programs. The uncontrolled before/after example cannot establish a causal training benefit. Ask students why the paired test uses the SD of differences, why the observations within a pair are related, and why a displayed SPSS p-value of .000 should be reported as p < .001 rather than p = 0. The lab includes native output, instructions for reading the correct tables, diagnostic prompts, exercises, and an answer key.

## Method references

- NIST/SEMATECH e-Handbook, [Two-Sample t-Test for Equal Means](https://www.itl.nist.gov/div898/handbook/eda/section3/eda353.htm): independent-samples test statistic, Welch–Satterthwaite degrees of freedom, and two-sided reference distribution.
- IBM SPSS Statistics documentation, [Examples: T-TEST command](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=test-examples-t-command): syntax reference for the analysis command and confidence-interval request. The supplied syntax uses basic commands intended for the user's SPSS 29 installation.

These sources support the method. The aviation scenario, synthetic data, graphics, and teaching sequence were created for this course preparation.

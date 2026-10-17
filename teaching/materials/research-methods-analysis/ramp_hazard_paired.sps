* RSCH650: a separate synthetic before-and-after study of 20 workers.
* Each row is the SAME worker measured before and after scenario practice.
* These workers are NOT the two independent groups in ramp_hazard_training.sps.
* All times are seconds to correctly report a hazard in a simulator task.
* Every worker correctly reports on both occasions; no missing or censored times.
* The two occasions use comparable tasks, with one recorded response per occasion.
* This uncontrolled before/after illustration cannot establish a causal benefit.
* Run the complete file. Inline data require no folder or import-path changes.

NEW FILE.
SET DECIMAL=DOT.
DATA LIST FREE /worker_id (F3.0) before_seconds (F8.2) after_seconds (F8.2).
BEGIN DATA
301 35 37
302 43 33
303 49 40
304 51 50
305 38 30
306 45 42
307 60 50
308 55 50
309 48 48
310 42 31
311 57 50
312 46 42
313 53 41
314 40 41
315 62 56
316 44 35
317 50 48
318 37 29
319 59 55
320 46 32
END DATA.
DATASET NAME RampPaired.
WEIGHT OFF.
SPLIT FILE OFF.
FILTER OFF.

VARIABLE LABELS
 worker_id 'Synthetic worker identifier'
 before_seconds 'Before practice: correct hazard-reporting time (seconds)'
 after_seconds 'After practice: correct hazard-reporting time (seconds)'.
VARIABLE LEVEL worker_id (NOMINAL) before_seconds after_seconds (SCALE).
FORMATS worker_id (F3.0) before_seconds after_seconds (F8.2).

* A positive difference means faster reporting after practice.
COMPUTE reduction_seconds=before_seconds-after_seconds.
VARIABLE LABELS reduction_seconds 'Before minus after reporting time (seconds)'.
VARIABLE LEVEL reduction_seconds (SCALE).
FORMATS reduction_seconds (F8.2).
EXECUTE.

DESCRIPTIVES VARIABLES=before_seconds after_seconds reduction_seconds
 /STATISTICS=MEAN STDDEV MIN MAX.

* Assess the DIFFERENCES for extreme outliers and substantial non-normality.
* Plots inform judgment; a normality-test p-value is not a pass/fail gate.
EXAMINE VARIABLES=reduction_seconds
 /PLOT=BOXPLOT HISTOGRAM NPPLOT
 /STATISTICS=DESCRIPTIVES
 /CINTERVAL=95
 /MISSING=LISTWISE
 /NOTOTAL.

* This produces Paired Samples Statistics, Correlations, and Test tables.
* Read the TWO-SIDED p-value in the Test table, not the correlation p-value.
T-TEST PAIRS=before_seconds WITH after_seconds (PAIRED)
 /CRITERIA=CI(.95)
 /MISSING=ANALYSIS.

* Optional arithmetic check: a paired t-test equals this one-sample test.
* This is the same hypothesis and data, not a second independent finding.
T-TEST
 /TESTVAL=0
 /VARIABLES=reduction_seconds
 /CRITERIA=CI(.95)
 /MISSING=ANALYSIS.

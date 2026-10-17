* RSCH 650: synthetic ramp hazard reporting example.
* Each row is one different worker; all observations are invented for teaching.
* Group 1 = standard briefing; group 2 = scenario practice.
* Outcome = seconds to correctly report a hazard in a standardized simulator task.
* Read the Equal variances not assumed row for the Welch test.
DATA LIST FREE /worker_id (F3.0) training (F1.0) report_seconds (F12.9).
BEGIN DATA
101 1 49.884519585
102 1 45.217597775
103 1 43.937311553
104 1 64.718440458
105 1 50.926103314
106 1 42.199029670
107 1 61.623736105
108 1 41.976901259
109 1 50.242003067
110 1 45.474706490
111 1 32.492043991
112 1 40.811213188
113 1 48.649716031
114 1 44.037276127
115 1 64.572832941
116 1 46.886470254
117 1 41.897854426
118 1 45.729290019
119 1 48.158302178
120 1 50.564651571
201 2 43.489953108
202 2 37.366789621
203 2 45.511309026
204 2 46.287791565
205 2 47.582381178
206 2 42.252996471
207 2 31.292767010
208 2 35.155943799
209 2 32.334230551
210 2 44.732406823
211 2 47.817233419
212 2 38.251111999
213 2 33.675646433
214 2 52.504854396
215 2 33.783197257
216 2 33.168587384
217 2 50.378896269
218 2 37.418376582
219 2 61.844849203
220 2 45.150677905
END DATA.
DATASET NAME RampHazard.
VARIABLE LABELS training 'Assigned training method'
 report_seconds 'Time to correctly report a simulated ramp hazard (seconds)'.
VALUE LABELS training 1 'Standard briefing' 2 'Scenario practice'.
VARIABLE LEVEL training (NOMINAL) report_seconds (SCALE).
FORMATS report_seconds (F8.2).
T-TEST GROUPS=training(1 2)
 /VARIABLES=report_seconds
 /MISSING=ANALYSIS
 /CRITERIA=CI(.95).

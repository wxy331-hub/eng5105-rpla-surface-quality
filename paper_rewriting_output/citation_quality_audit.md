# Citation Quality Audit

- Output directory: `D:\12591\Documents\5105\paper_rewriting_output`
- Scene: report_review
- Research-stage candidate target: 20
- Candidate entries sampled below: 20
- Candidate sample result: 20 verified | 0 mismatched | 0 dead
- Candidate-sample quality score: 89/100
- Final-report reference count: 49
- Final-report citation uses: 169 expanded numeric uses in each language version

The table below is the research-stage quality sample, not the final reference list. The final list was enlarged after technical review and now comprises 16 peer-reviewed publications, 12 manufacturer or supplier primary sources, eight standards/government/institutional sources, four course-controlled documents and nine formally cited unpublished project records. The internal records identify provenance while the report reproduces their decision-relevant results and limitations, so submission does not depend on access to the project directory. The paired validator confirms that all 49 entries, URLs and citation numbers are identical across the English and Chinese reports.

> Each entry below includes a teaching note explaining *why* the citation quality matters.

## Per-Citation Analysis

| ID | DOI | Type | Resolves | Title Match | Year Match | Score | Status |
|---|---|---|---|---|---|---|---|
| R01 | 10.3390/polym15173651 | sota | yes | 81% | yes | 85 | verified |
| R03 | 10.1016/j.clwas.2023.100100 | sota | yes | 100% | yes | 85 | verified |
| R05 | 10.1016/j.cirpj.2024.08.007 | sota | yes | 100% | yes | 95 | verified |
| R09 | 10.1089/3dp.2022.0222 | sota | yes | 100% | yes | 95 | verified |
| R10 | 10.1016/j.rineng.2024.103013 | sota | yes | 100% | yes | 95 | verified |
| R15 | 10.1039/D5SU00959F | sota | yes | 100% | yes | 100 | verified |
| R18 | 10.3390/ma11081322 | sota | yes | 100% | yes | 60 | verified |
| R19 | 10.1016/j.jclepro.2018.06.275 | sota | yes | 100% | yes | 60 | verified |
| V01 | 10.1007/s11263-026-02743-0 | benchmark | yes | 100% | yes | 100 | verified |
| V02 | 10.1016/j.compind.2024.104151 | benchmark | yes | 100% | yes | 95 | verified |
| V03 | 10.1109/CVPR52733.2024.02159 | benchmark | yes | 100% | yes | 95 | verified |
| V05 | 10.1016/j.cscm.2023.e02561 | sota | yes | 100% | yes | 85 | verified |
| V07 | 10.1016/j.measurement.2024.114 | sota | yes | 100% | yes | 95 | verified |
| V09 | 10.3390/app14010235 | sota | yes | 100% | no | 95 | verified |
| V17 | 10.1109/TIM.2024.3390198 | sota | yes | 100% | yes | 95 | verified |
| V19 | 10.1007/s00170-023-11789-0 | sota | yes | 100% | yes | 85 | verified |
| S06 | 10.1016/j.mfglet.2024.09.153 | sota | yes | 100% | yes | 95 | verified |
| S08 | 10.6028/NIST.SP.800-82r3 | sota | yes | 100% | yes | 85 | verified |
| S10 | 10.1016/j.patter.2023.100804 | critique | yes | 100% | yes | 85 | verified |
| S11 | 10.1109/ACCESS.2024.3383047 | benchmark | yes | 100% | yes | 95 | verified |

## Final-Report Diversity and Fitness Check

- **rPLA and material context:** peer-reviewed sources cover recycled-filament variability, moisture, mechanical behaviour and life-cycle implications.
- **industrial visual inspection:** dataset, anomaly-detection, line-scan and surface-defect studies support the imaging and validation discussion without transferring their reported accuracy to rPLA.
- **alternative sensing:** filament-diameter sensing and laser-line profilometry provide genuine concept alternatives and clarify why the proposed system remains a visible-surface inspection design.
- **implementation authority:** camera, processor, microcontroller, ADC, op-amp and GPIO claims use manufacturer documentation; observed prices and stock use dated supplier pages.
- **safety, governance and sustainability:** ISO, NIST, OAIC, Australian legislation, UN and Monash sources support system-level obligations.

No external paper is used as evidence that this project has already achieved defect accuracy, calibration, Raspberry Pi deployment, STM32 safe-output control or production-line performance. Those claims remain tied to the internal evidence register or to future verification gates.


## Scene-Specific Citation Strategy

For **report_review** papers, your citation strategy should:

- **direct task or state-of-the-art paper**: Cite representative methods across the field. Breadth matters more than exhaustiveness.
- **foundational method or theory paper**: Cite the key methods that define the field. Explain their contributions.
- **dataset, benchmark, or evaluation protocol paper**: Cite datasets if you use them.
- **survey, review, or meta-analysis**: Essential: cite 3-5 surveys to establish the review's coverage.
- **domain-application or impact paper**: Include application papers that show real-world relevance.
- **limitation, robustness, reproducibility, or ethics paper**: Include limitation/robustness discussions to show balanced coverage.

## Citation Strategy Principles

- **Diversity over density.** A narrow citation pool makes your Introduction read as insular. Mix SOTA, foundational, benchmark, survey, and application papers.
- **Recency signals engagement.** Most citations should be from the last 3 years. Older citations are fine for foundational work, but they need a reason to be there.
- **Verifiability is non-negotiable.** Every DOI must resolve. A dead DOI in your final paper is a credibility failure that reviewers notice immediately.
- **Type matters by venue.** Journals expect deep SOTA coverage. Reports expect broad survey coverage. Competitions expect benchmark and leaderboard coverage. Match your strategy to your scene.

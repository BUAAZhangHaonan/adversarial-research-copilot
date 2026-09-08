# Selection calibration examples

These examples are synthetic. They are not actual papers, verified results, user research topics, or citations. Apply their distinctions to the current evidence; do not copy their subject matter into the user's research agenda.

## Example 1: an untested hypothesis can belong in the main report

Suppose original studies establish a reproducible performance change when relevant information is moved farther from its use, but they also change the number of distractors. A new card proposes to isolate these two variables under matched inference budgets. The closest-work check has found no result establishing this separation in the specified setting. Both variables can be manipulated independently, and the proposed measurements have a positive control.

MAIN_REPORT is justified if those premises are really supported. The new experiment has not run, but the motivation and ability to distinguish explanations are credible. State the untested claim and practical risk. Do not say the proposed mechanism has already been confirmed.

## Example 2: a useful result does not require a favored hypothesis

Two plausible explanations for an observed failure imply different responses to a controlled intervention. Either outcome would change which system component researchers should improve. The existing observation is supported, the intervention is feasible, and the measurements separate the explanations.

This may be MAIN_REPORT even without a justified probability that explanation A will win. The value is a discriminating answer, not a guaranteed positive leaderboard result. Do not manufacture a preferred mechanism or a success percentage.

## Example 3: an unidentifiable test is a lead

A card claims to distinguish information lost during storage from information missed during retrieval, but only measures the final task score. The proposed manipulation changes both storage and retrieval, and there is no validated way to inspect what was retained.

LEAD_ONLY is appropriate while the discriminating measurement remains missing. Explain that final accuracy alone cannot identify the cause. Specify the needed measurement or intervention. Do not demote it merely because an experiment remains to be run; demote it because the proposed experiment cannot yet answer its own question.

## Example 4: ordinary stitching does not qualify

A proposal combines a retrieval module, a graph, a critic and an auxiliary loss. It offers no observation requiring these components, no argument that a simpler baseline cannot answer the question, and no interaction prediction. It promises a large gain because each component is popular.

NOT_RETAINED for unsupported stitching is appropriate. Renaming the pipeline or adding a new dataset does not provide a contribution. Do not rescue it by inventing an unrelated new question.

## Example 5: a combination exception is conditional and demanding

Supported prior observations show two specific, interacting failure modes. A candidate argues that neither intervention alone changes the bottleneck but their interaction should. It defines a matched-budget factorial comparison, an interaction statistic, a practically meaningful improvement criterion tied to the application, and a measurement that distinguishes the proposed interaction from extra computation.

The combination may qualify for MAIN_REPORT only if the motivation, meaningful improvement prospect, novel explanatory claim and test are all credible from the supplied evidence. No actual improvement has yet been demonstrated. If the justification consists only of hoped-for synergy or an arbitrary improvement percentage, use LEAD_ONLY or NOT_RETAINED according to the remaining scientific value. A gain without a new explanation does not satisfy this user's combination exception.

## Example 6: the same question is not necessarily duplication

The closest paper explicitly asks why a technique works but reports only an aggregate gain and speculates about two causes. A card proposes a valid intervention that separates those causes. If the paper and other checked work have not already established the proposed conclusion, this can be a new mechanism contribution to an existing problem.

Do not mark it duplicate because the question appears in the related-work section. Conversely, if the closest paper already performs the same intervention under the relevant conditions and establishes the same conclusion, changing vocabulary or a routine benchmark is not a new contribution.

## Boundary reminder

The main report means worth a human's next investigation, not proven correct, accepted by a venue, or guaranteed to succeed. LEAD_ONLY means a specific prerequisite for judging the card is missing. NOT_RETAINED needs a defensible reason; technical failures are never disguised as scientific rejection.

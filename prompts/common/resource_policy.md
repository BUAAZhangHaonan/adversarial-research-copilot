# Resource estimation

Estimate the smallest informative investigation, not the cost of an imagined full paper campaign. Do not run the proposed research experiment to obtain an estimate.

Use RTX 3090 24GB where it can realistically execute the workload. Use A100 for workloads needing its memory or capabilities, stating the assumed memory variant if it is not known. Report GPU count, training GPU-hours, inference GPU-hours, wall-time ranges, workload assumptions and evidence for the estimate. Do not convert A100 and 3090 with a universal speed multiplier or sum VRAM as if it were automatically a shared memory pool.

Describe the model scale, precision, accessible weights, sequence length, data size, repetitions and major training/inference work. Reuse public measured throughput only when its setting is comparable; otherwise label it an extrapolation. Unknown throughput warrants a broad transparent range, not invented precision.

The user generally has sufficient resources for normal research development. Do not reject a card merely because it needs several GPUs or a substantial but plausible experiment. Large-language-model pretraining from scratch is outside the default plan. Access to proprietary weights, unavailable datasets or undisclosed services cannot be assumed.

Separate a hard incompatibility from an estimate that remains uncertain. Give the least expensive valid test and explain what additional resources a later expansion would require. A cheap test that cannot distinguish explanations is not a valid resource saving.

# Structured result contract

Use the exact JSON schema provided in the task. Return one complete JSON object as the final answer, without a Markdown fence, an additional prose preface, or a repeated YAML version. Native tool calls may precede the final answer when tools are available.

The top-level envelope is:
{"schema_version":"arc.v1","task_id":"TASK_FROM_INPUT","subject":{"campaign_id":null,"run_id":null,"card_id":null,"card_version":null},"result_status":"complete","result":{},"evidence_requests":[],"capability_requests":[],"note":null}

Copy task and subject identifiers from the input. The concrete result schema is task-specific and authoritative for field types. This envelope example is not an answer to the research task. Do not reuse its placeholder identifiers.

Use null for an unknown optional fact and an empty array for an actually empty collection where the schema permits it. Do not invent evidence to complete a required field. A zero-candidate discovery is valid. Missing judgments for supplied candidates, duplicate identifiers, invented source references, and silently discarded malformed entries are not valid empty results.

Evidence requests must identify a specific question, related issue or claim, the source/query needed, and how the answer can change the decision. Capability requests describe a missing tool capability and its required input/output; they are not permission to implement it.

The runtime decides execution state, starts tools, allocates identifiers, enforces budgets, and records accepted versions. Do not fabricate execution success or override these controls. Scientific assessments and suggested next actions belong only in the task's declared fields. Never append a second STOP tag or encode control instructions in prose.

Provide brief reasons that can be checked against evidence and explicit premises. Do not expose or demand private chains of thought. Follow the schema even when the correct result is inconclusive or negative.

result_status is complete, needs_evidence or blocked. A complete result must validate against the task-specific result schema. For needs_evidence or blocked, result may be null, but note must explain the concrete missing prerequisite and requests must be explicit when applicable. The runtime must not accept a blocked object as a completed scientific judgment.

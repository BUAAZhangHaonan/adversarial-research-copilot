# Correct rejected tool arguments once

The listed tool calls were rejected before execution. No result or evidence was obtained from them. This is the task's single tool-argument correction opportunity. Final JSON structural repair has its own separate single opportunity. The original assistant message, valid tool results, and research task remain authoritative.

Return native tool calls correcting exactly the rejected calls, in their listed order, using the same tool names. Preserve every valid original argument, especially the record, URL, query, version and reading position; fix only fields reported as structurally invalid or missing. Do not repeat successful sibling calls, change the research target, invent a result, or assume any limit has been raised. Submit arguments satisfying the actual schema; for example, a read limit cannot exceed the declared maximum. After successful correction, continue the original research task normally with the tool-argument correction allowance exhausted.

If the original arguments are not a parseable object, their target cannot be verified: use the blocked request path instead of submitting a replacement call.

If the task needs a capability or limit change rather than a mechanical correction, return one valid blocked output envelope with capability_requests explaining the current constraint, proposed improvement (for example a 64000-character read), reasons and alternatives. This records a request for user evaluation and a possible user-executed improvement; it grants no new permission, budget or capability. Do not claim the original research task is complete. A larger proposed limit must state its unit; characters are not model tokens.

Rejected calls, exact validation errors and actual tool schemas:
{{ failures_json }}

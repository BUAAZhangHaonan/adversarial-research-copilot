# Repair an invalid structured response

Task ID: {{ task_id }}
Subject: {{ subject_json }}

The previous response did not satisfy its output contract. Repair its JSON structure using the supplied response, input records and validation errors. Do not perform fresh research, alter the question, invent a citation or manufacture a verdict merely to satisfy the schema.

## Original task data

{{ payload_json }}

## Previous response

{{ previous_response_json }}

## Validation errors

{{ validation_errors_json }}

## Required schema

{{ output_schema_json }}

Return one complete JSON object. Preserve every scientifically meaningful statement that is supported by the original response and records. Represent genuinely missing information explicitly where the schema permits it. If a required scientific judgment was not actually made and cannot be recovered from these records, return the task's unresolved/protocol outcome rather than silently approving or rejecting it. This is the single permitted structural correction, not permission to restart an entire research stage.

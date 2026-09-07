# read_record

Open the relevant stored card, proposal version, evidence segment or issue record by its registered identifier. Use this when a compact summary omits a condition necessary for the current decision. The operation is read-only. Preserve source provenance, prior rejection conditions and version boundaries. Do not treat an old model judgment as an established scientific fact. Request the needed record rather than loading the entire archive or conversation history.

## Cached source coverage

For source text, content_offset and cached_content_chars describe the locally stored text. more_cached_content only says whether another local page exists. content_total_chars and content_complete retain the original source metadata; an unknown total remains unknown. Exhausting the cache does not establish that the full source was read. If requires_source_fetch is true, read_record cannot retrieve the missing original text: use an actually available read_web or read_paper operation to extend the source, or record the access limitation. Do not close a full-text verification or assert that a condition is absent merely because the cached prefix ended. Even a complete stored source must be read over the relevant ranges before making a coverage claim.

A metadata-only source has no stored body: content is null, cached_content_chars is zero, content_complete is false and requires_source_fetch is true. Repeating read_record on that unchanged source cannot produce body text. Search snippets remain metadata; use an available original-source fetch if the body is needed, otherwise retain the unresolved access limitation.

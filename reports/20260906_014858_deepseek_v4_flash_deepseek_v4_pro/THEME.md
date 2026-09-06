This mandate targets LLM agent systems acting over long interaction horizons (100+ turns) and the memory architectures that support them. The goal is to map where sustained-horizon agentic behavior breaks — retrieval failures, stale memory, cumulative errors, goal drift — and how memory designs attempt to mitigate that. Explicitly out of scope: model-level context engineering and non-agentic static RAG. A paper belongs if it studies an agent with persistent state over many steps, not if it merely improves context length.

```yaml
theme:
  field: memory mechanisms and failure modes in long-horizon LLM agent systems
  subtopics:
    - agent memory architectures (episodic/semantic memory stores, scratchpads, memory modules for agents)
    - long-horizon agent evaluation: benchmarks and metrics for sustained 100+ turn/task performance
    - degradation and failure analyses: error accumulation, goal drift, stale/conflicting memory
    - memory consolidation, summarization, forgetting, and update over long sessions
    - retrieval and attention interactions with long transcripts (retrieval misses, memory interference)
  must_include:
    - LLM agent / language agent
    - memory architecture / memory module
    - long-horizon / 100-turn / multi-turn
    - performance degradation / failure mode
    - retrieval-augmented memory / RAG over history
    - benchmark / evaluation
  exclude:
    - model-level long-context methods (KV-cache, streaming attention, context compression)
    - non-agentic document QA or static RAG pipelines
    - multi-agent orchestration/planning without a memory component
  search_queries:
    - "LLM agent memory architecture long-horizon performance degradation"
    - "long-horizon LLM agent benchmarks sustained success 100 turns"
    - "multi-turn LLM agent error accumulation memory failures"
    - "LLM agent episodic semantic memory consolidation summarization"
    - "agent memory retrieval stale information forgetting long sessions"
```

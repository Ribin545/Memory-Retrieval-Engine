# Memory Architecture Design Document

## 1. What to Extract and Store (Schema + Rationale)

### Session Input Schema
Each session produces a structured JSON record with the following fields:

| Field | Stored As | Rationale |
|-------|-----------|-----------|
| `session_id` | Metadata | Enables traceability and audit logs |
| `timestamp` | Metadata | Supports temporal queries and recency scoring |
| `theme` | Topic tag index | Allows topic-based filtering ("work stress", "family conflict") |
| `emotional_tone` | Emotion metadata (primary, secondary, intensity) | Drives emotion-aware retrieval and response policy |
| `key_moments` | Individual memory cards | Granular, actionable details: exact phrases, commitments, coping strategies |
| `summary` | Session summary card | Captures narrative arc and context for broad retrieval |
| `risk_flags` | Safety metadata (sensitivity score) | Blocks unsafe references in greetings or notifications |
| `follow_up_topics` | Follow-up intent cards | Powers re-engagement: unresolved topics trigger check-ins |

### Why This Schema?
- **Rich metadata enables multi-dimensional retrieval**: Not just text search, but emotion-aware, topic-aware, safety-aware selection
- **Separation of concerns**: `key_moments` for specifics, `summary` for context, `follow_up_topics` for continuity
- **Explicit over implicit**: Storing `risk_flags` upfront prevents the system from inferring danger incorrectly

---

## 2. Retrieval at Session Start (Low Latency)

### Challenge
When a user opens a new session, we need relevant memories in <200ms. Loading a full vector DB query + LLM judge + policy lookup is too slow for a greeting.

### Solution: Tiered Retrieval

```
Session Start
    ↓
Tier 1: Cached "Safe Opener Memory" ( < 5ms )
    ↓
Tier 2: Rule-based pre-selected memory ( < 50ms )
    ↓
Tier 3: Full vector + judge pipeline (background, async )
```

**Tier 1 — Pre-computed safe memories:**
- At the end of each session, compute one `safe_to_reference_in_opener` memory
- Cache it in Redis/session store keyed by `user_id`
- On session start: instant lookup, no DB query

**Tier 2 — Fast rule-based selection:**
- If cache miss, query an inverted index (not vector DB) on:
  - `safe_to_reference_in_opener = true`
  - `sensitivity < 0.5`
  - `resolved_status != resolved` (prioritize continuity)
  - Sort by recency
- Returns in <50ms from a lightweight index (e.g., SQLite or in-memory)

**Tier 3 — Full pipeline (async):**
- Trigger vector DB retrieval + LLM judge in background
- Results available for Turn 2+ of conversation
- Avoids blocking the greeting

### Why This Works
- **Latency-critical path** (greeting) uses pre-computed or indexed data
- **Quality-critical path** (deep retrieval) runs async without user-perceived delay
- **Fallback**: If Tier 1/2 return nothing, generic warm greeting — no wrong memory injected

---

## 3. Privacy and User Control

### Data Minimization
- Each memory includes `user_id` for isolation
- Vector DB queries are always filtered by `user_id`
- No cross-user memory leakage possible by design

### User Controls (Planned)

| Control | Implementation |
|---------|---------------|
| **View memories** | API endpoint: `GET /my-memories` — returns user's own cards |
| **Delete a memory** | `DELETE /memories/{memory_id}` — removes from JSON + rebuilds vector index |
| **Edit a memory** | `PATCH /memories/{memory_id}` — user can correct summary or exact value |
| **Export data** | `GET /export` — GDPR-style JSON dump of all user memories |
| **Opt-out of re-engagement** | Boolean flag in user profile — blocks all notification generation |
| **Memory expiry** | User can set TTL (e.g., "forget this after 30 days") |

### What the System Never Does
- **Never stores raw chat transcripts**: Only structured summaries and extracted cards
- **Never shares memories across users**: Strict `user_id` filtering at every layer
- **Never sends exact values in notifications**: Vague copy only, even for low-sensitivity memories
- **Never references high-sensitivity memories in openers**: `safe_to_reference_in_opener` gate

---

## 4. What NOT to Store, and Why

| Not Stored | Why |
|------------|-----|
| **Raw conversation transcripts** | Too verbose, privacy risk, hard to index. Structured summaries and key moments are sufficient. |
| ** Personally identifiable information (PII)** | No names, addresses, phone numbers. If mentioned in session, redact or mark as high-sensitivity and avoid referencing. |
| **Medical diagnoses or clinical assessments** | The system is not clinical. Risk flags are heuristics, not diagnoses. Storing "diagnosed with depression" would be unsafe and misleading. |
| **User's location or device info** | Not relevant to emotional support context; privacy risk outweighs utility. |
| **Other users' data in cross-session references** | E.g., "Your brother's contact info" — if mentioned, store only as anonymized relationship context, not as a contact record. |
| **Exact timestamps of sensitive disclosures** | Prevents temporal correlation attacks. Only session-level date is stored. |
| **Failed memory extractions** | If extraction fails, don't store a partial or low-confidence card. Absence is better than hallucination. |

### Rationale for Exclusions
- **Privacy by design**: It's easier to not collect data than to secure it later
- **Legal safety**: Minimizing stored data reduces GDPR/CCPA compliance burden
- **Quality**: Less noise = better retrieval. Raw transcripts would drown meaningful signals in fluff
- **Ethics**: An emotional support companion should remember what's important, not everything

---

## Summary

The architecture prioritizes:
1. **Structured richness** over raw text — for precise retrieval
2. **Pre-computation** over real-time heavy lifting — for low-latency greetings
3. **User control** over system opacity — for trust
4. **Minimalism** over completeness — for privacy and safety
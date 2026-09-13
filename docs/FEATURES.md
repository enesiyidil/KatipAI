# KatipAI — Feature list

> Ideas live here. Mark completed items with `[x]`.

**Last updated:** 2026-07-07

---

## How to use this file

- Add a new idea under the matching section.
- Flip `- [ ]` to `- [x]` as work lands.
- Split large features into sub-items; check the parent when every child is done.

---

## Notes and vault

### Custom note keys (labels)

**Status:** Planned

Today there is a single **general notes** flow: the speaker uses voice commands
(`"bunu genel notlara ekle"`, `"genel not olarak …"`) and notes are appended to
`general/Notlar.md` (`core/vault/general_notes.py`, General Notes page).

**Goal:** Users define their own note categories — add a key/label, create a
matching note area, and route matching utterances into that file.

- [ ] Settings/model for user-defined note keys (name, trigger phrases, vault path or filename)
- [ ] Settings UI: add, edit, delete keys
- [ ] Pipeline: match keys in the transcript and write to the matching vault file (`note_pipeline` + vault writer)
- [ ] Web UI: a page per key, or tabs on a single page
- [ ] Backward compatibility for the default general-note flow

**Example**

| Key | Trigger (example) | Target |
|-----|-------------------|--------|
| `genel` | "genel not olarak …" | `general/Notlar.md` (current) |
| `fikirler` | "fikir olarak kaydet …" | `general/Fikirler.md` |
| `todo` | "yapılacaklar listesine ekle …" | `general/Yapilacaklar.md` |

---

## Speech identity

### Full speaker recognition / diarization

**Status:** Planned

There is a single-user **voice profile**: microphone chunks are matched against
the enrolled embedding (`VoiceProfileService`, `VoiceMatcher`). If there is no
match, or the chunk is system audio, the speaker is labeled roughly **Me** /
**Other** / **Unknown**. Multi-speaker separation and durable speaker IDs are
not implemented.

**Goal:** Reliably tell *who said what* in meetings and background sessions —
recognize several speakers and label them correctly in transcripts and vault output.

- [ ] Multi-speaker enrollment: name + audio sample per profile
- [ ] Real-time or post-chunk speaker matching (embedding / diarization)
- [ ] Auto-segment unknown speakers; assign names later
- [ ] Correct `speaker` labels in transcript, timeline, and vault rows
- [ ] Settings UI: manage speaker profiles and thresholds
- [ ] Compatible transition from the current single-profile `voice_filter_mode`

---

## Meeting mode

### Auto-detect meetings (Teams → meeting mode)

**Status:** Planned

**Meeting mode** is selected manually from the tray (`RecordingMode.MEETING`).
Per-app system capture and echo separation exist, but meeting start is not
detected automatically. Meeting notes are also not collected on a dedicated tab
separate from the daily transcript / AI-note stream.

**Goal:** When the user joins a Teams meeting, KatipAI notices, switches to
**meeting mode**, and configures capture:

- Microphone → the user's voice (**Me**)
- Teams system audio → the other side / other speakers (**Other**)
- Echo dedup, channel split, and related settings apply automatically
- Meeting transcripts, summaries, and notes appear on a **meetings** tab

- [ ] Detect meeting apps (priority: Microsoft Teams — `com.microsoft.teams2`)
- [ ] Automatic or confirmed switch: normal → meeting mode + start recording
- [ ] Auto-select / bind Teams system-audio capture
- [ ] Dual-channel recording: microphone + Teams system audio in sync
- [ ] Meeting-specific defaults (echo dedup, chunk lengths, voice filter)
- [ ] Auto-exit or confirmed return to normal mode when the meeting ends
- [ ] Tray prompt: "Meeting detected — start recording?" (`meeting_auto_detect`, `meeting_auto_start`)
- [ ] API: meeting status and accept/dismiss endpoints
- [ ] DB: `Meeting` session model (start/end, app, title, transcript/summary FKs)
- [ ] Web UI: **Meetings** tab — history and live meetings, per-meeting transcript + AI summary
- [ ] Vault: one file per meeting or a meeting block in the daily file (`meetings/2026-07-07 — Sprint Planning.md`)
- [ ] Later: Zoom, Meet, FaceTime, and others

### Meeting title (Teams integration)

**Status:** Research — include if the integration is cheap enough

Process detection alone probably will not yield a title. Priority:

| Method | Difficulty | Notes |
|--------|------------|-------|
| Read the Teams window title / UI text | Low–medium | No OAuth; brittle but a fast POC |
| Outlook / calendar match (nearby event) | Medium | Title from the invite |
| Microsoft Graph (Teams + Calendar) | High | OAuth, scopes, most reliable title |

- [ ] POC: can we read a meeting name from the window title while Teams is active?
- [ ] Fallback if not: `Teams meeting — {datetime}` or a user edit
- [ ] Graph API only if the POC fails and the value is high (separate phase)
- [ ] Use the title in the tray prompt, UI tab, and vault filename

### Non-meeting call detection (1:1 calls)

**Status:** Planned

Voice/video **calls** that are not scheduled meetings have the same recording
need. Treat them like meetings: detect, meeting mode, transcript, summary.

**Goal:** Detect 1:1 or small-group calls (no meeting room) and record them
with the same pipeline.

- [ ] Detect Teams call state (call UI / process — a different signal than a meeting room)
- [ ] On call start: meeting mode + dual-channel capture (same profile as meetings)
- [ ] On call end: close the session and produce a summary
- [ ] UI: show calls on the meetings tab or as a subtype (`Teams call — Ahmet`)
- [ ] Remote party name when possible (Teams UI / Graph / recent history)
- [ ] Later: Phone / FaceTime and other call sources

**Example flow**

```
Teams meeting or call opens
  → KatipAI detects (+ title if available: "Weekly sprint" / "Call — Ayşe")
  → Meeting mode + Teams system audio + microphone
  → Me / Other split is automatic
  → Transcript + summary → Meetings tab + vault
  → Session ends → normal mode
```

---

## Search and assistant

### RAG chatbot (in-app Q&A)

**Status:** Planned

Transcripts, AI notes, and general notes are read on separate pages; finding
something from last week is a manual search. There is no in-app assistant that
answers questions in natural language.

**Goal:** A **chatbot** inside KatipAI. AI notes, transcripts, general notes,
meeting summaries, and vault markdown are indexed with **RAG**. A question
retrieves the relevant pieces and the local LLM (Qwen) answers.

**Sources to index**

| Source | Example question |
|--------|------------------|
| Transcripts | "What did Ahmet say yesterday?" |
| AI notes / session summaries | "What were the decisions in the last meeting?" |
| General notes | "What is on my to-do list?" |
| Meeting notes | "What risks came up in sprint planning?" |
| Vault markdown | "Which topics came up last week?" |

- [ ] Embedding model + vector store (fully local — sqlite-vec / Chroma / similar)
- [ ] Indexing pipeline: chunk + embed as new transcripts, summaries, and notes arrive
- [ ] Chunk strategy: tag with date, speaker, session/meeting metadata
- [ ] RAG retrieval: semantic search plus optional date/source filters
- [ ] Chat API: `POST /api/chat` — question → retrieval → LLM answer + source refs
- [ ] Web UI: chat panel/page (history, source snippets, vault links)
- [ ] **Cite sources** (which transcript/note, which date) to reduce hallucination
- [ ] Backfill index on first setup for existing data
- [ ] Later: MCP / external tools, command-style actions ("add this to general notes")

**Example**

```
User: "What did we say about the project deadline this week?"
  → RAG: matching transcript + AI-summary chunks
  → LLM: short answer + sources (7 July session, sprint meeting)
```

---

## Other ideas

*(Add items here as they come up.)*

- [ ] …

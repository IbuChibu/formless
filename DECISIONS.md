# Architecture Decisions

## 2026-09-29 — PDF first, online forms later

Decision:
The hackathon MVP supports uploaded fillable PDFs.

Reason:
PDF workflow is substantially easier to make reliable before the deadline.

Online/browser forms are explicitly out of scope for the initial submission.

---

## 2026-09-29 — No agent framework initially

Decision:
Agent orchestration will be implemented directly in Python.

Reason:
LangChain/LangGraph are unnecessary for the initial workflow and add complexity.

---

## 2026-09-29 — Voice added after text workflow

Decision:
The assistant must work fully through typed text before speech input/output is implemented.

Reason:
Voice should be an interface around the agent, not coupled to agent logic.

---

## 2026-10-08 — Conversation-first interface with a manual fallback

Decision:
The final product will make voice and text conversation the primary interface.
The existing manual field controls will remain available in a collapsible
"Edit all fields" drawer rather than being removed.

Reason:
The manual controls are useful for accessibility, corrections, review,
unsupported fields, demonstrations, and development. Keeping them as a fallback
does not require the user to experience the product as a traditional form
builder.

---

## 2026-10-08 — The agent proposes field changes but does not apply them

Decision:
The Form Agent will return structured proposals containing stable PDF field IDs
and candidate values. AI-proposed factual values must remain separate from
confirmed values until the user explicitly confirms or edits them.

Reason:
This preserves the user as the source of factual information, prevents model
output from silently changing a legal or financial form, and keeps AI logic
separate from PDF manipulation.

---

## 2026-10-08 — All input modes share one field state

Decision:
Voice, typed conversation, direct edits on the displayed PDF, and the manual
drawer will all update the same canonical field state through stable field IDs.
The AI will not interact with manual UI elements or maintain a duplicate copy of
the form.

Reason:
A single state model prevents conflicting answers, allows every input mode to
reuse the existing PDF filling endpoint, and makes correction and review
consistent across the product.

---

## 2026-10-10 — Official guidance is local, allowlisted, and version-specific

Decision:
Official guidance used by the Form Agent will come from small reviewed local
resources selected only for an exact recognized form ID and version. Guidance
responses expose the source and keep the official excerpt separate from the
assistant's plain-language explanation.

Reason:
This gives users attributable help without runtime crawling or general RAG,
prevents silently applying instructions from the wrong form edition, and keeps
external text inside the same untrusted-data boundary as PDF and user content.

---

## 2026-10-10 — Live web guidance is policy-gated and separate from reviewed guidance

Decision:
The Form Agent may use Tavily for one bounded search only when the user asks an
informational question and reviewed local guidance is insufficient. Search
eligibility and query construction are deterministic backend responsibilities.
Live results remain visibly separate from reviewed official guidance.

Reason:
This provides current, attributable help for unrecognized forms without giving
the model autonomous tool access or maintaining a large domain allowlist. The
query excludes PDF bytes, field values, proposals, personal answers, and
conversation history, while returned snippets and URLs are treated as
untrusted data and cannot cross the existing proposal-confirmation boundary.

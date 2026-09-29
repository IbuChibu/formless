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
---
name: servicenow-docs
description: Use when the user asks how ServiceNow works, how to configure or troubleshoot a ServiceNow product or platform feature (ITSM, CSM, HR, CMDB, Flow Designer, scripting APIs, etc.), or what a ServiceNow field, role, table or property does. Answers come from the official ServiceNow docs through the servicenow-docs tools, with citations.
---

# ServiceNow docs

Answer ServiceNow questions from the official product documentation, not from memory.

1. Call `snow_docs_search` with the question in plain English, using ServiceNow's own
   terms: the docs are English-only, so translate a question asked in another language
   first (and still answer in the user's language). If the user's instance
   runs the Brazil release, pass `release: "brazil"`; otherwise leave the default
   (Australia). If the results look off-topic, rephrase and search again, or narrow with
   `product` (for example `it-service-management`).
2. Answer only from the returned passages. Cite every factual claim with the passage `id`
   in square brackets. When a result has a `url`, you may also link the docs page.
3. Before giving step-by-step instructions, field lists or scripts, call `snow_docs_read`
   with the passage `id` to get the full section.
4. If the docs don't cover the question, or only cover another release or product, say
   so plainly instead of guessing.
5. If sources disagree, point out the conflict and cite both.

If a tool says the docs are still being set up, tell the user it's a one-time download
and to try again in a minute or two; `snow_docs_status` shows progress.

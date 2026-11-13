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
6. For a question about what changes between Australia and Brazil (an upgrade, what's
   new), call `snow_docs_compare` with the topic, or with `page` for one page. Lead with
   the release notes it returns, then the changed sections, and say that small
   rewordings are not listed.
7. Before writing or reviewing ServiceNow script code, check each class and method with
   `snow_docs_api` (for example `GlideRecord.addEncodedQuery`, or `gs` for all of
   GlideSystem). If it answers `not_found`, do not use that method; say so, and offer
   the closest documented one. After writing or changing a script, pass the whole
   script to `snow_docs_check_script` and act on what it finds before showing the code.
8. Table and field names depend on the instance. If the ServiceNow SDK (`now-sdk`) or another
   tool for the user's own instance is available, offer to check them there, and ask before
   anything that queries the instance; otherwise say they are unverified.
9. For code written with the ServiceNow SDK or Fluent, read `snow_docs_sdk_explain`: it is
   the documentation of the SDK version installed on this computer. `snow_docs_sdk_status`
   shows whether the SDK is set up and for which instances. After changing a Fluent file,
   suggest `now-sdk build`, which type-checks it locally.
10. To show something to the user rather than read it yourself: `snow_docs_open` displays a
   page as a document, and `snow_docs_diagram` draws a process as a flow, or as swimlanes
   when several roles take part. Take every step from the docs you read and give its source
   id. In Claude Code no panel appears: show the returned `mermaid` text in a code block, or
   give the page's `url`.

To see what the docs have on a product rather than search them, call `snow_docs_browse`:
without arguments for the product areas, with `product` (and `folder`) for the folders and
pages by title.

If a tool says the docs are still being set up, tell the user it's a one-time download
and to try again in a minute or two; `snow_docs_status` shows progress.

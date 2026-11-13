---
name: servicenow-setup-checklist
description: Use when the user asks how to set up, configure, activate, install or implement a ServiceNow product, application or feature and wants the steps, prerequisites, roles or plugins, or asks for a setup or implementation checklist. Builds an ordered, cited checklist from the official docs through the servicenow-docs tools.
---

# ServiceNow setup checklist

Write a setup checklist: the steps to set up one ServiceNow feature, in order, taken from
the docs. Use only the ServiceNow docs tools; do not fill gaps from memory.
1. Find the pages. Call snow_docs_search with the feature and words such as "set up",
   "configure" and "activate". If the feature is a product or an application, also call
   snow_docs_browse for its folder and pick the setup, configuration, installation and
   administration pages by title.
2. Read every page you take a step from with snow_docs_read (the section, or the whole page
   with the id cut off after "::"). Follow "Before you begin" and "What to do next" to the
   pages they name, and read those too.
3. Write the checklist in these parts, in this order, each item ending with its citation [id]:
   - Before you start: plugins or store applications to activate, licenses, the roles needed
     to do the setup, and other features it depends on.
   - Steps: numbered, in the order the docs give, one action per step, with the navigation
     path and the role where the docs state them.
   - Check that it works: how the docs say to verify the result. If they do not say, write
     that.
   - Next: optional configuration the docs point to.
4. Where the docs for the user's release (Australia unless they say Brazil) lack a step, say
   so instead of filling it in. If two pages disagree, show both.
5. If a tool for the user's own ServiceNow instance is connected, ask before using it. With a
   yes, look up which plugins are active and which roles the user has, and mark the items
   that are already done.
Answer in the user's language; keep navigation paths, field names and role names as the docs
write them.

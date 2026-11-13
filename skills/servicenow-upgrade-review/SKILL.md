---
name: servicenow-upgrade-review
description: Use when the user asks what to check, what changes or what is new for a ServiceNow product when upgrading from the Australia release to Brazil, or asks for an upgrade checklist or upgrade impact review. Builds a cited checklist from ServiceNow's release notes through the servicenow-docs tools.
---

# ServiceNow upgrade review

Write an upgrade review: what to check for one ServiceNow product when upgrading from
Australia to Brazil. Use only the ServiceNow docs tools; do not fill gaps from memory.
1. Call snow_docs_compare with the product name as `query`. `release_notes` has one passage
   per page; each page is "Combined <application> release notes for upgrades from Australia to
   Brazil". Release notes are per application, so a product often has several pages (the
   application, its workspace, its AI skills): use every page that belongs to what the user
   asked about, and name the pages you used. `more_release_notes` lists further pages whose
   application name shares a word with the query (the docs may call the product something
   else): use those that belong, too. If none fits, try the product's other names once
   (abbreviation, old name). If there is still none, say that the release notes have no page for
   this product, and stop.
2. For each page, call snow_docs_read with the passage's id cut off after "::" (this returns
   the whole page). If the result is truncated, read it again with max_chars 100000. If you
   still do not have every part of the page in front of you, read it part by part: the id
   of a part is the page id followed by the page title, " > " and the part's heading (for
   example "… > New features"). Do not write the checklist from a page you read only partly.
3. Write the checklist in these parts, in this order, one line per item, each ending with its
   citation [id]:
   - Before and after the upgrade (the page's "Important information for upgrading")
   - New features to evaluate ("New features")
   - Changed behavior ("Changes")
   - Removed and deprecated ("Removed", "Deprecations")
   - Activation and requirements ("Activation information", "Additional requirements")
   Take items only from the Brazil rows of the page. Where the page says
   "No updates for this release", write that for the part instead of leaving it out.
4. Add a part "Changed in the documentation" with the `changed_pages` from step 1, if there are
   any, and say that small rewordings are not listed.
5. If a tool for the user's own ServiceNow instance is connected, ask before using it. With a
   yes, look up the instance's release and installed applications, and mark the items that
   apply to this instance.
6. End with what the review does not cover: customizations, integrations and other products.
Answer in the user's language; keep product, feature and field names as the docs write them.

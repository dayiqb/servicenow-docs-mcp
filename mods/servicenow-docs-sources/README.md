# ServiceNow docs sources

A pane for Claude Code that lists the ServiceNow documentation passages Claude found and read
in the current session, newest first: the page title, the section, the release, whether Claude
read the section in full, and a link that opens the page on servicenow.com.

It works together with the `servicenow-docs` plugin: it watches the results of that plugin's
`snow_docs_search`, `snow_docs_read` and `snow_docs_compare` tools and nothing else. The pane
opens by itself the first time Claude searches the docs in a session; `/docs-sources` opens it
again after you close it. It keeps the last 60 passages of the session and stores nothing
between sessions.

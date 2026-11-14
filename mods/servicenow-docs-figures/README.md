# ServiceNow docs figures

A pane for Claude Code, beside the chat, where Claude draws a figure when a picture explains a
ServiceNow concept better than text: a lifecycle and its states, how records relate, what
happens over time. The answer in the chat stays short; the figure adds to it.

It gives Claude one tool, `show_figure`. Claude draws the figure as SVG from documentation it
has read with the `servicenow-docs` plugin and names those pages as sources. The pane adds the
styling, for light and dark, and shows the figure with its title, one line of caption and
links to the pages. Claude draws a figure twice, wide and narrow, and the pane shows the one
that fits its width, so the text keeps its size when the pane is made narrow. Earlier figures
of the session can be paged back to. Nothing is drawn for
a search or a read, and nothing is kept between sessions.

`/docs-figures` opens the pane again after you close it. A terminal, which draws no vector
figures, shows what the figure says in words.

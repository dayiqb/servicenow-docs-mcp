/**
 * The plugin's hooks module: the panes beside the chat in Claude Code.
 *
 * - The figures pane (`/docs-figures`): Claude draws a figure that explains a ServiceNow concept.
 * - The ServiceNow SDK panel (`/sdk-panel`): only when its setting is on. It can run `now-sdk`
 *   commands after a confirmation; everything else in the plugin only reads.
 *
 * A plugin has one hooks module, and one hook for an event and matcher: a second one keeps the
 * whole module from loading. So what each pane sets up at the start of a session is called from
 * the one `session.start` hook here, and each pane registers the rest under its own names.
 */

import type { Register } from 'claude-code'

import { register as registerFigures, start as startFigures } from '../panes/figures/pane.tsx'
import { register as registerSdkPanel, start as startSdkPanel } from '../panes/sdk-panel/pane.tsx'

export const register: Register = (on, options) => {
  const hasSdkPanel = options.sdk_panel === true

  on('session.start', async ($, e, next) => {
    await startFigures($)
    if (hasSdkPanel) await startSdkPanel($)

    return next(e)
  })

  registerFigures(on, options)
  if (hasSdkPanel) registerSdkPanel(on, options)
}

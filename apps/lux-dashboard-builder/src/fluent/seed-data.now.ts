import '@servicenow/sdk/global'
import { Record } from '@servicenow/sdk/core'

// Starting allow list. Loaded on first install only, so admin changes stay.
Record({
    $id: Now.ID['allowed-incident'],
    $meta: { installMethod: 'first install' },
    table: 'x_steas_dash_allowed_table',
    data: { source_table: 'incident', secure_count: true, active: true },
})

Record({
    $id: Now.ID['allowed-task'],
    $meta: { installMethod: 'first install' },
    table: 'x_steas_dash_allowed_table',
    data: { source_table: 'task', secure_count: true, active: true },
})

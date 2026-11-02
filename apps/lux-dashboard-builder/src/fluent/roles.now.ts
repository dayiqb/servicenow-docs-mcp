import '@servicenow/sdk/global'
import { Role } from '@servicenow/sdk/core'

// Can open shared dashboards.
export const viewerRole = Role({
    name: 'x_steas_dash.viewer',
    description: 'Can view dashboards that are shared with everyone.',
})

// Can create and edit own dashboards.
export const builderRole = Role({
    name: 'x_steas_dash.builder',
    description: 'Can create dashboards and charts, and edit their own dashboards.',
    containsRoles: [viewerRole],
})

// Can manage the table allow list and all dashboards.
export const adminRole = Role({
    name: 'x_steas_dash.admin',
    description: 'Can manage the table allow list and edit all dashboards.',
    containsRoles: [builderRole],
})

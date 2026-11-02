import '@servicenow/sdk/global'
import { Acl } from '@servicenow/sdk/core'
import { viewerRole, builderRole, adminRole } from './roles.now'

// Record-level ACLs. The widget server scripts check the same rules in code.

const canSeeDashboard = `answer = gs.hasRole('x_dash.admin') || current.owner == gs.getUserID() || current.shared == true;`
const canChangeDashboard = `answer = gs.hasRole('x_dash.admin') || current.owner == gs.getUserID();`
const canSeeChart = `answer = gs.hasRole('x_dash.admin') || current.dashboard.owner == gs.getUserID() || current.dashboard.shared == true;`
const canChangeChart = `answer = gs.hasRole('x_dash.admin') || current.dashboard.owner == gs.getUserID();`

Acl({
    $id: Now.ID['acl-dashboard-read'],
    type: 'record',
    table: 'x_dash_dashboard',
    operation: 'read',
    decisionType: 'allow',
    roles: [viewerRole],
    script: canSeeDashboard,
    description: 'Viewers read shared dashboards and their own.',
})

Acl({
    $id: Now.ID['acl-dashboard-create'],
    type: 'record',
    table: 'x_dash_dashboard',
    operation: 'create',
    decisionType: 'allow',
    roles: [builderRole],
    description: 'Builders create dashboards.',
})

Acl({
    $id: Now.ID['acl-dashboard-write'],
    type: 'record',
    table: 'x_dash_dashboard',
    operation: 'write',
    decisionType: 'allow',
    roles: [builderRole],
    script: canChangeDashboard,
    description: 'Builders change their own dashboards. Dashboard admins change all.',
})

Acl({
    $id: Now.ID['acl-dashboard-delete'],
    type: 'record',
    table: 'x_dash_dashboard',
    operation: 'delete',
    decisionType: 'allow',
    roles: [builderRole],
    script: canChangeDashboard,
    description: 'Builders delete their own dashboards. Dashboard admins delete all.',
})

Acl({
    $id: Now.ID['acl-chart-read'],
    type: 'record',
    table: 'x_dash_chart',
    operation: 'read',
    decisionType: 'allow',
    roles: [viewerRole],
    script: canSeeChart,
    description: 'Viewers read charts on dashboards they can see.',
})

Acl({
    $id: Now.ID['acl-chart-create'],
    type: 'record',
    table: 'x_dash_chart',
    operation: 'create',
    decisionType: 'allow',
    roles: [builderRole],
    script: canChangeChart,
    description: 'Builders add charts to their own dashboards.',
})

Acl({
    $id: Now.ID['acl-chart-write'],
    type: 'record',
    table: 'x_dash_chart',
    operation: 'write',
    decisionType: 'allow',
    roles: [builderRole],
    script: canChangeChart,
    description: 'Builders change charts on their own dashboards.',
})

Acl({
    $id: Now.ID['acl-chart-delete'],
    type: 'record',
    table: 'x_dash_chart',
    operation: 'delete',
    decisionType: 'allow',
    roles: [builderRole],
    script: canChangeChart,
    description: 'Builders remove charts from their own dashboards.',
})

Acl({
    $id: Now.ID['acl-allowed-read'],
    type: 'record',
    table: 'x_dash_allowed_table',
    operation: 'read',
    decisionType: 'allow',
    roles: [viewerRole],
    description: 'Viewers read the table allow list.',
})

Acl({
    $id: Now.ID['acl-allowed-create'],
    type: 'record',
    table: 'x_dash_allowed_table',
    operation: 'create',
    decisionType: 'allow',
    roles: [adminRole],
    description: 'Dashboard admins add allowed tables.',
})

Acl({
    $id: Now.ID['acl-allowed-write'],
    type: 'record',
    table: 'x_dash_allowed_table',
    operation: 'write',
    decisionType: 'allow',
    roles: [adminRole],
    description: 'Dashboard admins change allowed tables.',
})

Acl({
    $id: Now.ID['acl-allowed-delete'],
    type: 'record',
    table: 'x_dash_allowed_table',
    operation: 'delete',
    decisionType: 'allow',
    roles: [adminRole],
    description: 'Dashboard admins remove allowed tables.',
})

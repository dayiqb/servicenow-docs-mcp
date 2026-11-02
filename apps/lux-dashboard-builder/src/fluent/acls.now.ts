import '@servicenow/sdk/global'
import { Acl } from '@servicenow/sdk/core'
import { viewerRole, adminRole } from './roles.now'

// Record-level ACLs for the table allow list.

Acl({
    $id: Now.ID['acl-allowed-read'],
    type: 'record',
    table: 'x_steas_dash_allowed_table',
    operation: 'read',
    decisionType: 'allow',
    roles: [viewerRole],
    description: 'Viewers read the table allow list.',
})

Acl({
    $id: Now.ID['acl-allowed-create'],
    type: 'record',
    table: 'x_steas_dash_allowed_table',
    operation: 'create',
    decisionType: 'allow',
    roles: [adminRole],
    description: 'Dashboard admins add allowed tables.',
})

Acl({
    $id: Now.ID['acl-allowed-write'],
    type: 'record',
    table: 'x_steas_dash_allowed_table',
    operation: 'write',
    decisionType: 'allow',
    roles: [adminRole],
    description: 'Dashboard admins change allowed tables.',
})

Acl({
    $id: Now.ID['acl-allowed-delete'],
    type: 'record',
    table: 'x_steas_dash_allowed_table',
    operation: 'delete',
    decisionType: 'allow',
    roles: [adminRole],
    description: 'Dashboard admins remove allowed tables.',
})

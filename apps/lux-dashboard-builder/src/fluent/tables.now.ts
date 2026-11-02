import '@servicenow/sdk/global'
import { Table, StringColumn, BooleanColumn } from '@servicenow/sdk/core'
import { viewerRole, adminRole } from './roles.now'

// Tables that builders may use. Admins manage this list.
export const x_steas_dash_allowed_table = Table({
    name: 'x_steas_dash_allowed_table',
    label: 'Dashboard allowed table',
    display: 'source_table',
    audit: true,
    readRoles: [viewerRole],
    createRoles: [adminRole],
    writeRoles: [adminRole],
    deleteRoles: [adminRole],
    schema: {
        source_table: StringColumn({ label: 'Table', maxLength: 80, mandatory: true }),
        secure_count: BooleanColumn({
            label: 'Count with full record security',
            default: true,
        }),
        active: BooleanColumn({ label: 'Active', default: true }),
    },
    index: [{ name: 'x_steas_dash_allowed_table_unique', unique: true, element: 'source_table' }],
})

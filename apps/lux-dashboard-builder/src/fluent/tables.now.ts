import '@servicenow/sdk/global'
import {
    Table,
    StringColumn,
    BooleanColumn,
    ChoiceColumn,
    IntegerColumn,
    ReferenceColumn,
    MultiLineTextColumn,
} from '@servicenow/sdk/core'
import { viewerRole, builderRole, adminRole } from './roles.now'

// One row per dashboard. Ownership checks run in the widget server scripts.
export const x_dash_dashboard = Table({
    name: 'x_dash_dashboard',
    label: 'Dashboard',
    display: 'name',
    audit: true,
    readRoles: [viewerRole],
    createRoles: [builderRole],
    writeRoles: [builderRole],
    deleteRoles: [builderRole],
    schema: {
        name: StringColumn({ label: 'Name', maxLength: 100, mandatory: true }),
        description: StringColumn({ label: 'Description', maxLength: 1000 }),
        owner: ReferenceColumn({ label: 'Owner', referenceTable: 'sys_user' }),
        shared: BooleanColumn({ label: 'Shared with all viewers', default: false }),
        active: BooleanColumn({ label: 'Active', default: true }),
    },
})

// One row per chart on a dashboard.
export const x_dash_chart = Table({
    name: 'x_dash_chart',
    label: 'Dashboard chart',
    display: 'title',
    audit: true,
    readRoles: [viewerRole],
    createRoles: [builderRole],
    writeRoles: [builderRole],
    deleteRoles: [builderRole],
    schema: {
        dashboard: ReferenceColumn({
            label: 'Dashboard',
            referenceTable: 'x_dash_dashboard',
            mandatory: true,
            cascadeRule: 'delete',
        }),
        title: StringColumn({ label: 'Title', maxLength: 100 }),
        source_table: StringColumn({ label: 'Table', maxLength: 80, mandatory: true }),
        query: MultiLineTextColumn({ label: 'Filter (encoded query)', maxLength: 4000 }),
        group_by: StringColumn({ label: 'Group by', maxLength: 160 }),
        group_by_2: StringColumn({ label: 'Second group by', maxLength: 160 }),
        aggregate: ChoiceColumn({
            label: 'Aggregate',
            default: 'COUNT',
            choices: {
                COUNT: { label: 'Count', sequence: 0 },
                SUM: { label: 'Sum', sequence: 1 },
                AVG: { label: 'Average', sequence: 2 },
                MIN: { label: 'Minimum', sequence: 3 },
                MAX: { label: 'Maximum', sequence: 4 },
            },
        }),
        aggregate_field: StringColumn({ label: 'Aggregate field', maxLength: 160 }),
        chart_type: ChoiceColumn({
            label: 'Chart type',
            default: 'column',
            choices: {
                score: { label: 'Single score', sequence: 0 },
                column: { label: 'Vertical bar', sequence: 1 },
                bar: { label: 'Horizontal bar', sequence: 2 },
                stacked: { label: 'Stacked bar', sequence: 3 },
                line: { label: 'Line', sequence: 4 },
                area: { label: 'Area', sequence: 5 },
                pie: { label: 'Pie', sequence: 6 },
                donut: { label: 'Donut', sequence: 7 },
                heatmap: { label: 'Heat map', sequence: 8 },
                list: { label: 'List', sequence: 9 },
            },
        }),
        trend: ChoiceColumn({
            label: 'Date trend',
            default: 'none',
            choices: {
                none: { label: 'None', sequence: 0 },
                Day: { label: 'Day', sequence: 1 },
                Week: { label: 'Week', sequence: 2 },
                Month: { label: 'Month', sequence: 3 },
                Quarter: { label: 'Quarter', sequence: 4 },
                Year: { label: 'Year', sequence: 5 },
            },
        }),
        list_fields: StringColumn({ label: 'List fields', maxLength: 1000 }),
        max_groups: IntegerColumn({ label: 'Max groups', default: 10 }),
        width: IntegerColumn({ label: 'Width (1 to 4 columns)', default: 2 }),
        order: IntegerColumn({ label: 'Order', default: 100 }),
    },
})

// Tables that builders may use. Admins manage this list.
export const x_dash_allowed_table = Table({
    name: 'x_dash_allowed_table',
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
    index: [{ name: 'x_dash_allowed_table_unique', unique: true, element: 'source_table' }],
})

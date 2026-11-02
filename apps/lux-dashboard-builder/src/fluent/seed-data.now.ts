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

// A sample dashboard that every viewer can see. No owner, so only admins edit it.
export const sampleDashboard = Record({
    $id: Now.ID['sample-dashboard'],
    $meta: { installMethod: 'first install' },
    table: 'x_steas_dash_dashboard',
    data: {
        name: 'Incident overview',
        description: 'Sample dashboard. Shows open incidents.',
        shared: true,
        active: true,
    },
})

Record({
    $id: Now.ID['sample-chart-open'],
    $meta: { installMethod: 'first install' },
    table: 'x_steas_dash_chart',
    data: {
        dashboard: sampleDashboard,
        title: 'Open incidents',
        source_table: 'incident',
        query: 'active=true',
        group_by: '',
        group_by_2: '',
        aggregate: 'COUNT',
        chart_type: 'score',
        trend: 'none',
        max_groups: 10,
        grid_x: 0,
        grid_y: 0,
        grid_w: 3,
        grid_h: 3,
    },
})

Record({
    $id: Now.ID['sample-chart-priority'],
    $meta: { installMethod: 'first install' },
    table: 'x_steas_dash_chart',
    data: {
        dashboard: sampleDashboard,
        title: 'Open incidents by priority',
        source_table: 'incident',
        query: 'active=true',
        group_by: 'priority',
        group_by_2: '',
        aggregate: 'COUNT',
        chart_type: 'column',
        trend: 'none',
        max_groups: 10,
        grid_x: 3,
        grid_y: 0,
        grid_w: 9,
        grid_h: 3,
    },
})

Record({
    $id: Now.ID['sample-chart-state'],
    $meta: { installMethod: 'first install' },
    table: 'x_steas_dash_chart',
    data: {
        dashboard: sampleDashboard,
        title: 'Open incidents by state',
        source_table: 'incident',
        query: 'active=true',
        group_by: 'state',
        group_by_2: '',
        aggregate: 'COUNT',
        chart_type: 'donut',
        trend: 'none',
        max_groups: 10,
        grid_x: 0,
        grid_y: 3,
        grid_w: 4,
        grid_h: 4,
    },
})

Record({
    $id: Now.ID['sample-chart-category'],
    $meta: { installMethod: 'first install' },
    table: 'x_steas_dash_chart',
    data: {
        dashboard: sampleDashboard,
        title: 'Open incidents by category',
        source_table: 'incident',
        query: 'active=true',
        group_by: 'category',
        group_by_2: '',
        aggregate: 'COUNT',
        chart_type: 'bar',
        trend: 'none',
        max_groups: 10,
        grid_x: 4,
        grid_y: 3,
        grid_w: 8,
        grid_h: 4,
    },
})

Record({
    $id: Now.ID['sample-chart-heat'],
    $meta: { installMethod: 'first install' },
    table: 'x_steas_dash_chart',
    data: {
        dashboard: sampleDashboard,
        title: 'Priority by state',
        source_table: 'incident',
        query: 'active=true',
        group_by: 'state',
        group_by_2: 'priority',
        aggregate: 'COUNT',
        chart_type: 'heatmap',
        trend: 'none',
        max_groups: 10,
        grid_x: 0,
        grid_y: 7,
        grid_w: 12,
        grid_h: 4,
    },
})


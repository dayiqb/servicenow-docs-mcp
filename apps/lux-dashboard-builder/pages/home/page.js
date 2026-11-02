import {customElement} from 'lit/decorators.js';
import {AIUXDashboard, decorators} from '@servicenow/aiux/aiux-components-core';
import '@servicenow/glide-widgets/x_steas_dash/x-dash-chart-widget';

const {title, subtitle, roles} = decorators;

/**
 * The home page is a native Lux canvas (dashboard page).
 * The build turns `items` into sys_aix_dashboard_item records.
 * Admins change the canvas in the canvas editor. Users can personalize it.
 * Grid: 12 columns, each row is 80 px high.
 */
@customElement('x-dash-home-page')
@title('Incident overview')
@subtitle('Sample charts. Edit the canvas to add, move, or change charts.')
@roles(['x_steas_dash.viewer'])
export default class HomePage extends AIUXDashboard {
  static gridOptions = {};

  static items = [
    {
      widget: 'x-dash-chart-widget',
      title: 'Open incidents',
      category: 'unlocked',
      gridProps: {x: 0, y: 0, w: 3, h: 3},
      widgetProperties: {
        chartTitle: 'Open incidents',
        sourceTable: 'incident',
        filter: 'active=true',
        chartType: 'score'
      }
    },
    {
      widget: 'x-dash-chart-widget',
      title: 'Open incidents by priority',
      category: 'unlocked',
      gridProps: {x: 3, y: 0, w: 9, h: 3},
      widgetProperties: {
        chartTitle: 'Open incidents by priority',
        sourceTable: 'incident',
        filter: 'active=true',
        chartType: 'column',
        groupBy: 'priority'
      }
    },
    {
      widget: 'x-dash-chart-widget',
      title: 'Open incidents by state',
      category: 'unlocked',
      gridProps: {x: 0, y: 3, w: 4, h: 4},
      widgetProperties: {
        chartTitle: 'Open incidents by state',
        sourceTable: 'incident',
        filter: 'active=true',
        chartType: 'donut',
        groupBy: 'state'
      }
    },
    {
      widget: 'x-dash-chart-widget',
      title: 'Open incidents by category',
      category: 'unlocked',
      gridProps: {x: 4, y: 3, w: 8, h: 4},
      widgetProperties: {
        chartTitle: 'Open incidents by category',
        sourceTable: 'incident',
        filter: 'active=true',
        chartType: 'bar',
        groupBy: 'category'
      }
    },
    {
      widget: 'x-dash-chart-widget',
      title: 'Priority by state',
      category: 'unlocked',
      gridProps: {x: 0, y: 7, w: 12, h: 4},
      widgetProperties: {
        chartTitle: 'Priority by state',
        sourceTable: 'incident',
        filter: 'active=true',
        chartType: 'heatmap',
        groupBy: 'state',
        secondGroupBy: 'priority'
      }
    },
    {
      widget: 'x-dash-chart-widget',
      title: 'Chart',
      description: 'A chart of records from one table. Set it in the side panel.',
      category: 'library',
      widgetProperties: {
        chartTitle: 'New chart',
        sourceTable: 'incident',
        filter: 'active=true',
        chartType: 'column',
        groupBy: 'priority'
      }
    }
  ];
}

import {html, css} from 'lit';
import {customElement} from 'lit/decorators.js';
import {AIUXElement, decorators} from '@servicenow/aiux/aiux-components-core';
import {i18n} from '@servicenow/aiux/aiux-services';
import {setDocumentTitle} from '../../../utils/document-title.js';
import '../../../widgets/x-dash-board/index.js';

const {acl} = decorators;

@customElement('x-dash-dashboard-page')
@acl([{decision: 'allow_if', roles: ['x_steas_dash.viewer']}])
export default class DashboardPage extends AIUXElement {
  static styles = css`
    :host {
      display: block;
      min-height: 100%;
    }
  `;

  static async loader(ctx) {
    return {id: ctx.params?.id || ''};
  }

  firstUpdated() {
    setDocumentTitle(i18n.getMessage('Dashboard'));
  }

  render() {
    const {id} = this.loaderData || {};
    return html`<x-dash-board dashboard-id=${id || ''}></x-dash-board>`;
  }
}

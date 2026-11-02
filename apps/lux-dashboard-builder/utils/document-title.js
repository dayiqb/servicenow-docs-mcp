import {isServer} from 'lit';

/** Sets the browser tab title (WCAG 2.4.2). */
export function setDocumentTitle(title) {
  if (isServer) return;
  document.title = title;
}

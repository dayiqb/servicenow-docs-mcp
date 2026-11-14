// Runs the panel's own rendering code outside a browser, for tests/test_panel.py.
//
//   node tests/panel_harness.mjs <panel.html>   (cases as JSON on stdin, results as JSON on stdout)
//
// The page is one script that builds everything with createElement and never parses markup, so
// a small stand-in for the DOM is enough to see what it would put on the screen. Cases:
//   { op: "markdown", text }          -> the rendered blocks as an HTML-like string
//   { op: "inline", text }            -> one run of inline text, the same way
//   { op: "plain", text }             -> docs text as plain words
//   { op: "show", result, args, open } -> the whole panel after a tool result, as a string;
//                                        `open` lists the fold buttons to click first, by position
//   { op: "words" }                   -> the keys of the strings, per language
import { readFileSync } from "node:fs";

class Text {
  constructor(text) { this.nodeType = 3; this.data = String(text); this.parentNode = null; }
  get textContent() { return this.data; }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
}

class Element {
  constructor(tag, fragment) {
    this.nodeType = fragment ? 11 : 1;
    this.tagName = fragment ? "" : String(tag).toUpperCase();
    this.localName = String(tag);
    this.attrs = new Map();
    this.childNodes = [];
    this.parentNode = null;
    this.listeners = {};
    this.style = { setProperty() {} };
    this.dataset = {};
    this.hidden = false;
    const self = this;
    this.classList = {
      contains: (name) => self.className.split(/\s+/).includes(name),
      add: (name) => { if (!self.classList.contains(name)) self.className = (self.className + " " + name).trim(); },
      remove: (name) => { self.className = self.className.split(/\s+/).filter((c) => c !== name).join(" "); },
      toggle: (name, on) => { (on ?? !self.classList.contains(name)) ? self.classList.add(name) : self.classList.remove(name); },
    };
  }
  get className() { return this.attrs.get("class") || ""; }
  set className(value) { this.attrs.set("class", String(value)); }
  get id() { return this.attrs.get("id") || ""; }
  set id(value) { this.attrs.set("id", String(value)); }
  set tabIndex(value) { this.attrs.set("tabindex", String(value)); }
  get children() { return this.childNodes.filter((c) => c.nodeType === 1); }
  get firstElementChild() { return this.children[0] || null; }
  get lastElementChild() { return this.children[this.children.length - 1] || null; }
  get firstChild() { return this.childNodes[0] || null; }
  get lastChild() { return this.childNodes[this.childNodes.length - 1] || null; }
  get previousElementSibling() { const all = this.parentNode ? this.parentNode.children : []; return all[all.indexOf(this) - 1] || null; }
  get textContent() { return this.childNodes.map((c) => c.textContent).join(""); }
  set textContent(value) { this.replaceChildren(); if (value != null && value !== "") this.append(String(value)); }
  setAttribute(name, value) { this.attrs.set(name, String(value)); }
  getAttribute(name) { return this.attrs.has(name) ? this.attrs.get(name) : null; }
  hasAttribute(name) { return this.attrs.has(name); }
  removeAttribute(name) { this.attrs.delete(name); }
  addEventListener(type, handler) { (this.listeners[type] = this.listeners[type] || []).push(handler); }
  click() { for (const handler of this.listeners.click || []) handler({ currentTarget: this, target: this, preventDefault() {} }); }
  removeChild(node) { const at = this.childNodes.indexOf(node); if (at >= 0) { this.childNodes.splice(at, 1); node.parentNode = null; } }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  #take(items) {
    const out = [];
    for (const item of items) {
      if (item == null) { out.push(new Text(String(item))); continue; } // as a browser does: append(null) writes "null"
      if (typeof item === "string" || typeof item === "number") out.push(new Text(item));
      else if (item.nodeType === 11) { out.push(...item.childNodes); item.childNodes = []; }
      else { item.remove(); out.push(item); }
    }
    for (const node of out) node.parentNode = this;
    return out;
  }
  append(...items) { this.childNodes.push(...this.#take(items)); }
  prepend(...items) { this.childNodes.unshift(...this.#take(items)); }
  replaceChildren(...items) { for (const c of this.childNodes) c.parentNode = null; this.childNodes = []; this.append(...items); }
  after(...items) { const p = this.parentNode; const at = p.childNodes.indexOf(this); const taken = p.#take(items); p.childNodes.splice(at + 1, 0, ...taken); }
  before(...items) { const p = this.parentNode; const taken = p.#take(items); p.childNodes.splice(p.childNodes.indexOf(this), 0, ...taken); }
  *walk() { for (const c of this.children) { yield c; yield* c.walk(); } }
  matches(selector) {
    return selector.split(",").some((one) => {
      const m = one.trim().match(/^([a-z0-9]*)((?:\.[\w-]+)*)$/i);
      if (!m) return false;
      return (!m[1] || this.localName === m[1].toLowerCase()) && m[2].split(".").filter(Boolean).every((c) => this.classList.contains(c));
    });
  }
  querySelectorAll(selector) {
    const scoped = selector.replace(/^:scope\s*>\s*/, "");
    const pool = scoped === selector ? [...this.walk()] : this.children;
    return pool.filter((node) => node.matches(scoped));
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) { for (let n = this; n && n.nodeType === 1; n = n.parentNode) if (n.matches(selector)) return n; return null; }
  getBoundingClientRect() { return { top: 0, left: 0, width: 0, height: 0 }; }
  get clientWidth() { return 0; }
  get scrollWidth() { return 0; }
  scrollIntoView() {}
  focus() {}
}

const byId = { app: new Element("main"), live: new Element("div") };
const documentElement = new Element("html");
const body = new Element("body");
globalThis.document = {
  createElement: (tag) => new Element(tag),
  createElementNS: (_, tag) => new Element(tag),
  createDocumentFragment: () => new Element("#fragment", true),
  createTextNode: (text) => new Text(text),
  getElementById: (id) => byId[id] || null,
  documentElement, body, head: new Element("head"),
};
globalThis.window = { addEventListener() {}, postMessage() {}, innerWidth: 720 };
globalThis.window.parent = globalThis.window;
globalThis.requestAnimationFrame = () => 0;
globalThis.cancelAnimationFrame = () => {};
globalThis.getComputedStyle = () => ({ fontFamily: "sans-serif" });
globalThis.ResizeObserver = class { observe() {} disconnect() {} };

const page = readFileSync(process.argv[2], "utf8");
const script = page.match(/<script>([\s\S]*)<\/script>/)[1];
const tail = /\bstart\(\);\s*\}\)\(\);\s*$/;
if (!tail.test(script)) throw new Error("the panel's script no longer ends with start(); })();");
(0, eval)(script.replace(tail, "globalThis.panel = { markdown, inline, plainText, documentBody, show, state, WORDS }; })();"));
const { markdown, inline, plainText, documentBody, show, state, WORDS } = globalThis.panel;

const KEPT = ["class", "start", "href", "colspan", "rowspan", "scope", "role", "aria-label", "aria-expanded", "aria-controls", "tabindex", "id"];
const escape = (text) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
function html(node) {
  if (node.nodeType === 3) return escape(node.data);
  const inner = node.childNodes.map(html).join("");
  if (node.nodeType === 11) return inner;
  const attrs = KEPT.filter((k) => node.attrs.has(k)).map((k) => ` ${k}="${escape(node.attrs.get(k))}"`).join("")
    + (node.hidden ? ' hidden=""' : "");
  return `<${node.localName}${attrs}>${inner}</${node.localName}>`;
}
function tree(node) {
  if (node.nodeType === 3) return { text: node.data };
  return { tag: node.localName, attrs: Object.fromEntries(node.attrs), text: node.textContent, kids: node.childNodes.map(tree) };
}
function holder(fragment) { const div = new Element("div"); div.append(fragment); return div; }

const run = {
  markdown: (c) => holder(markdown(c.text, c.anchors ? [] : undefined)).childNodes.map(html).join(""),
  inline: (c) => html(inline(c.text, new Element("p"))),
  document: (c) => { const d = documentBody(c.text, c.title); return { html: html(d.body), anchors: d.anchors.map((a) => a.text) }; },
  plain: (c) => plainText(c.text),
  show: (c) => {
    state.args = c.args || {}; show(c.result);
    for (const at of c.open || []) byId.app.querySelectorAll("button.fold")[at].click();
    return html(byId.app);
  },
  words: () => Object.fromEntries(Object.entries(WORDS).map(([language, words]) => [language, Object.keys(words)])),
};
const cases = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(cases.map((c) => { try { return run[c.op](c); } catch (e) { return { error: String(e && e.stack || e) }; } })));

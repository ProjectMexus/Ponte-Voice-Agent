// Small DOM test double for the dependency-free frontend. Rendering and event
// handlers remain the real production code; only browser APIs are replaced.
export function createDOM() {
  const documentListeners = new Map();
  const allNodes = [];
  let document;

  function matches(node, selector) {
    return selector.split(",").some((part) => {
      part = part.trim();
      if (!part) return false;
      const exclusions = [...part.matchAll(/:not\(([^)]+)\)/g)].map((match) => match[1]);
      part = part.replace(/:not\([^)]+\)/g, "");
      if (exclusions.some((excluded) => matches(node, excluded))) return false;
      const tag = part.match(/^[a-z][\w-]*/i)?.[0];
      if (tag && node.tagName !== tag.toUpperCase()) return false;
      const id = part.match(/#([\w-]+)/)?.[1];
      if (id && node.id !== id) return false;
      if ([...part.matchAll(/\.([\w-]+)/g)].some((match) => !node.classList.contains(match[1]))) return false;
      return [...part.matchAll(/\[([^\]=]+)(?:=["']?([^\]"']*)["']?)?\]/g)].every((match) => {
        const actual = node.getAttribute(match[1]);
        return actual !== null && (match[2] === undefined || actual === match[2]);
      });
    });
  }

  class Node {
    constructor(tag) {
      this.tagName = tag.toUpperCase();
      this.children = [];
      this.parentElement = null;
      this.attributes = new Map();
      this.dataset = {};
      this.listeners = new Map();
      this.hidden = false;
      this.disabled = false;
      this.value = "";
      this._text = "";
      this.classList = {
        contains: (name) => this.className.split(/\s+/).includes(name),
        add: (...names) => { this.className = [...new Set([...this.className.split(/\s+/).filter(Boolean), ...names])].join(" "); },
        remove: (...names) => { this.className = this.className.split(/\s+/).filter((name) => !names.includes(name)).join(" "); },
        toggle: (name, force) => {
          const present = force ?? !this.classList.contains(name);
          this.classList[present ? "add" : "remove"](name);
          return present;
        },
      };
      allNodes.push(this);
    }
    get className() { return this.attributes.get("class") || ""; }
    set className(value) { this.attributes.set("class", String(value)); }
    get id() { return this.attributes.get("id") || ""; }
    set id(value) { this.attributes.set("id", String(value)); }
    get textContent() { return this._text + this.children.map((node) => node.textContent).join(""); }
    set textContent(value) { this.replaceChildren(); this._text = String(value ?? ""); }
    get isConnected() { return this === document.documentElement || Boolean(this.parentElement?.isConnected); }
    get outerHTML() { return `<${this.tagName.toLowerCase()}>${this.textContent}</${this.tagName.toLowerCase()}>`; }
    get firstElementChild() { return this.children[0] || null; }
    get lastElementChild() { return this.children.at(-1) || null; }
    getAttribute(name) {
      if (name === "disabled" && this.disabled) return "";
      if (name === "hidden" && this.hidden) return "";
      return this.attributes.get(name) ?? null;
    }
    setAttribute(name, value) {
      this.attributes.set(name, String(value));
      if (name.startsWith("data-")) this.dataset[name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = String(value);
      if (name === "tabindex") this.tabIndex = Number(value);
    }
    removeAttribute(name) { this.attributes.delete(name); }
    append(...nodes) {
      nodes.forEach((node) => {
        if (typeof node === "string") { const textNode = new Node("span"); textNode.textContent = node; node = textNode; }
        node.remove(); node.parentElement = this; this.children.push(node);
      });
    }
    replaceChildren(...nodes) { this.children.forEach((node) => { node.parentElement = null; }); this.children = []; this._text = ""; this.append(...nodes); }
    remove() {
      if (this.parentElement) this.parentElement.children = this.parentElement.children.filter((node) => node !== this);
      this.parentElement = null;
    }
    matches(selector) { return matches(this, selector); }
    closest(selector) { return this.matches(selector) ? this : this.parentElement?.closest(selector) || null; }
    contains(node) { return this === node || this.children.some((child) => child.contains(node)); }
    querySelectorAll(selector) { return this.children.flatMap((child) => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]); }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    addEventListener(type, handler) { const handlers = this.listeners.get(type) || []; handlers.push(handler); this.listeners.set(type, handlers); }
    dispatchEvent(event) { event.target ??= this; event.currentTarget = this; (this.listeners.get(event.type) || []).forEach((handler) => handler(event)); return !event.defaultPrevented; }
    click() { if (!this.disabled) this.dispatchEvent(createEvent("click")); }
    focus() { document.activeElement = this; }
    cloneNode(deep) { const node = new Node(this.tagName); node._text = this._text; node.attributes = new Map(this.attributes); node.dataset = { ...this.dataset }; if (deep) node.append(...this.children.map((child) => child.cloneNode(true))); return node; }
  }

  document = {
    createElement: (tag) => new Node(tag),
    getElementById: (id) => allNodes.find((node) => node.id === id && node.isConnected) || null,
    querySelectorAll: (selector) => document.documentElement.querySelectorAll(selector),
    querySelector: (selector) => document.documentElement.querySelector(selector),
    addEventListener(type, handler) { const handlers = documentListeners.get(type) || []; handlers.push(handler); documentListeners.set(type, handlers); },
    dispatchEvent(event) { (documentListeners.get(event.type) || []).forEach((handler) => handler(event)); return !event.defaultPrevented; },
  };
  document.documentElement = new Node("html");
  document.documentElement.lang = "zh-Hant";
  document.body = new Node("body");
  document.documentElement.append(document.body);
  document.activeElement = document.body;

  function add(tag, id, parent = document.body, className = "") {
    const node = document.createElement(tag);
    if (id) node.id = id;
    if (className) node.className = className;
    parent.append(node);
    return node;
  }
  return { document, add };
}

export function createEvent(type, attributes = {}) {
  return { type, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...attributes };
}

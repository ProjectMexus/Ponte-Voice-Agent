function createElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "";
  if (Array.isArray(value)) return value.map(displayValue).filter(Boolean).join(" · ");
  if (typeof value === "object") return Object.values(value).map(displayValue).filter(Boolean).join(" · ");
  return String(value);
}

function workspaceFields(fields) {
  if (Array.isArray(fields)) return fields;
  if (!fields || typeof fields !== "object") return [];
  return Object.entries(fields).map(([label, value]) => ({ label, value }));
}

function localCopy(zh, en) {
  return document.documentElement.lang?.startsWith("en") ? en : zh;
}

function appendWorkspaceFields(container, fields, onAction) {
  const list = createElement("dl", "workspace-fields");
  const options = createElement("div", "workspace-options");
  options.setAttribute("role", "group");
  options.setAttribute("aria-label", localCopy("選擇項目", "Choose an option"));
  const embeddedActionIds = new Set();
  workspaceFields(fields).forEach((field) => {
    const label = displayValue(field?.label);
    const value = displayValue(field?.value);
    if (!label && !value) return;
    if (field?.action?.event && typeof field.action.event === "object" && !Array.isArray(field.action.event)) {
      const actionId = field.action.event.action_id;
      if (actionId) embeddedActionIds.add(actionId);
      const row = createElement("button", "workspace-field workspace-field-action");
      row.type = "button";
      if (typeof field.key === "string") row.dataset.fieldKey = field.key;
      const copy = createElement("span", "workspace-option-copy");
      copy.append(createElement("span", "workspace-field-label", label));
      if (value) copy.append(createElement("span", "workspace-field-value", value));
      const mark = createElement("span", "workspace-option-mark", "›");
      mark.setAttribute("aria-hidden", "true");
      row.append(copy, mark);
      row.addEventListener("click", () => {
        row.classList.add("is-submitting");
        row.setAttribute("aria-busy", "true");
        onAction?.(field.action.event);
      });
      options.append(row);
    } else {
      const row = createElement("div", "workspace-field");
      if (typeof field.key === "string") row.dataset.fieldKey = field.key;
      row.append(createElement("dt", "", label), createElement("dd", "", value));
      list.append(row);
    }
  });
  if (list.children.length) container.append(list);
  if (options.children.length) {
    container.append(options);
  }
  return embeddedActionIds;
}

function canonicalReceiptFields(receipt) {
  const appointment = receipt?.appointment || {};
  return [
    ["Service", appointment.service],
    ["Date", appointment.date],
    ["Time", appointment.time],
    ["Location", appointment.location],
    ["Status", appointment.status || receipt?.status],
    ["Issued", receipt?.issued_at],
    ["Task", receipt?.task_id],
  ].filter(([, value]) => displayValue(value));
}

function renderReceiptContent(container, receipt) {
  container.replaceChildren();
  if (!receipt) return;
  container.append(createElement("p", "artifact-status", "Service completed"));
  const list = createElement("dl", "artifact-fields");
  canonicalReceiptFields(receipt).forEach(([label, value]) => {
    const row = createElement("div", "artifact-field");
    row.append(createElement("dt", "", label), createElement("dd", "", displayValue(value)));
    list.append(row);
  });
  container.append(list, createElement("p", "artifact-reference", `Reference: ${receipt.receipt_id || "—"}`));
}

export function renderWorkspace(container, workspace, onAction, { headingId } = {}) {
  if (!container || !workspace || typeof workspace !== "object") return false;
  const card = createElement("article", "workspace-card");
  if (workspace.view) card.dataset.view = String(workspace.view);
  if (headingId) {
    card.setAttribute("aria-labelledby", headingId);
  } else {
    const header = createElement("header", "workspace-header");
    header.append(createElement("h2", "workspace-title", workspace.title ? String(workspace.title) : localCopy("服務資料", "Service details")));
    card.append(header);
  }
  if (Array.isArray(workspace.context) && workspace.context.length) {
    const context = createElement("dl", "agent-context");
    workspace.context.forEach((field) => {
      if (typeof field?.label !== "string" || typeof field?.value !== "string") return;
      const row = createElement("div", "agent-context-row");
      row.append(createElement("dt", "", field.label), createElement("dd", "", field.value));
      context.append(row);
    });
    if (context.children.length) card.append(context);
  }
  const embeddedActionIds = appendWorkspaceFields(card, workspace.fields, onAction);

  const actions = createElement("div", "action-list");
  actions.setAttribute("role", "group");
  actions.setAttribute("aria-label", localCopy("下一步", "Next action"));
  (Array.isArray(workspace.actions) ? workspace.actions : []).forEach((action) => {
    if (!action || typeof action !== "object" || !action.event || typeof action.event !== "object" || Array.isArray(action.event)) return;
    if (embeddedActionIds.has(action.event.action_id)) return;
    const button = createElement("button", "action-button", action.label || localCopy("繼續", "Continue"));
    button.type = "button";
    // Style explicit server decisions without deriving or changing their events.
    if (action.event.decision === "approve") button.classList.add("is-primary");
    if (action.event.decision === "reject") button.classList.add("is-destructive");
    // Preserve the complete event issued by the server, including identifiers.
    button.addEventListener("click", () => {
      button.classList.add("is-submitting");
      button.setAttribute("aria-busy", "true");
      onAction?.(action.event);
    });
    actions.append(button);
  });
  if (actions.children.length) {
    card.append(actions);
  }
  if (workspace.artifact && typeof workspace.artifact === "object" && workspace.artifact.title) {
    card.append(createElement("p", "workspace-artifact", String(workspace.artifact.title)));
  }
  container.append(card);
  return true;
}

export function createInteractionView({
  conversationRoot,
  approvalRoot,
  healthRoot,
  taskListRoot,
  errorRoot,
  artifactRoot,
  artifactContentRoot,
  onAction,
} = {}) {
  const workspaceRoot = taskListRoot || approvalRoot;
  let activeTaskId = null;
  let latestResponse = null;
  let lastReceipt = null;
  let lastFocusedElement = null;

  function closeArtifact() {
    if (!artifactRoot) return;
    artifactRoot.hidden = true;
    document.body.classList.remove("artifact-open");
    lastFocusedElement?.focus?.();
  }

  function openArtifact(receipt = lastReceipt) {
    if (!artifactRoot || !artifactContentRoot || !receipt) return;
    lastReceipt = receipt;
    lastFocusedElement = document.activeElement;
    renderReceiptContent(artifactContentRoot, receipt);
    artifactRoot.hidden = false;
    document.body.classList.add("artifact-open");
    artifactRoot.querySelector("[data-artifact-close]")?.focus();
  }

  function appendUserMessage(text) {
    if (!conversationRoot || !text) return;
    conversationRoot.append(createElement("p", "message message-user", String(text)));
  }

  function renderResponse(response) {
    latestResponse = response && typeof response === "object" ? response : {};
    if (workspaceRoot) {
      workspaceRoot.replaceChildren();
      renderWorkspace(workspaceRoot, latestResponse.workspace, onAction);
      if (!workspaceRoot.children.length && latestResponse.recovery) {
        const recovery = createElement("section", "recovery-panel");
        recovery.append(createElement("h3", "recovery-title", "Recovery"));
        recovery.append(createElement("p", "recovery-explanation", displayValue(latestResponse.recovery.reason)));
        workspaceRoot.append(recovery);
      }
    }
    if (latestResponse.receipt && latestResponse.receipt.receipt_id !== lastReceipt?.receipt_id) {
      lastReceipt = latestResponse.receipt;
      if (conversationRoot) {
        const receipt = createElement("button", "receipt-link", "View receipt");
        receipt.type = "button";
        receipt.addEventListener("click", () => openArtifact(latestResponse.receipt));
        conversationRoot.append(receipt);
      }
    }
    return latestResponse;
  }

  function startTask({ taskId = null } = {}) {
    activeTaskId = taskId || `UI-TASK-${Date.now().toString(36)}`;
    if (workspaceRoot) workspaceRoot.replaceChildren();
    return activeTaskId;
  }

  function updateTask(taskId, response) {
    activeTaskId = taskId || activeTaskId;
    return renderResponse(response);
  }

  function getTaskResponse(taskId) {
    return taskId === activeTaskId ? latestResponse : null;
  }

  function continueTask(taskId) {
    return taskId === activeTaskId;
  }

  function toggleTask() {
    return Boolean(latestResponse);
  }

  function failTask(taskId, error) {
    if (taskId && taskId !== activeTaskId) return;
    renderError(error);
  }

  function renderHealth(payload) {
    if (!healthRoot) return;
    const reachable = payload?.backend_reachable !== false;
    healthRoot.classList.toggle("is-ready", reachable);
    healthRoot.classList.toggle("is-offline", !reachable);
    healthRoot.textContent = reachable ? "Service connected" : "Service unavailable";
  }

  function renderError(error) {
    if (!errorRoot) return;
    errorRoot.hidden = false;
    errorRoot.textContent = error?.message || "The service could not complete this turn.";
  }

  function clearError() {
    if (!errorRoot) return;
    errorRoot.hidden = true;
    errorRoot.replaceChildren();
  }

  artifactRoot?.querySelectorAll("[data-artifact-close]").forEach((button) => button.addEventListener("click", closeArtifact));
  artifactRoot?.querySelector("#artifact-print")?.addEventListener("click", () => window.print());
  artifactRoot?.querySelector("#artifact-download")?.addEventListener("click", () => {
    const body = artifactContentRoot?.cloneNode(true).outerHTML || "";
    const html = `<!doctype html><html lang="en"><meta charset="utf-8"><title>Ponte receipt</title><body>${body}</body></html>`;
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
    link.download = `ponte-receipt-${lastReceipt?.receipt_id || "service"}.html`;
    link.click();
    URL.revokeObjectURL(link.href);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && artifactRoot && !artifactRoot.hidden) closeArtifact();
  });

  return {
    appendUserMessage,
    startTask,
    updateTask,
    getTaskResponse,
    continueTask,
    toggleTask,
    failTask,
    renderHealth,
    renderError,
    clearError,
    renderResponse,
    closeArtifact,
    openArtifact,
  };
}

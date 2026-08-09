import { renderWorkspace as renderCanonicalWorkspace } from "./interaction-view.js";

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function valueText(value) {
  if (value === null || value === undefined || value === "") return "";
  if (Array.isArray(value)) return value.map(valueText).filter(Boolean).join(" · ");
  if (typeof value === "object") return Object.values(value).map(valueText).filter(Boolean).join(" · ");
  return String(value);
}

function localCopy(zh, en) {
  return document.documentElement.lang?.startsWith("en") ? en : zh;
}

function canonicalReceiptFields(receipt) {
  const appointment = receipt?.appointment || {};
  return [
    [localCopy("服務", "Service"), appointment.service],
    [localCopy("日期", "Date"), appointment.date],
    [localCopy("時間", "Time"), appointment.time],
    [localCopy("地點", "Location"), appointment.location],
    [localCopy("狀態", "Status"), appointment.status || receipt?.status],
    [localCopy("發出時間", "Issued"), receipt?.issued_at],
    [localCopy("任務編號", "Task"), receipt?.task_id],
  ].filter(([, value]) => valueText(value));
}

function appendReceiptFields(container, receipt) {
  const list = element("dl", "voice-facts");
  canonicalReceiptFields(receipt).forEach(([label, value]) => {
    const row = element("div", "voice-fact");
    row.append(element("dt", "", label), element("dd", "", valueText(value)));
    list.append(row);
  });
  if (list.children.length) container.append(list);
}

function renderWorkspaceCard(container, workspace, onAction) {
  if (!workspace || typeof workspace !== "object") return;
  const childCount = container.children.length;
  renderCanonicalWorkspace(container, workspace, onAction, {headingId: container.closest("#service-workspace") ? "workspace-heading" : undefined});
  const card = container.children[childCount];
  if (!card) return;
  card.classList.add("voice-exception-card");
}

function renderRecovery(container, recovery) {
  if (!recovery || typeof recovery !== "object") return;
  const panel = element("section", "recovery-panel voice-exception-card");
  panel.setAttribute("role", "status");
  if (!container.closest("#service-workspace")) panel.append(element("h3", "recovery-title", localCopy("服務需要處理", "Service needs attention")));
  if (recovery.reason) panel.append(element("p", "recovery-explanation", String(recovery.reason)));
  if (recovery.message) panel.append(element("p", "recovery-explanation", String(recovery.message)));
  if (recovery.explanation) panel.append(element("p", "recovery-explanation", String(recovery.explanation)));
  container.append(panel);
}

export function createVoiceExceptions({ approvalRoot, errorRoot, artifactRoot, artifactContentRoot, onAction } = {}) {
  let lastReceipt = null;
  let lastFocusedElement = null;
  const exceptionSurface = approvalRoot?.closest(".voice-exceptions");
  const workspaceSurface = approvalRoot?.closest("#service-workspace");

  function syncExceptionSurface() {
    // Only actual agent-projected cards, recovery, or receipts open the workspace.
    // Errors have their own visible surface outside this panel.
    if (workspaceSurface) workspaceSurface.hidden = !approvalRoot?.children.length;
    exceptionSurface?.classList.toggle("has-content", Boolean(
      approvalRoot?.children.length || (errorRoot && !errorRoot.hidden),
    ));
  }

  function clearError() {
    if (!errorRoot) return;
    errorRoot.hidden = true;
    errorRoot.replaceChildren();
    syncExceptionSurface();
  }

  function renderError(error) {
    if (!errorRoot) return;
    errorRoot.replaceChildren();
    errorRoot.hidden = false;
    errorRoot.append(element("p", "voice-error-message", error?.message || localCopy("服務未能完成這次操作，請再試一次。", "The service could not complete this turn. Please try again.")));
    const dismiss = element("button", "voice-error-close", "×");
    dismiss.type = "button";
    dismiss.setAttribute("aria-label", localCopy("關閉錯誤訊息", "Dismiss error"));
    dismiss.addEventListener("click", clearError);
    errorRoot.append(dismiss);
    syncExceptionSurface();
  }

  function closeArtifact() {
    if (!artifactRoot) return;
    artifactRoot.hidden = true;
    document.body.classList.remove("artifact-open");
    if (lastFocusedElement?.isConnected) lastFocusedElement.focus?.();
  }

  function openArtifact(receipt = lastReceipt) {
    if (!artifactRoot || !artifactContentRoot || !receipt) return;
    lastReceipt = receipt;
    if (artifactRoot.hidden) lastFocusedElement = document.activeElement;
    artifactContentRoot.replaceChildren();
    appendReceiptFields(artifactContentRoot, receipt);
    artifactContentRoot.append(element("p", "artifact-reference", `${localCopy("回執編號", "Reference")}: ${receipt.receipt_id || "—"}`));
    artifactRoot.hidden = false;
    document.body.classList.add("artifact-open");
    artifactRoot.querySelector("button[data-artifact-close]")?.focus();
  }

  function renderWorkspace(response) {
    if (!approvalRoot) return;
    // Omitted workspace means the turn has no replacement projection. An
    // explicit null clears the previous service, while errors leave it intact.
    if (!Object.hasOwn(response || {}, "workspace") && !response?.recovery) return;
    approvalRoot.replaceChildren();
    renderWorkspaceCard(approvalRoot, response?.workspace, onAction);
    if (!approvalRoot.children.length) renderRecovery(approvalRoot, response?.recovery);
    syncExceptionSurface();
  }

  // Kept as the delivery-surface hook used by the avatar app. It renders only
  // the canonical workspace projection; confirmation decisions arrive inside
  // workspace.actions[].event and are never created in the browser.
  function renderApproval(response) {
    renderWorkspace(response);
  }

  function renderReceipt(receipt) {
    if (!approvalRoot || !receipt) return;
    lastReceipt = receipt;
    approvalRoot.querySelectorAll(".receipt-card").forEach((card) => card.remove());
    const receiptControl = document.getElementById("last-receipt");
    if (receiptControl) {
      approvalRoot.querySelectorAll(".receipt-summary").forEach((summary) => summary.remove());
      receiptControl.hidden = false;
      if (!approvalRoot.children.length) approvalRoot.append(element("p", "voice-exception-card receipt-reference receipt-summary", `${localCopy("回執編號", "Reference")}: ${receipt.receipt_id || "—"}`));
      syncExceptionSurface();
      return;
    }
    const card = element("section", "voice-exception-card receipt-card");
    card.append(element("p", "receipt-reference", `${localCopy("回執編號", "Reference")}: ${receipt.receipt_id || "—"}`));
    const button = element("button", "exception-button is-primary", localCopy("查看回執", "View receipt"));
    button.type = "button";
    button.addEventListener("click", () => openArtifact(receipt));
    card.append(button);
    approvalRoot.append(card);
    syncExceptionSurface();
  }

  function reset() {
    closeArtifact();
    lastReceipt = null;
    lastFocusedElement = null;
    approvalRoot?.replaceChildren();
    artifactContentRoot?.replaceChildren();
    clearError();
    syncExceptionSurface();
  }

  function renderResponse(response) {
    clearError();
    renderApproval(response);
    if (response?.receipt) renderReceipt(response.receipt);
    syncExceptionSurface();
  }

  artifactRoot?.querySelectorAll("[data-artifact-close]").forEach((button) => button.addEventListener("click", closeArtifact));
  artifactRoot?.querySelector("#artifact-print")?.addEventListener("click", () => window.print());
  artifactRoot?.querySelector("#artifact-download")?.addEventListener("click", () => {
    const body = artifactContentRoot?.cloneNode(true).outerHTML || "";
    const html = `<!doctype html><html lang="${document.documentElement.lang?.startsWith("en") ? "en" : "zh-Hant"}"><meta charset="utf-8"><title>Ponte receipt</title><body>${body}</body></html>`;
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
    link.download = `ponte-receipt-${lastReceipt?.receipt_id || "service"}.html`;
    link.click();
    URL.revokeObjectURL(link.href);
  });
  document.addEventListener("keydown", (event) => {
    if (!artifactRoot || artifactRoot.hidden) return;
    if (event.key === "Escape") { closeArtifact(); return; }
    if (event.key !== "Tab") return;
    const focusable = Array.from(artifactRoot.querySelectorAll("button, a[href], input, select, textarea, [tabindex]"))
      .filter((node) => !node.disabled && !node.hidden && node.getAttribute("tabindex") !== "-1");
    const first = focusable[0];
    const last = focusable.at(-1);
    if (!first) { event.preventDefault(); return; }
    if (event.shiftKey && (document.activeElement === first || !artifactRoot.contains(document.activeElement))) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && (document.activeElement === last || !artifactRoot.contains(document.activeElement))) {
      event.preventDefault(); first.focus();
    }
  });

  syncExceptionSurface();
  return { clearError, renderError, renderResponse, renderWorkspace, renderApproval, renderReceipt, openArtifact, closeArtifact, reset };
}

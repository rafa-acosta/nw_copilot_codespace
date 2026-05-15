const CUSTOM_MODEL_VALUE = "__custom__";

const state = {
  documents: [],
  messages: [],
  retrieval_ready: false,
  chunk_count: 0,
  supported_types: [],
  ollama: null,
};

const documentList = document.getElementById("document-list");
const messageList = document.getElementById("message-list");
const emptyState = document.getElementById("empty-state");
const chatScroll = document.getElementById("chat-scroll");
const composerShell = document.querySelector(".composer-shell");
const fileInput = document.getElementById("file-input");
const uploadDropzone = document.getElementById("upload-dropzone");
const sendButton = document.getElementById("send-button");
const chatInput = document.getElementById("chat-input");
const modeSelect = document.getElementById("mode-select");
const domainSelect = document.getElementById("domain-select");
const topKRange = document.getElementById("top-k-range");
const topKValue = document.getElementById("top-k-value");
const statusLine = document.getElementById("status-line");
const readinessIndicator = document.getElementById("readiness-indicator");
const sourceFilterList = document.getElementById("source-filter-list");
const documentCount = document.getElementById("document-count");
const chunkCount = document.getElementById("chunk-count");
const clearDocumentsButton = document.getElementById("clear-documents-button");
const clearChatButton = document.getElementById("clear-chat-button");
const refreshOllamaButton = document.getElementById("refresh-ollama-button");
const applyOllamaButton = document.getElementById("apply-ollama-button");
const chatModelSelect = document.getElementById("chat-model-select");
const embeddingModelSelect = document.getElementById("embedding-model-select");
const chatModelCustom = document.getElementById("chat-model-custom");
const embeddingModelCustom = document.getElementById("embedding-model-custom");
const ollamaStatus = document.getElementById("ollama-status");
const augmentedPromptEmpty = document.getElementById("augmented-prompt-empty");
const augmentedPromptContent = document.getElementById("augmented-prompt-content");
const augmentedSystemPrompt = document.getElementById("augmented-system-prompt");
const augmentedUserPrompt = document.getElementById("augmented-user-prompt");
const copyAugmentedPromptButton = document.getElementById("copy-augmented-prompt-button");

const activeSourceTypes = new Set();
const expandedCitationMessages = new Set();

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

async function fetchState() {
  const payload = await api("/api/state");
  applyState(payload.state);
}

function applyState(nextState, { scrollTarget = "bottom" } = {}) {
  state.documents = nextState.documents;
  state.messages = nextState.messages;
  state.retrieval_ready = nextState.retrieval_ready;
  state.chunk_count = nextState.chunk_count;
  state.supported_types = nextState.supported_types;
  state.ollama = nextState.ollama;

  renderDocuments();
  renderMessages({ scrollTarget });
  renderFilters();
  renderOllamaSettings();
  renderAugmentedPromptDebug();

  documentCount.textContent = String(state.documents.length);
  chunkCount.textContent = String(state.chunk_count);
  readinessIndicator.textContent = state.retrieval_ready
    ? `Indexed and ready across ${state.documents.length} document(s)`
    : "No indexed documents yet";
}

function renderDocuments() {
  documentList.innerHTML = "";
  const template = document.getElementById("document-item-template");

  if (!state.documents.length) {
    const empty = document.createElement("p");
    empty.className = "status-line";
    empty.textContent = "No documents loaded yet.";
    documentList.appendChild(empty);
    return;
  }

  for (const indexedDocument of state.documents) {
    const fragment = template.content.cloneNode(true);
    fragment.querySelector(".document-name").textContent = indexedDocument.filename;
    const domainLabel = indexedDocument.domain
      ? `${indexedDocument.domain} ${Math.round((Number(indexedDocument.domain_confidence) || 0) * 100)}%`
      : "unclassified";
    fragment.querySelector(".document-type").textContent = `${indexedDocument.source_type} • ${domainLabel}`;
    fragment.querySelector(".document-chunks").textContent = `${indexedDocument.chunk_count} chunk(s)`;
    fragment.querySelector(".document-item").title = indexedDocument.domain_reason || "";
    fragment.querySelector(".remove-document-button").addEventListener("click", async () => {
      await mutate("/api/documents/remove", { document_id: indexedDocument.document_id }, "Document removed.");
    });
    documentList.appendChild(fragment);
  }
}

function renderMessages({ preserveScroll = false, scrollTarget = "bottom" } = {}) {
  const previousScrollTop = chatScroll.scrollTop;
  messageList.innerHTML = "";
  const template = document.getElementById("message-template");
  const citationTemplate = document.getElementById("citation-template");

  emptyState.style.display = state.messages.length ? "none" : "flex";
  composerShell.classList.toggle("has-conversation", state.messages.length > 0);

  for (const message of state.messages) {
    const fragment = template.content.cloneNode(true);
    const article = fragment.querySelector(".message");
    const contentElement = fragment.querySelector(".message-content");
    article.classList.add(message.role);
    fragment.querySelector(".message-avatar").textContent = message.role === "user" ? "You" : "AI";
    fragment.querySelector(".message-role").textContent = message.role === "user" ? "You" : "Assistant";
    if (message.role === "assistant") {
      contentElement.innerHTML = renderMarkdown(message.content);
    } else {
      contentElement.textContent = message.content;
    }
    contentElement.appendChild(createCopyButton(message.content));

    const metaParts = [];
    if (message.meta?.retrieval_mode) {
      metaParts.push(message.meta.retrieval_mode.toUpperCase());
    }
    if (message.meta?.total_latency_ms) {
      metaParts.push(`total ${formatSeconds(message.meta.total_latency_ms)}`);
    }
    if (message.meta?.latency_ms) {
      metaParts.push(`retrieval ${Number(message.meta.latency_ms).toFixed(1)} ms`);
    }
    if (message.meta?.generation_latency_ms) {
      metaParts.push(`generation ${formatSeconds(message.meta.generation_latency_ms)}`);
    }
    if (message.meta?.result_count !== undefined) {
      metaParts.push(`${message.meta.result_count} result(s)`);
    }
    if (message.meta?.answer_model) {
      metaParts.push(message.meta.answer_model);
    }
    if (message.meta?.domain) {
      const domainMode = message.meta?.domain_mode === "manual" ? "manual" : "auto";
      const routed = `${String(message.meta.domain).toUpperCase()} ${domainMode}`;
      metaParts.push(routed);
    }
    if (message.meta?.domain_filter_applied) {
      metaParts.push("domain-filtered");
    }
    fragment.querySelector(".message-meta").textContent = metaParts.join(" • ");

    const actions = fragment.querySelector(".message-actions");
    const ragasResults = fragment.querySelector(".ragas-results");
    if (message.role === "assistant" && message.meta?.ragas_available) {
      const evaluateButton = document.createElement("button");
      evaluateButton.type = "button";
      evaluateButton.className = "ghost-button evaluate-button";
      evaluateButton.textContent = message.meta?.ragas_evaluated ? "Re-evaluate with RAGAS" : "Evaluate with RAGAS";
      evaluateButton.addEventListener("click", () => evaluateMessage(message.message_id, evaluateButton));
      actions.appendChild(evaluateButton);
      renderRagasResults(ragasResults, message.meta?.ragas);
    }

    const citations = message.citations || [];
    const citationToggle = fragment.querySelector(".citation-toggle");
    const citationList = fragment.querySelector(".citation-list");
    const citationsExpanded = expandedCitationMessages.has(message.message_id);
    if (citations.length) {
      citationToggle.hidden = false;
      citationToggle.textContent = `${citationsExpanded ? "Hide" : "Show"} sources (${citations.length})`;
      citationToggle.setAttribute("aria-expanded", String(citationsExpanded));
      citationToggle.addEventListener("click", () => {
        if (expandedCitationMessages.has(message.message_id)) {
          expandedCitationMessages.delete(message.message_id);
        } else {
          expandedCitationMessages.add(message.message_id);
        }
        renderMessages({ preserveScroll: true });
      });
      citationList.hidden = !citationsExpanded;
    }
    for (const citation of citations) {
      const citationFragment = citationTemplate.content.cloneNode(true);
      citationFragment.querySelector(".citation-label").textContent = citation.label;
      citationFragment.querySelector(".citation-score").textContent = formatCitationScore(citation);
      citationFragment.querySelector(".citation-excerpt").textContent = citation.excerpt;
      citationList.appendChild(citationFragment);
    }

    messageList.appendChild(fragment);
  }

  if (preserveScroll) {
    chatScroll.scrollTop = previousScrollTop;
  } else if (scrollTarget === "latest-assistant") {
    scrollLatestAssistantIntoView();
  } else {
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }
}

function formatCitationScore(citation) {
  const scoreParts = [
    ["rank", citation.score],
    ["fused", citation.fused_score],
    ["keyword", citation.keyword_score],
    ["dense", citation.dense_score],
  ];
  return scoreParts
    .filter(([, value]) => Number.isFinite(Number(value)))
    .map(([label, value]) => `${label} ${Number(value).toFixed(3)}`)
    .join(" · ");
}

function renderAugmentedPromptDebug() {
  const latestDebugMessage = [...state.messages]
    .reverse()
    .find((message) => message.role === "assistant" && message.meta?.augmented_prompt_debug);
  const debugPayload = latestDebugMessage?.meta?.augmented_prompt_debug;

  if (!debugPayload) {
    augmentedPromptEmpty.hidden = false;
    augmentedPromptContent.hidden = true;
    copyAugmentedPromptButton.disabled = true;
    augmentedSystemPrompt.textContent = "";
    augmentedUserPrompt.textContent = "";
    return;
  }

  augmentedPromptEmpty.hidden = true;
  augmentedPromptContent.hidden = false;
  copyAugmentedPromptButton.disabled = false;
  augmentedSystemPrompt.textContent = debugPayload.system || "";
  augmentedUserPrompt.textContent = debugPayload.user || "";
}

function scrollLatestAssistantIntoView() {
  const assistantMessages = messageList.querySelectorAll(".message.assistant");
  const latestAssistantMessage = assistantMessages[assistantMessages.length - 1];
  if (!latestAssistantMessage) {
    chatScroll.scrollTop = chatScroll.scrollHeight;
    return;
  }

  const scrollRect = chatScroll.getBoundingClientRect();
  const messageRect = latestAssistantMessage.getBoundingClientRect();
  chatScroll.scrollTop += messageRect.top - scrollRect.top - 4;
}

function createCopyButton(text) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ghost-button message-action-button copy-button";
  button.setAttribute("aria-label", "Copy message");
  button.title = "Copy message";

  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    try {
      await copyTextToClipboard(text);
      showCopyFeedback(button);
      setStatus("Message copied to clipboard.");
    } catch (error) {
      setStatus("Could not copy message to clipboard.", true);
    }
  });

  return button;
}

async function copyTextToClipboard(text) {
  const normalizedText = String(text || "");
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(normalizedText);
      return;
    } catch (error) {
      // Some browsers expose Clipboard API but block it outside secure contexts.
    }
  }

  copyTextWithSelection(normalizedText);
}

function copyTextWithSelection(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "0";
  textarea.style.top = "0";
  textarea.style.width = "1px";
  textarea.style.height = "1px";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);

  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) {
    throw new Error("Clipboard copy failed");
  }
}

function showCopyFeedback(button) {
  button.classList.add("copied");
  button.setAttribute("aria-label", "Copied");
  button.title = "Copied";
  window.setTimeout(() => {
    button.classList.remove("copied");
    button.setAttribute("aria-label", "Copy message");
    button.title = "Copy message";
  }, 1400);
}

function formatSeconds(milliseconds) {
  const seconds = Number(milliseconds || 0) / 1000;
  return `${seconds.toFixed(seconds >= 10 ? 1 : 2)} s`;
}

function renderRagasResults(container, ragas) {
  container.innerHTML = "";
  if (!ragas || !Array.isArray(ragas.metrics)) {
    return;
  }

  const summary = document.createElement("div");
  summary.className = "ragas-summary";
  summary.textContent = `RAGAS • ${ragas.model || "judge model"} • ${ragas.retrieved_context_count || 0} context(s)`;
  container.appendChild(summary);

  const grid = document.createElement("div");
  grid.className = "ragas-metric-grid";
  for (const metric of ragas.metrics) {
    const item = document.createElement("div");
    item.className = "ragas-metric";
    item.classList.toggle("has-error", Boolean(metric.error || metric.skipped));

    const name = document.createElement("span");
    name.className = "ragas-metric-name";
    name.textContent = String(metric.name || "").replace(/_/g, " ");

    const score = document.createElement("strong");
    score.className = "ragas-metric-score";
    score.textContent = metric.score === null || metric.score === undefined ? "n/a" : Number(metric.score).toFixed(3);

    item.appendChild(name);
    item.appendChild(score);
    if (metric.reason || metric.error) {
      const note = document.createElement("p");
      note.className = "ragas-metric-note";
      note.textContent = metric.error || metric.reason;
      item.appendChild(note);
    }
    grid.appendChild(item);
  }
  container.appendChild(grid);
}

function renderFilters() {
  if (sourceFilterList.childElementCount && sourceFilterList.dataset.initialized === "true") {
    for (const chip of sourceFilterList.querySelectorAll(".filter-chip")) {
      const sourceType = chip.dataset.sourceType;
      chip.classList.toggle("active", activeSourceTypes.has(sourceType));
    }
    return;
  }

  sourceFilterList.innerHTML = "";
  for (const sourceType of state.supported_types) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "filter-chip";
    chip.dataset.sourceType = sourceType;
    chip.textContent = sourceType;
    chip.addEventListener("click", () => {
      if (activeSourceTypes.has(sourceType)) {
        activeSourceTypes.delete(sourceType);
      } else {
        activeSourceTypes.add(sourceType);
      }
      chip.classList.toggle("active", activeSourceTypes.has(sourceType));
    });
    sourceFilterList.appendChild(chip);
  }
  sourceFilterList.dataset.initialized = "true";
}

function renderMarkdown(markdown) {
  const normalized = String(markdown || "").replace(/\r\n?/g, "\n");
  return renderMarkdownBlocks(normalized);
}

function renderMarkdownBlocks(markdown) {
  const html = [];
  const lines = markdown.split("\n");
  let paragraphLines = [];
  let listType = null;
  let listItems = [];
  let listHadBlankLine = false;
  let quoteLines = [];
  let inCodeFence = false;
  let codeFenceLanguage = "";
  let codeFenceLines = [];

  function flushParagraph() {
    if (!paragraphLines.length) {
      return;
    }
    html.push(`<p>${paragraphLines.map((line) => renderInlineMarkdown(line)).join("<br>")}</p>`);
    paragraphLines = [];
  }

  function flushList() {
    if (!listItems.length || !listType) {
      return;
    }
    const tag = listType === "ol" ? "ol" : "ul";
    html.push(
      `<${tag}>${listItems
        .map((item) => `<li>${renderInlineMarkdown(item).replace(/\n/g, "<br>")}</li>`)
        .join("")}</${tag}>`
    );
    listItems = [];
    listType = null;
    listHadBlankLine = false;
  }

  function flushQuote() {
    if (!quoteLines.length) {
      return;
    }
    html.push(`<blockquote>${renderMarkdownBlocks(quoteLines.join("\n"))}</blockquote>`);
    quoteLines = [];
  }

  function flushCodeFence() {
    const languageClass = codeFenceLanguage ? ` class="language-${escapeHtml(codeFenceLanguage)}"` : "";
    html.push(`<pre><code${languageClass}>${escapeHtml(codeFenceLines.join("\n"))}</code></pre>`);
    codeFenceLines = [];
    codeFenceLanguage = "";
  }

  for (const line of lines) {
    const codeFenceMatch = line.match(/^```([\w-]+)?\s*$/);
    if (inCodeFence) {
      if (codeFenceMatch) {
        flushCodeFence();
        inCodeFence = false;
      } else {
        codeFenceLines.push(line);
      }
      continue;
    }

    if (codeFenceMatch) {
      flushParagraph();
      flushList();
      flushQuote();
      inCodeFence = true;
      codeFenceLanguage = codeFenceMatch[1] || "";
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      if (quoteLines.length) {
        flushQuote();
        continue;
      }
      if (listItems.length) {
        listHadBlankLine = true;
        continue;
      }
      continue;
    }

    const orderedMatch = line.match(/^\s*\d+\.\s+(.*)$/);
    const unorderedMatch = line.match(/^\s*[-*+]\s+(.*)$/);

    if (listHadBlankLine && !orderedMatch && !unorderedMatch) {
      flushList();
    }

    if (/^\s*>\s?/.test(line)) {
      flushParagraph();
      flushList();
      quoteLines.push(line.replace(/^\s*>\s?/, ""));
      continue;
    }

    if (quoteLines.length) {
      flushQuote();
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = headingMatch[1].length;
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    if (/^\s*---+\s*$/.test(line) || /^\s*\*\*\*+\s*$/.test(line)) {
      flushParagraph();
      flushList();
      html.push("<hr>");
      continue;
    }

    if (orderedMatch) {
      flushParagraph();
      if (listType && listType !== "ol") {
        flushList();
      }
      listType = "ol";
      listItems.push(orderedMatch[1].trim());
      listHadBlankLine = false;
      continue;
    }

    if (unorderedMatch) {
      flushParagraph();
      if (listType === "ol" && listItems.length) {
        listItems[listItems.length - 1] += `\n- ${unorderedMatch[1].trim()}`;
        listHadBlankLine = false;
        continue;
      }
      if (listType && listType !== "ul") {
        flushList();
      }
      listType = "ul";
      listItems.push(unorderedMatch[1].trim());
      listHadBlankLine = false;
      continue;
    }

    if (listItems.length) {
      listItems[listItems.length - 1] += `\n${line.trim()}`;
      listHadBlankLine = false;
      continue;
    }

    paragraphLines.push(line.trim());
  }

  flushParagraph();
  flushList();
  flushQuote();
  if (inCodeFence) {
    flushCodeFence();
  }

  return html.join("");
}

function renderInlineMarkdown(text) {
  const placeholders = [];
  let safe = escapeHtml(String(text ?? ""));

  safe = safe.replace(/`([^`]+)`/g, (_, code) => {
    const key = `__CODE_${placeholders.length}__`;
    placeholders.push(`<code>${code}</code>`);
    return key;
  });

  safe = safe.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_, label, url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`
  );
  safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  safe = safe.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  safe = safe.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  safe = safe.replace(/_([^_\n]+)_/g, "<em>$1</em>");
  safe = safe.replace(/~~([^~]+)~~/g, "<del>$1</del>");

  placeholders.forEach((value, index) => {
    safe = safe.replace(`__CODE_${index}__`, value);
  });
  return safe;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderOllamaSettings() {
  const ollama = state.ollama;
  if (!ollama) {
    chatModelSelect.innerHTML = "";
    embeddingModelSelect.innerHTML = "";
    chatModelSelect.disabled = true;
    embeddingModelSelect.disabled = true;
    chatModelCustom.hidden = true;
    embeddingModelCustom.hidden = true;
    applyOllamaButton.disabled = true;
    refreshOllamaButton.disabled = true;
    setInlineStatus(ollamaStatus, "Ollama configuration is unavailable in this session.", true);
    return;
  }

  chatModelSelect.disabled = false;
  embeddingModelSelect.disabled = false;
  applyOllamaButton.disabled = false;
  refreshOllamaButton.disabled = false;

  populateModelSelect(chatModelSelect, ollama.available_models || [], ollama.chat_model);
  populateModelSelect(embeddingModelSelect, ollama.available_models || [], ollama.embedding_model);

  chatModelCustom.value = ollama.chat_model || "";
  embeddingModelCustom.value = ollama.embedding_model || "";
  syncCustomModelInput(chatModelSelect, chatModelCustom, ollama.chat_model);
  syncCustomModelInput(embeddingModelSelect, embeddingModelCustom, ollama.embedding_model);

  if (ollama.last_error) {
    setInlineStatus(ollamaStatus, ollama.last_error, true);
    return;
  }

  const modelCount = (ollama.available_models || []).length;
  const suffix = modelCount === 1 ? "" : "s";
  setInlineStatus(
    ollamaStatus,
    `Detected ${modelCount} installed model${suffix} at ${ollama.base_url}.`,
    false
  );
}

function populateModelSelect(selectElement, models, currentValue) {
  const installedModels = Array.isArray(models) ? models : [];
  selectElement.innerHTML = "";

  for (const modelName of installedModels) {
    const option = document.createElement("option");
    option.value = modelName;
    option.textContent = modelName;
    selectElement.appendChild(option);
  }

  const customOption = document.createElement("option");
  customOption.value = CUSTOM_MODEL_VALUE;
  customOption.textContent = "Custom model...";
  selectElement.appendChild(customOption);

  if (currentValue && installedModels.includes(currentValue)) {
    selectElement.value = currentValue;
  } else {
    selectElement.value = CUSTOM_MODEL_VALUE;
  }
}

function syncCustomModelInput(selectElement, inputElement, currentValue = "") {
  const isCustom = selectElement.value === CUSTOM_MODEL_VALUE;
  inputElement.hidden = !isCustom;
  if (isCustom && !inputElement.value.trim()) {
    inputElement.value = currentValue || "";
  }
}

function setInlineStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

async function mutate(path, body, successMessage, workingMessage = "Working...") {
  setStatus(workingMessage);
  try {
    const payload = await api(path, {
      method: "POST",
      body: JSON.stringify(body || {}),
    });
    applyState(payload.state);
    setStatus(payload.message || successMessage || "Done.");
  } catch (error) {
    setStatus(error.message, true);
  }
}

function setStatus(message, isError = false) {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", isError);
}

function selectedModelValue(selectElement, inputElement) {
  if (selectElement.value === CUSTOM_MODEL_VALUE) {
    return inputElement.value.trim();
  }
  return selectElement.value.trim();
}

async function applyOllamaSettings() {
  const chatModel = selectedModelValue(chatModelSelect, chatModelCustom);
  const embeddingModel = selectedModelValue(embeddingModelSelect, embeddingModelCustom);

  if (!chatModel) {
    setStatus("Choose a chat model before applying settings.", true);
    return;
  }
  if (!embeddingModel) {
    setStatus("Choose an embedding model before applying settings.", true);
    return;
  }

  await mutate(
    "/api/settings/ollama",
    {
      chat_model: chatModel,
      embedding_model: embeddingModel,
    },
    "Ollama models updated.",
    "Updating Ollama models..."
  );
}

async function refreshOllamaModels() {
  await mutate(
    "/api/settings/ollama/refresh",
    {},
    "Refreshed local Ollama models.",
    "Refreshing Ollama models..."
  );
}

async function evaluateMessage(messageId, button) {
  const previousLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Evaluating...";
  setStatus("Evaluating answer with RAGAS...");

  try {
    const payload = await api("/api/chat/evaluate", {
      method: "POST",
      body: JSON.stringify({ message_id: messageId }),
    });
    applyState(payload.state);
    setStatus(payload.message || "RAGAS evaluation complete.");
  } catch (error) {
    setStatus(error.message, true);
    button.disabled = false;
    button.textContent = previousLabel;
  }
}

async function sendMessage() {
  const message = chatInput.value.trim();
  if (!message) {
    return;
  }

  chatInput.value = "";
  autoresizeTextarea();

  const startedAt = performance.now();
  const updateElapsedStatus = () => {
    setStatus(`Searching indexed documents... ${formatSeconds(performance.now() - startedAt)}`);
  };
  updateElapsedStatus();
  const timerId = window.setInterval(updateElapsedStatus, 1000);

  try {
    const payload = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        mode: modeSelect.value,
        domain: domainSelect.value,
        top_k: Number(topKRange.value),
        source_types: Array.from(activeSourceTypes),
      }),
    });
    applyState(payload.state, { scrollTarget: "latest-assistant" });
    setStatus(`${payload.message || "Answer ready."} Took ${formatSeconds(performance.now() - startedAt)}.`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    window.clearInterval(timerId);
  }
}

function autoresizeTextarea() {
  chatInput.style.height = "auto";
  chatInput.style.height = `${Math.min(chatInput.scrollHeight, 180)}px`;
}

async function fileToBase64(file) {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary);
}

async function uploadFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) {
    return;
  }

  setStatus(`Indexing ${files.length} file(s)...`);

  try {
    const payloadFiles = [];
    for (const file of files) {
      payloadFiles.push({
        name: file.name,
        content_base64: await fileToBase64(file),
      });
    }

    const payload = await api("/api/documents/upload", {
      method: "POST",
      body: JSON.stringify({ files: payloadFiles }),
    });
    applyState(payload.state);
    setStatus(payload.message || `Indexed ${files.length} file(s).`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    fileInput.value = "";
  }
}

sendButton.addEventListener("click", sendMessage);
applyOllamaButton.addEventListener("click", applyOllamaSettings);
refreshOllamaButton.addEventListener("click", refreshOllamaModels);
chatModelSelect.addEventListener("change", () => syncCustomModelInput(chatModelSelect, chatModelCustom, state.ollama?.chat_model));
embeddingModelSelect.addEventListener("change", () =>
  syncCustomModelInput(embeddingModelSelect, embeddingModelCustom, state.ollama?.embedding_model)
);
chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});
chatInput.addEventListener("input", autoresizeTextarea);
fileInput.addEventListener("change", (event) => uploadFiles(event.target.files));
uploadDropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  uploadDropzone.classList.add("dragging");
});
uploadDropzone.addEventListener("dragleave", () => {
  uploadDropzone.classList.remove("dragging");
});
uploadDropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  uploadDropzone.classList.remove("dragging");
  uploadFiles(event.dataTransfer.files);
});
topKRange.addEventListener("input", () => {
  topKValue.textContent = topKRange.value;
});
clearDocumentsButton.addEventListener("click", () => mutate("/api/documents/clear", {}, "All documents cleared."));
clearChatButton.addEventListener("click", () => mutate("/api/chat/reset", {}, "Chat cleared."));
copyAugmentedPromptButton.addEventListener("click", async () => {
  const text = [
    "SYSTEM:",
    augmentedSystemPrompt.textContent || "",
    "",
    "USER:",
    augmentedUserPrompt.textContent || "",
  ].join("\n");
  try {
    await copyTextToClipboard(text);
    setStatus("Augmented prompt copied to clipboard.");
  } catch (error) {
    setStatus("Could not copy augmented prompt to clipboard.", true);
  }
});

fetchState().catch((error) => setStatus(error.message, true));

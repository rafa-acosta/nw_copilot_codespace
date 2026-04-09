const state = {
  documents: [],
  messages: [],
  retrieval_ready: false,
  chunk_count: 0,
  supported_types: [],
};

const documentList = document.getElementById("document-list");
const messageList = document.getElementById("message-list");
const emptyState = document.getElementById("empty-state");
const chatScroll = document.getElementById("chat-scroll");
const fileInput = document.getElementById("file-input");
const uploadDropzone = document.getElementById("upload-dropzone");
const sendButton = document.getElementById("send-button");
const chatInput = document.getElementById("chat-input");
const modeSelect = document.getElementById("mode-select");
const topKRange = document.getElementById("top-k-range");
const topKValue = document.getElementById("top-k-value");
const statusLine = document.getElementById("status-line");
const readinessIndicator = document.getElementById("readiness-indicator");
const sourceFilterList = document.getElementById("source-filter-list");
const documentCount = document.getElementById("document-count");
const chunkCount = document.getElementById("chunk-count");
const clearDocumentsButton = document.getElementById("clear-documents-button");
const clearChatButton = document.getElementById("clear-chat-button");

const activeSourceTypes = new Set();

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

function applyState(nextState) {
  state.documents = nextState.documents;
  state.messages = nextState.messages;
  state.retrieval_ready = nextState.retrieval_ready;
  state.chunk_count = nextState.chunk_count;
  state.supported_types = nextState.supported_types;

  renderDocuments();
  renderMessages();
  renderFilters();

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

  for (const document of state.documents) {
    const fragment = template.content.cloneNode(true);
    fragment.querySelector(".document-name").textContent = document.filename;
    fragment.querySelector(".document-type").textContent = document.source_type;
    fragment.querySelector(".document-chunks").textContent = `${document.chunk_count} chunk(s)`;
    fragment.querySelector(".remove-document-button").addEventListener("click", async () => {
      await mutate("/api/documents/remove", { document_id: document.document_id }, "Document removed.");
    });
    documentList.appendChild(fragment);
  }
}

function renderMessages() {
  messageList.innerHTML = "";
  const template = document.getElementById("message-template");
  const citationTemplate = document.getElementById("citation-template");

  emptyState.style.display = state.messages.length ? "none" : "flex";

  for (const message of state.messages) {
    const fragment = template.content.cloneNode(true);
    const article = fragment.querySelector(".message");
    article.classList.add(message.role);
    fragment.querySelector(".message-avatar").textContent = message.role === "user" ? "You" : "AI";
    fragment.querySelector(".message-role").textContent = message.role === "user" ? "You" : "Assistant";
    fragment.querySelector(".message-content").textContent = message.content;

    const metaParts = [];
    if (message.meta?.retrieval_mode) {
      metaParts.push(message.meta.retrieval_mode.toUpperCase());
    }
    if (message.meta?.latency_ms) {
      metaParts.push(`${Number(message.meta.latency_ms).toFixed(1)} ms`);
    }
    if (message.meta?.result_count !== undefined) {
      metaParts.push(`${message.meta.result_count} result(s)`);
    }
    if (message.meta?.answer_model) {
      metaParts.push(message.meta.answer_model);
    }
    fragment.querySelector(".message-meta").textContent = metaParts.join(" • ");

    const citationList = fragment.querySelector(".citation-list");
    for (const citation of message.citations || []) {
      const citationFragment = citationTemplate.content.cloneNode(true);
      citationFragment.querySelector(".citation-label").textContent = citation.label;
      citationFragment.querySelector(".citation-score").textContent = citation.score.toFixed(3);
      citationFragment.querySelector(".citation-excerpt").textContent = citation.excerpt;
      citationList.appendChild(citationFragment);
    }

    messageList.appendChild(fragment);
  }

  chatScroll.scrollTop = chatScroll.scrollHeight;
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

async function sendMessage() {
  const message = chatInput.value.trim();
  if (!message) {
    return;
  }

  chatInput.value = "";
  autoresizeTextarea();

  await mutate(
    "/api/chat",
    {
      message,
      mode: modeSelect.value,
      top_k: Number(topKRange.value),
      source_types: Array.from(activeSourceTypes),
    },
    "Answer ready.",
    "Searching indexed documents..."
  );
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

fetchState().catch((error) => setStatus(error.message, true));

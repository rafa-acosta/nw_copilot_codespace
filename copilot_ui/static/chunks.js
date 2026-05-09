const chunkState = {
  documents: [],
  chunks: [],
  total: 0,
};

const summary = document.getElementById("chunks-summary");
const documentSelect = document.getElementById("chunk-document-select");
const searchInput = document.getElementById("chunk-search-input");
const emptyState = document.getElementById("chunks-empty-state");
const chunkList = document.getElementById("chunk-list");
const chunkTemplate = document.getElementById("chunk-card-template");

async function api(path) {
  const response = await fetch(path);
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

async function fetchChunks() {
  const params = new URLSearchParams({ limit: "1000" });
  if (documentSelect.value) {
    params.set("document_id", documentSelect.value);
  }

  summary.textContent = "Loading indexed content...";
  const payload = await api(`/api/chunks?${params.toString()}`);
  chunkState.documents = payload.documents || [];
  chunkState.chunks = payload.chunks || [];
  chunkState.total = Number(payload.total || 0);

  renderDocumentOptions();
  renderChunks();
}

function renderDocumentOptions() {
  const selectedValue = documentSelect.value;
  documentSelect.innerHTML = "";

  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "All documents";
  documentSelect.appendChild(allOption);

  for (const indexedDocument of chunkState.documents) {
    const option = document.createElement("option");
    option.value = indexedDocument.document_id;
    option.textContent = `${indexedDocument.filename} (${indexedDocument.chunk_count})`;
    documentSelect.appendChild(option);
  }

  documentSelect.value = Array.from(documentSelect.options).some((option) => option.value === selectedValue)
    ? selectedValue
    : "";
}

function renderChunks() {
  const query = searchInput.value.trim().toLowerCase();
  const visibleChunks = query
    ? chunkState.chunks.filter((chunk) => searchableChunkText(chunk).includes(query))
    : chunkState.chunks;

  chunkList.innerHTML = "";
  emptyState.style.display = chunkState.chunks.length ? "none" : "flex";

  const selectedDocument = documentSelect.value
    ? chunkState.documents.find((indexedDocument) => indexedDocument.document_id === documentSelect.value)
    : null;
  const scope = selectedDocument ? selectedDocument.filename : "all documents";
  summary.textContent = `${visibleChunks.length} visible chunk(s) from ${scope}. ${chunkState.total} indexed in this view.`;

  for (const [index, chunk] of visibleChunks.entries()) {
    const fragment = chunkTemplate.content.cloneNode(true);
    const metadata = chunk.metadata || {};
    const title = fragment.querySelector(".chunk-title");
    const subtitle = fragment.querySelector(".chunk-subtitle");
    const type = fragment.querySelector(".chunk-type");
    const metadataContainer = fragment.querySelector(".chunk-metadata");
    const content = fragment.querySelector(".chunk-content");

    title.textContent = `Chunk ${index + 1}`;
    subtitle.textContent = chunk.chunk_id || "No chunk id";
    type.textContent = chunk.source_type || "unknown";
    content.textContent = chunk.content || "";

    for (const item of metadataItems(metadata, chunk.filename)) {
      const pill = document.createElement("span");
      pill.className = "metadata-pill";
      pill.textContent = item;
      metadataContainer.appendChild(pill);
    }

    chunkList.appendChild(fragment);
  }
}

function metadataItems(metadata, filename) {
  const items = [];
  if (filename || metadata.filename) {
    items.push(`file: ${filename || metadata.filename}`);
  }
  if (metadata.page_number) {
    items.push(`page: ${metadata.page_number}`);
  }
  if (metadata.section) {
    items.push(`section: ${metadata.section}`);
  }
  if (metadata.sheet_name) {
    items.push(`sheet: ${metadata.sheet_name}`);
  }
  if (metadata.row_start || metadata.row_end) {
    items.push(`rows: ${metadata.row_start || "?"}-${metadata.row_end || "?"}`);
  }
  if (metadata.json_key_path) {
    items.push(`json: ${metadata.json_key_path}`);
  }
  if (metadata.cisco_feature) {
    items.push(`cisco: ${metadata.cisco_feature}`);
  }
  if (metadata.domain) {
    items.push(`domain: ${metadata.domain}`);
  }
  return items;
}

function searchableChunkText(chunk) {
  return [
    chunk.content,
    chunk.chunk_id,
    chunk.filename,
    chunk.source_type,
    JSON.stringify(chunk.metadata || {}),
  ]
    .join(" ")
    .toLowerCase();
}

documentSelect.addEventListener("change", () => {
  fetchChunks().catch((error) => {
    summary.textContent = error.message;
    summary.classList.add("error");
  });
});
searchInput.addEventListener("input", renderChunks);

fetchChunks().catch((error) => {
  summary.textContent = error.message;
  summary.classList.add("error");
});

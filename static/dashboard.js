const API = "/api";
let currentFilter = "";
let currentDocId = null;

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const uploadStatus = document.getElementById("uploadStatus");
const docList = document.getElementById("docList");
const emptyState = document.getElementById("emptyState");

// --- Upload interactions ---
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) uploadFile(fileInput.files[0]);
  fileInput.value = "";
});

function setStatus(text, kind) {
  uploadStatus.hidden = false;
  uploadStatus.textContent = text;
  uploadStatus.className = "upload-status " + (kind || "");
}

async function uploadFile(file) {
  setStatus(`Reading ${file.name}…`, "progress");
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await fetch(`${API}/documents`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    if (data.status === "failed") {
      setStatus(`Could not read ${file.name}: ${data.error_message}`, "error");
    } else {
      setStatus(`Extracted ${data.char_count} characters from ${file.name}.`, "success");
    }
    await refreshAll();
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  }
}

// --- Filters ---
document.querySelectorAll(".filter-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentFilter = btn.dataset.filter;
    loadDocuments();
  });
});

// --- Data loading ---
async function loadStats() {
  const res = await fetch(`${API}/stats`);
  const s = await res.json();
  document.getElementById("statTotal").textContent = s.total_documents;
  document.getElementById("statChars").textContent = s.total_characters_extracted.toLocaleString();
  document.getElementById("statConf").textContent = s.average_confidence != null ? `${s.average_confidence}%` : "—";
}

function timeAgo(iso) {
  const diff = (Date.now() - new Date(iso + "Z")) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

async function loadDocuments() {
  const params = new URLSearchParams();
  if (currentFilter) params.set("status", currentFilter);
  const res = await fetch(`${API}/documents?${params}`);
  const docs = await res.json();

  docList.querySelectorAll(".doc-row").forEach((el) => el.remove());
  emptyState.hidden = docs.length > 0;

  docs.forEach((doc) => {
    const row = document.createElement("div");
    row.className = "doc-row";
    row.innerHTML = `
      <span class="doc-name">${escapeHtml(doc.original_filename)}</span>
      <span class="doc-meta">${doc.char_count} chars${doc.confidence ? ` · ${Math.round(doc.confidence)}% conf.` : ""}</span>
      <span class="doc-meta">${timeAgo(doc.created_at)}</span>
      <span class="doc-status ${doc.status}">${doc.status}</span>
    `;
    row.addEventListener("click", () => openPreview(doc.id));
    docList.appendChild(row);
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function refreshAll() {
  await Promise.all([loadStats(), loadDocuments()]);
}

// --- Preview modal ---
const overlay = document.getElementById("previewOverlay");
document.getElementById("previewClose").addEventListener("click", closePreview);
overlay.addEventListener("click", (e) => { if (e.target === overlay) closePreview(); });

async function openPreview(id) {
  const res = await fetch(`${API}/documents/${id}`);
  if (!res.ok) return;
  const doc = await res.json();
  currentDocId = id;
  document.getElementById("previewTitle").textContent = doc.original_filename;
  document.getElementById("previewText").textContent = doc.extracted_text || "(no text extracted)";
  document.getElementById("downloadTxt").href = `${API}/documents/${id}/download?fmt=txt`;
  document.getElementById("downloadPdf").href = `${API}/documents/${id}/download?fmt=pdf`;
  overlay.hidden = false;
}

function closePreview() {
  overlay.hidden = true;
  currentDocId = null;
}

document.getElementById("deleteDoc").addEventListener("click", async () => {
  if (currentDocId == null) return;
  if (!confirm("Delete this document and its files?")) return;
  await fetch(`${API}/documents/${currentDocId}`, { method: "DELETE" });
  closePreview();
  await refreshAll();
});

refreshAll();

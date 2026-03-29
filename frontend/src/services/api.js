import axios from "axios";
import { getIdToken } from "./auth";
import config from "../config";

const api = axios.create({ baseURL: config.api.baseUrl });

// Attach JWT token to every request
api.interceptors.request.use(async (req) => {
  const token = await getIdToken();
  req.headers.Authorization = `Bearer ${token}`;
  return req;
});

// ── Documents ──────────────────────────────────────────────────────────────────

export async function listDocuments() {
  const { data } = await api.get("/documents");
  return data.documents;
}

export async function requestUpload(filename, contentType) {
  const { data } = await api.post("/documents", { filename, content_type: contentType });
  return data; // { document_id, upload_url, s3_key }
}

export async function uploadFileToS3(uploadUrl, file) {
  // Upload directly to S3 using the presigned URL (no auth header needed)
  await axios.put(uploadUrl, file, {
    headers: { "Content-Type": file.type },
    onUploadProgress: undefined, // caller can wrap with their own handler
  });
}

export async function startProcessing(documentId) {
  const { data } = await api.post(`/documents/${documentId}/process`);
  return data;
}

export async function getDocument(documentId) {
  const { data } = await api.get(`/documents/${documentId}`);
  return data;
}

export async function deleteDocument(documentId) {
  await api.delete(`/documents/${documentId}`);
}

// ── AI / Q&A ──────────────────────────────────────────────────────────────────

export async function askQuestion(documentId, question) {
  const { data } = await api.post(`/documents/${documentId}/qa`, { question });
  return data; // { answer, sources }
}

// ── Search ────────────────────────────────────────────────────────────────────

export async function searchDocuments(query, type = "semantic") {
  const { data } = await api.post("/search", { query, type });
  return data; // { results, count, query }
}

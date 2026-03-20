import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { requestUpload, startProcessing } from "../services/api";

const ACCEPTED_TYPES = {
  "application/pdf": ".pdf",
  "image/jpeg": ".jpg, .jpeg",
  "image/png": ".png",
  "application/msword": ".doc",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
};

export default function Upload() {
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState(""); // "uploading" | "queued" | "done" | "error"
  const [error, setError] = useState("");
  const fileInputRef = useRef();
  const navigate = useNavigate();

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) validateAndSet(dropped);
  }

  function handleFileChange(e) {
    if (e.target.files[0]) validateAndSet(e.target.files[0]);
  }

  function validateAndSet(f) {
    if (!ACCEPTED_TYPES[f.type]) {
      return setError("Unsupported file type. Please upload PDF, JPEG, PNG, DOC, or DOCX.");
    }
    setError("");
    setFile(f);
  }

  async function handleUpload() {
    if (!file) return;
    setError("");
    setStage("uploading");
    setProgress(0);

    try {
      // Step 1: Get presigned URL
      const { document_id, upload_url } = await requestUpload(file.name, file.type);

      // Step 2: Upload file directly to S3
      await axios.put(upload_url, file, {
        headers: { "Content-Type": file.type },
        onUploadProgress: (evt) => {
          setProgress(Math.round((evt.loaded / evt.total) * 100));
        },
      });

      // Step 3: Trigger processing pipeline
      setStage("queued");
      await startProcessing(document_id);

      setStage("done");
      setTimeout(() => navigate("/dashboard"), 1500);
    } catch (err) {
      setError(err.response?.data?.error || err.message || "Upload failed");
      setStage("error");
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Upload Document</h2>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {stage === "done" ? (
        <div className="alert alert-success">
          Document uploaded and queued for processing. Redirecting to dashboard...
        </div>
      ) : (
        <>
          <div
            className={`dropzone ${dragOver ? "dragover" : ""} ${file ? "has-file" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={Object.values(ACCEPTED_TYPES).join(",")}
              onChange={handleFileChange}
              style={{ display: "none" }}
            />
            {file ? (
              <div>
                <p className="dropzone-filename">{file.name}</p>
                <p className="dropzone-size">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
            ) : (
              <div>
                <p className="dropzone-prompt">Drag & drop a file here, or click to browse</p>
                <p className="dropzone-types">PDF, JPEG, PNG, DOC, DOCX</p>
              </div>
            )}
          </div>

          {stage === "uploading" && (
            <div className="progress-bar-wrap">
              <div className="progress-bar" style={{ width: `${progress}%` }} />
              <span>{progress}%</span>
            </div>
          )}

          {stage === "queued" && (
            <p className="status-text">Starting AI processing pipeline...</p>
          )}

          <button
            className="btn btn-primary"
            onClick={handleUpload}
            disabled={!file || stage === "uploading" || stage === "queued"}
          >
            {stage === "uploading" ? "Uploading..." : stage === "queued" ? "Processing..." : "Upload & Analyse"}
          </button>
        </>
      )}
    </div>
  );
}

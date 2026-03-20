import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listDocuments } from "../services/api";
import { onMessage } from "../services/websocket";
import StatusBadge from "../components/StatusBadge";

export default function Dashboard() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDocuments();

    // Update document status in real-time via WebSocket
    const unsubscribe = onMessage("PROCESSING_COMPLETE", (payload) => {
      setDocuments((prev) =>
        prev.map((doc) =>
          doc.document_id === payload.document_id
            ? { ...doc, status: "COMPLETE", summary: payload.summary, keywords: payload.keywords }
            : doc
        )
      );
    });

    return unsubscribe;
  }, []);

  async function fetchDocuments() {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch (err) {
      setError("Failed to load documents");
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="loading">Loading documents...</div>;

  return (
    <div className="page">
      <div className="page-header">
        <h2>My Documents</h2>
        <Link to="/upload" className="btn btn-primary">Upload New</Link>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {documents.length === 0 ? (
        <div className="empty-state">
          <p>No documents yet.</p>
          <Link to="/upload" className="btn btn-primary">Upload your first document</Link>
        </div>
      ) : (
        <div className="document-grid">
          {documents.map((doc) => (
            <Link
              key={doc.document_id}
              to={`/documents/${doc.document_id}`}
              className="document-card"
            >
              <div className="document-card-header">
                <span className="document-icon">
                  {doc.content_type === "application/pdf" ? "PDF" : "IMG"}
                </span>
                <StatusBadge status={doc.status} />
              </div>
              <h3 className="document-name">{doc.filename}</h3>
              <p className="document-date">
                {new Date(doc.created_at).toLocaleDateString()}
              </p>
              {doc.keywords && doc.keywords.length > 0 && (
                <div className="keyword-list">
                  {doc.keywords.slice(0, 3).map((kw) => (
                    <span key={kw} className="keyword-tag">{kw}</span>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

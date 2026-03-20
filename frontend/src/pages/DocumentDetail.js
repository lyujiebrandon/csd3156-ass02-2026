import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { getDocument, askQuestion } from "../services/api";
import { onMessage } from "../services/websocket";
import StatusBadge from "../components/StatusBadge";

export default function DocumentDetail() {
  const { documentId } = useParams();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Q&A state
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const chatEndRef = useRef();

  useEffect(() => {
    fetchDoc();

    // Listen for real-time processing completion
    const unsubscribe = onMessage("PROCESSING_COMPLETE", (payload) => {
      if (payload.document_id === documentId) {
        setDoc((prev) => prev ? {
          ...prev,
          status: "COMPLETE",
          summary: payload.summary,
          keywords: payload.keywords,
        } : prev);
      }
    });

    return unsubscribe;
  }, [documentId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function fetchDoc() {
    try {
      const data = await getDocument(documentId);
      setDoc(data);
    } catch (err) {
      setError("Failed to load document");
    } finally {
      setLoading(false);
    }
  }

  async function handleAsk(e) {
    e.preventDefault();
    if (!question.trim()) return;

    const userMsg = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setQuestion("");
    setAsking(true);

    try {
      const result = await askQuestion(documentId, question);
      setMessages((prev) => [...prev, { role: "assistant", content: result.answer, sources: result.sources }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "error", content: "Failed to get answer. Please try again." }]);
    } finally {
      setAsking(false);
    }
  }

  if (loading) return <div className="loading">Loading document...</div>;
  if (error) return <div className="alert alert-error">{error}</div>;
  if (!doc) return null;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>{doc.filename}</h2>
          <StatusBadge status={doc.status} />
        </div>
      </div>

      {/* Summary */}
      {doc.summary && (
        <section className="card">
          <h3>Summary</h3>
          <p>{doc.summary}</p>
        </section>
      )}

      {/* Keywords */}
      {doc.keywords && doc.keywords.length > 0 && (
        <section className="card">
          <h3>Keywords</h3>
          <div className="keyword-list">
            {doc.keywords.map((kw) => (
              <span key={kw} className="keyword-tag">{kw}</span>
            ))}
          </div>
        </section>
      )}

      {doc.status !== "COMPLETE" && (
        <div className="alert alert-info">
          Document is still being processed. Q&A will be available once complete.
        </div>
      )}

      {/* Q&A Chat */}
      {doc.status === "COMPLETE" && (
        <section className="card chat-section">
          <h3>Ask a Question</h3>
          <div className="chat-messages">
            {messages.length === 0 && (
              <p className="chat-empty">Ask anything about this document...</p>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`chat-message ${msg.role}`}>
                <span className="chat-role">{msg.role === "user" ? "You" : "DocuMind"}</span>
                <p>{msg.content}</p>
              </div>
            ))}
            {asking && (
              <div className="chat-message assistant">
                <span className="chat-role">DocuMind</span>
                <p className="typing">Thinking...</p>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <form onSubmit={handleAsk} className="chat-input-row">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What is this document about?"
              disabled={asking}
            />
            <button type="submit" className="btn btn-primary" disabled={asking || !question.trim()}>
              Ask
            </button>
          </form>
        </section>
      )}
    </div>
  );
}

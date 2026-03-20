import { useState } from "react";
import { Link } from "react-router-dom";
import { searchDocuments } from "../services/api";
import StatusBadge from "../components/StatusBadge";

export default function Search() {
  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState("semantic");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setError("");
    setLoading(true);
    try {
      const data = await searchDocuments(query, searchType);
      setResults(data);
    } catch (err) {
      setError("Search failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Search Documents</h2>
      </div>

      <form onSubmit={handleSearch} className="search-form">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search your documents..."
          className="search-input"
        />
        <div className="search-type-toggle">
          <label>
            <input
              type="radio"
              value="semantic"
              checked={searchType === "semantic"}
              onChange={() => setSearchType("semantic")}
            />
            Semantic
          </label>
          <label>
            <input
              type="radio"
              value="keyword"
              checked={searchType === "keyword"}
              onChange={() => setSearchType("keyword")}
            />
            Keyword
          </label>
        </div>
        <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {error && <div className="alert alert-error">{error}</div>}

      {results && (
        <div className="search-results">
          <p className="search-count">
            {results.count} result{results.count !== 1 ? "s" : ""} for "{results.query}"
          </p>

          {results.count === 0 ? (
            <div className="empty-state">No matching documents found.</div>
          ) : (
            results.results.map((result, i) => (
              <Link
                key={`${result.document_id}-${i}`}
                to={`/documents/${result.document_id}`}
                className="search-result-card"
              >
                <div className="search-result-header">
                  <span className="document-name">{result.filename}</span>
                  <StatusBadge status={result.status} />
                  <span className="search-score">Score: {result.score?.toFixed(2)}</span>
                </div>
                <p className="search-excerpt">{result.text?.slice(0, 200)}...</p>
              </Link>
            ))
          )}
        </div>
      )}
    </div>
  );
}

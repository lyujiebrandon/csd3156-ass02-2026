const STATUS_STYLES = {
  PENDING:        { bg: "#fef9c3", color: "#854d0e", label: "Pending" },
  PROCESSING:     { bg: "#dbeafe", color: "#1d4ed8", label: "Processing" },
  OCR_IN_PROGRESS:{ bg: "#dbeafe", color: "#1d4ed8", label: "OCR Running" },
  OCR_COMPLETE:   { bg: "#d1fae5", color: "#065f46", label: "OCR Done" },
  AI_IN_PROGRESS: { bg: "#ede9fe", color: "#5b21b6", label: "AI Analysing" },
  COMPLETE:       { bg: "#d1fae5", color: "#065f46", label: "Complete" },
  OCR_FAILED:     { bg: "#fee2e2", color: "#991b1b", label: "OCR Failed" },
  AI_FAILED:      { bg: "#fee2e2", color: "#991b1b", label: "AI Failed" },
};

export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || { bg: "#f3f4f6", color: "#374151", label: status };
  return (
    <span style={{
      backgroundColor: style.bg,
      color: style.color,
      padding: "2px 10px",
      borderRadius: "12px",
      fontSize: "0.75rem",
      fontWeight: 600,
    }}>
      {style.label}
    </span>
  );
}

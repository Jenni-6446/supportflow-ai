import { useState } from "react";
import type { DocumentationResponse, UpdatedDiagnosisResponse } from "./types";

interface DocumentationPanelProps {
  diagnosis: UpdatedDiagnosisResponse | null;
  documentation: DocumentationResponse | null;
  isGenerating: boolean;
  error: string | null;
  onGenerateDocumentation: () => void;
}

async function copyText(text: string): Promise<void> {
  if (!navigator.clipboard) {
    return;
  }
  await navigator.clipboard.writeText(text);
}

function NoteBlock({
  title,
  value,
  copied,
  onCopy
}: {
  title: string;
  value: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="note-card">
      <div className="note-header">
        <h3>{title}</h3>
        <button className="copy-button" type="button" onClick={onCopy}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="note-box">{value}</div>
    </div>
  );
}

export function DocumentationPanel({
  diagnosis,
  documentation,
  isGenerating,
  error,
  onGenerateDocumentation
}: DocumentationPanelProps) {
  const [copiedNote, setCopiedNote] = useState<string | null>(null);

  const handleCopy = async (key: string, value: string) => {
    await copyText(value);
    setCopiedNote(key);
    window.setTimeout(() => setCopiedNote(null), 1600);
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Notes for the Ticket</h2>
          <p className="panel-subtitle">Generate notes after diagnosis is updated.</p>
        </div>
      </div>
      <div className="panel-body">
        {error ? <div className="alert">{error}</div> : null}
        <div className="actions">
          <button
            type="button"
            className="button-primary"
            disabled={!diagnosis || isGenerating}
            onClick={onGenerateDocumentation}
          >
            {isGenerating ? "Generating..." : "Generate Notes"}
          </button>
        </div>
        {!documentation ? (
          <div className="empty-state">
            Update diagnosis first, then generate professional ticket notes.
          </div>
        ) : (
          <div className="note-grid">
            <NoteBlock
              title="Internal Note"
              value={documentation.internalNote}
              copied={copiedNote === "internal"}
              onCopy={() => handleCopy("internal", documentation.internalNote)}
            />
            <NoteBlock
              title="User Response Draft"
              value={documentation.userResponseDraft}
              copied={copiedNote === "user"}
              onCopy={() => handleCopy("user", documentation.userResponseDraft)}
            />
            <NoteBlock
              title="Resolution Note"
              value={documentation.resolutionNote}
              copied={copiedNote === "resolution"}
              onCopy={() => handleCopy("resolution", documentation.resolutionNote)}
            />
            <NoteBlock
              title="Escalation Note"
              value={documentation.escalationNote}
              copied={copiedNote === "escalation"}
              onCopy={() => handleCopy("escalation", documentation.escalationNote)}
            />
          </div>
        )}
      </div>
    </section>
  );
}

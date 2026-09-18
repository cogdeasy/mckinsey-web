import { useState } from 'react';

import { claimsApi, type DocumentView } from '../api/client';
import { formatDateTime, humanise } from '../lib/format';

interface DocumentListProps {
  claimReference: string;
  documents: DocumentView[];
}

export function DocumentList({ claimReference, documents }: DocumentListProps) {
  const [preview, setPreview] = useState<{ id: string; url: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function open(document: DocumentView) {
    setError(null);
    try {
      const ticket = await claimsApi.getDownloadUrl(claimReference, document.id);
      setPreview({ id: document.id, url: ticket.download_url });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The document could not be opened');
    }
  }

  if (documents.length === 0) {
    return <p className="empty">No evidence has been attached.</p>;
  }

  return (
    <div>
      <ul className="documents" aria-label="Claim documents">
        {documents.map((document) => (
          <li key={document.id}>
            <div>
              <p className="documents__name">{document.filename}</p>
              <p className="documents__meta">
                {humanise(document.kind)} - {Math.round(document.size_bytes / 1024)} kB -{' '}
                {formatDateTime(document.created_at)}
              </p>
            </div>
            <button type="button" onClick={() => void open(document)}>
              View
            </button>
          </li>
        ))}
      </ul>
      {error ? <p className="error">{error}</p> : null}
      {preview ? (
        <figure className="viewer">
          <figcaption>Secure preview link, expires shortly</figcaption>
          <a href={preview.url} rel="noreferrer noopener" target="_blank">
            {preview.url}
          </a>
        </figure>
      ) : null}
    </div>
  );
}

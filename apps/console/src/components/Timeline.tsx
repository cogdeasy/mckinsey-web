import type { TimelineEntry } from '../api/client';
import { formatDateTime, humanise } from '../lib/format';

export function Timeline({ entries }: { entries: TimelineEntry[] }) {
  if (entries.length === 0) {
    return <p className="empty">Nothing has happened on this claim yet.</p>;
  }
  return (
    <ol className="timeline" aria-label="Claim timeline">
      {entries.map((entry) => (
        <li key={`${entry.kind}-${entry.occurred_at}-${entry.summary}`}>
          <span className="timeline__kind">{humanise(entry.kind)}</span>
          <span className="timeline__summary">{entry.summary}</span>
          <span className="timeline__meta">
            {formatDateTime(entry.occurred_at)} by {entry.actor_id}
          </span>
        </li>
      ))}
    </ol>
  );
}

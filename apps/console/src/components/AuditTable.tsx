import type { AuditEventView } from '../api/client';
import { formatDateTime } from '../lib/format';

export function AuditTable({ events }: { events: AuditEventView[] }) {
  if (events.length === 0) {
    return <p className="empty">No audit events recorded.</p>;
  }
  return (
    <table className="table table--compact" aria-label="Audit trail">
      <thead>
        <tr>
          <th scope="col">Recorded</th>
          <th scope="col">Event</th>
          <th scope="col">Actor</th>
          <th scope="col">Correlation</th>
          <th scope="col">Digest</th>
        </tr>
      </thead>
      <tbody>
        {events.map((event) => (
          <tr key={event.id}>
            <td>{formatDateTime(event.created_at)}</td>
            <td>{event.event_type}</td>
            <td>{event.actor_id}</td>
            <td className="mono">{event.correlation_id}</td>
            <td className="mono">{event.payload_digest.slice(0, 12)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

import type { components } from '../api/schema';
import { formatDateTime } from '../lib/format';

export function SlaCell({ sla }: { sla: components['schemas']['SlaView'] }) {
  if (sla.awaiting_information) {
    return <span className="sla sla--paused">Paused, awaiting information</span>;
  }
  return (
    <span className={sla.breached ? 'sla sla--breached' : 'sla'}>
      {sla.breached ? 'Breached ' : 'Due '}
      {formatDateTime(sla.decision_due_at)}
    </span>
  );
}

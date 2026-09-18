import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { claimsApi, type QueueQuery } from '../api/client';
import { QueueTable } from '../components/QueueTable';

const STATUSES = [
  'REGISTERED',
  'TRIAGED',
  'IN_ASSESSMENT',
  'PENDING_APPROVAL',
  'APPROVED',
  'SETTLED',
] as const;

const SEGMENTS = ['FAST_TRACK', 'STANDARD', 'COMPLEX', 'SPECIAL_INVESTIGATION'] as const;

export function QueuePage() {
  const [filters, setFilters] = useState<QueueQuery>({ limit: 25 });

  const { data, isPending, error } = useQuery({
    queryKey: ['claims', filters],
    queryFn: () => claimsApi.listClaims(filters),
  });

  return (
    <section>
      <div className="page__heading">
        <h1>Claims queue</h1>
        <p className="page__lede">
          Work items are ordered by triage priority, then by how long they have been waiting.
        </p>
      </div>

      <form className="filters" aria-label="Queue filters">
        <label>
          Status
          <select
            value={filters.status ?? ''}
            onChange={(event) =>
              setFilters((current) => ({
                ...current,
                status: event.target.value ? (event.target.value as never) : undefined,
              }))
            }
          >
            <option value="">All</option>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </label>
        <label>
          Segment
          <select
            value={filters.segment ?? ''}
            onChange={(event) =>
              setFilters((current) => ({
                ...current,
                segment: event.target.value ? (event.target.value as never) : undefined,
              }))
            }
          >
            <option value="">All</option>
            {SEGMENTS.map((segment) => (
              <option key={segment} value={segment}>
                {segment}
              </option>
            ))}
          </select>
        </label>
        <label className="filters__checkbox">
          <input
            type="checkbox"
            checked={filters.breached === true}
            onChange={(event) =>
              setFilters((current) => ({
                ...current,
                breached: event.target.checked ? true : undefined,
              }))
            }
          />
          Breached only
        </label>
      </form>

      {isPending ? <p className="empty">Loading the queue.</p> : null}
      {error ? (
        <p className="error" role="alert">
          {error.message}
        </p>
      ) : null}
      {data ? <QueueTable claims={data.items} /> : null}
    </section>
  );
}

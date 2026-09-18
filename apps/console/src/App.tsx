import { NavLink, Navigate, Route, Routes } from 'react-router-dom';

import { ClaimPage } from './pages/ClaimPage';
import { QueuePage } from './pages/QueuePage';

export function App() {
  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <span className="app__mark">MA</span>
          <div>
            <p className="app__title">Meridian Assurance</p>
            <p className="app__subtitle">Claims operations console</p>
          </div>
        </div>
        <nav className="app__nav">
          <NavLink to="/queue">Queue</NavLink>
        </nav>
      </header>
      <main className="app__main">
        <Routes>
          <Route path="/" element={<Navigate to="/queue" replace />} />
          <Route path="/queue" element={<QueuePage />} />
          <Route path="/claims/:claimReference" element={<ClaimPage />} />
          <Route path="*" element={<p className="empty">That page does not exist.</p>} />
        </Routes>
      </main>
    </div>
  );
}

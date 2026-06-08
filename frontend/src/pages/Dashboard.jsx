import React, { useState, useEffect } from 'react';
import api from '../lib/api';

export default function Dashboard() {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    total: 0,
    inTransit: 0,
    deliveredToday: 0,
    delayed: 0
  });

  const fetchData = async () => {
    try {
      const data = await api.get('/shipments', { page: 1, limit: 100 });
      const list = data.shipments || [];
      setShipments(list);

      // Compute Stats
      const total = list.length;
      const inTransit = list.filter(s => s.status === 'IN_TRANSIT' || s.status === 'LOADED').length;
      
      // Check for delivery today
      const todayStr = new Date().toISOString().split('T')[0];
      const deliveredToday = list.filter(s => {
        if (s.status !== 'DELIVERED') return false;
        const deliveredDate = s.delivered_at ? s.delivered_at.split('T')[0] : '';
        return deliveredDate === todayStr || s.scheduled_date === todayStr; // fallback for seeded data
      }).length;
      
      const delayed = list.filter(s => s.status === 'DELAYED' || s.delay_alerted === true).length;

      setStats({ total, inTransit, deliveredToday, delayed });
      setLoading(false);
    } catch (error) {
      console.error("Failed to load shipments:", error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Auto-refresh every 30 seconds (Ticket 6.2)
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (isoString) => {
    if (!isoString) return 'N/A';
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
  };

  if (loading) {
    return <div style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-display)' }}>Loading Live Operations Panel...</div>;
  }

  return (
    <div>
      {/* Stat Cards */}
      <div className="stats-grid">
        <div className="card">
          <div className="stat-label">Total Shipments</div>
          <div className="stat-value">{stats.total}</div>
        </div>
        <div className="card">
          <div className="stat-label">In Transit</div>
          <div className="stat-value" style={{ color: 'var(--color-amber)' }}>{stats.inTransit}</div>
        </div>
        <div className="card">
          <div className="stat-label">Delivered Today</div>
          <div className="stat-value" style={{ color: 'var(--color-success)' }}>{stats.deliveredToday}</div>
        </div>
        <div className="card" style={{ borderLeft: stats.delayed > 0 ? '3px solid var(--color-danger)' : '1px solid var(--color-navy-light)' }}>
          <div className="stat-label">Delay Flags</div>
          <div className="stat-value" style={{ color: stats.delayed > 0 ? 'var(--color-danger)' : 'var(--color-text-primary)' }}>{stats.delayed}</div>
        </div>
      </div>

      {/* Shipments Table */}
      <div className="table-container">
        <div className="table-header-row">
          <div className="table-title">Live Shipments Board</div>
          <button className="btn-secondary" onClick={fetchData} style={{ padding: '6px 12px', fontSize: '11px' }}>
            🔄 Refresh
          </button>
        </div>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Trip ID</th>
                <th>Operator</th>
                <th>Route</th>
                <th>Cargo / Weight</th>
                <th>Truck Number</th>
                <th>Status</th>
                <th>E-Way Bill Draft</th>
                <th>Last Update</th>
              </tr>
            </thead>
            <tbody>
              {shipments.length === 0 ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', color: 'var(--color-text-secondary)', padding: '30px' }}>
                    No shipments active on the board.
                  </td>
                </tr>
              ) : (
                shipments.map((s) => (
                  <tr key={s.id}>
                    <td>{s.id.substring(0, 8).toUpperCase()}</td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{s.operators?.business_name || 'Individual Operator'}</div>
                      <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>{s.operators?.phone}</div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{s.origin} ➔ {s.destination}</div>
                      <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>Sched: {s.scheduled_date}</div>
                    </td>
                    <td>
                      <div>{s.cargo_type}</div>
                      <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>{s.weight_tons} Tons</div>
                    </td>
                    <td>
                      {s.trucks ? (
                        <>
                          <div style={{ fontWeight: 600 }}>{s.trucks.truck_number}</div>
                          <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>{s.trucks.driver_name}</div>
                        </>
                      ) : (
                        <span style={{ color: 'var(--color-text-muted)' }}>Not Assigned</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge badge-${s.status.toLowerCase()}`}>
                        {s.status}
                      </span>
                    </td>
                    <td>
                      {s.ewb_pdf_url ? (
                        <a href={s.ewb_pdf_url} target="_blank" rel="noopener noreferrer" className="pdf-link">
                          📄 Download EWB
                        </a>
                      ) : (
                        <span style={{ color: 'var(--color-text-muted)' }}>N/A</span>
                      )}
                    </td>
                    <td>{formatTime(s.updated_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

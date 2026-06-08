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
        return deliveredDate === todayStr || s.scheduled_date === todayStr;
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
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (isoString) => {
    if (!isoString) return 'N/A';
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
  };

  const getStatusClass = (status) => {
    switch (status.toUpperCase()) {
      case 'DELIVERED': return 'badge-pill-success';
      case 'CONFIRMED': return 'badge-pill-info';
      case 'LOADED':
      case 'IN_TRANSIT': return 'badge-pill-amber';
      case 'DELAYED': return 'badge-pill-danger';
      default: return 'badge-pill-pending';
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
        <header className="app-header">
          <h2 className="page-title">Live Operations Control</h2>
          <div className="header-actions">
            <div className="sandbox-badge">
              <svg className="sandbox-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
              Sandbox Mode
            </div>
          </div>
        </header>
        <div className="content-body">
          <div style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-display)', fontWeight: 600 }}>Loading control room board...</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Consistent Header */}
      <header className="app-header">
        <h2 className="page-title">Live Operations Control</h2>
        <div className="header-actions">
          <div className="sandbox-badge">
            <svg className="sandbox-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
            Sandbox Mode
          </div>
        </div>
      </header>

      {/* Main Content Body */}
      <div className="content-body">
        {/* Statistics Grid */}
        <div className="stats-grid">
          <div className="card-stat">
            <div className="stat-info">
              <span className="stat-title">Total Shipments</span>
              <span className="stat-num">{stats.total}</span>
            </div>
            <div className="stat-icon-container" style={{ background: 'rgba(37, 99, 235, 0.08)' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 21h20M20 17H4l-2-6h20l-2 6zM12 11V3l4 3-4 2" />
              </svg>
            </div>
          </div>
          
          <div className="card-stat">
            <div className="stat-info">
              <span className="stat-title">In Transit</span>
              <span className="stat-num">{stats.inTransit}</span>
            </div>
            <div className="stat-icon-container" style={{ background: 'rgba(217, 119, 6, 0.08)' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="1" y="3" width="15" height="13" />
                <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
                <circle cx="5.5" cy="18.5" r="2.5" />
                <circle cx="18.5" cy="18.5" r="2.5" />
              </svg>
            </div>
          </div>

          <div className="card-stat">
            <div className="stat-info">
              <span className="stat-title">Delivered Today</span>
              <span className="stat-num">{stats.deliveredToday}</span>
            </div>
            <div className="stat-icon-container" style={{ background: 'rgba(21, 128, 61, 0.08)' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#15803d" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>
          </div>

          <div className="card-stat">
            <div className="stat-info">
              <span className="stat-title">Delay Flags</span>
              <span className="stat-num">{stats.delayed}</span>
            </div>
            <div className="stat-icon-container" style={{ background: 'rgba(185, 28, 28, 0.08)' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#b91c1c" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </div>
          </div>
        </div>

        {/* Live Shipments Board */}
        <div className="table-panel">
          <div className="table-panel-header">
            <h3 className="table-panel-title">Live Shipments Board</h3>
            <button className="btn-refresh" onClick={fetchData}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
              </svg>
              Refresh
            </button>
          </div>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Trip ID</th>
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
                    <td colSpan="7" style={{ textAlign: 'center', color: 'var(--color-text-secondary)', padding: '40px' }}>
                      No active shipments found.
                    </td>
                  </tr>
                ) : (
                  shipments.map((s) => (
                    <tr key={s.id}>
                      <td className="trip-id-text">
                        SHP_{s.id.substring(0, 4).toUpperCase()}
                      </td>
                      <td>
                        <div style={{ fontWeight: 700 }}>{s.origin} ➔ {s.destination}</div>
                      </td>
                      <td>
                        <div>{s.cargo_type} / {s.weight_tons} Tons</div>
                      </td>
                      <td>
                        {s.trucks ? (
                          <div style={{ fontWeight: 600 }}>{s.trucks.truck_number}</div>
                        ) : (
                          <span style={{ color: 'var(--color-text-muted)' }}>Not Assigned</span>
                        )}
                      </td>
                      <td>
                        <span className={`badge-pill ${getStatusClass(s.status)}`}>
                          {s.status}
                        </span>
                      </td>
                      <td>
                        {s.ewb_pdf_url ? (
                          <a href={s.ewb_pdf_url} target="_blank" rel="noopener noreferrer" className="ewb-link">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
                            </svg>
                            Download EWB
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
    </div>
  );
}

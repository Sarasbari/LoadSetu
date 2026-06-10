import { useState, useEffect, useCallback } from 'react';
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

  // Timeline and detail states
  const [selectedShipment, setSelectedShipment] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState(null);

  // Simulation states
  const [simulating, setSimulating] = useState(false);
  const [simulationStatus, setSimulationStatus] = useState('');

  // Dispute pack generation state
  const [generatingDispute, setGeneratingDispute] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const data = await api.get('/shipments', { page: 1, limit: 100 });
      const list = data.shipments || [];
      setShipments(list);

      // Refresh drawer info if open
      if (selectedShipment) {
        const updated = list.find(s => s.id === selectedShipment.id);
        if (updated) {
          setSelectedShipment(updated);
        }
      }

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
  }, [selectedShipment]);

  useEffect(() => {
    Promise.resolve().then(() => {
      fetchData();
    });
    const interval = setInterval(fetchData, 10000); // Poll every 10 seconds for real-time sandbox feel
    return () => clearInterval(interval);
  }, [fetchData]);

  const fetchTimeline = useCallback(async (shipmentId) => {
    setTimelineLoading(true);
    setTimelineError(null);
    try {
      const data = await api.get(`/shipments/${shipmentId}/timeline`);
      setTimeline(data.timeline || []);
    } catch (error) {
      console.error("Failed to load timeline:", error);
      setTimelineError("Failed to load timeline.");
    } finally {
      setTimelineLoading(false);
    }
  }, []);

  const handleShipmentClick = (shipment) => {
    setSelectedShipment(shipment);
    setTimeline([]);
    fetchTimeline(shipment.id);
  };

  const handleDownloadDisputePack = async (shipmentId) => {
    setGeneratingDispute(true);
    try {
      const res = await api.post(`/shipments/${shipmentId}/dispute-pack`);
      if (res.pdf_url) {
        window.open(res.pdf_url, '_blank');
      } else {
        alert("Failed to generate dispute packet URL.");
      }
    } catch (error) {
      console.error("Failed to generate dispute pack:", error);
      alert("Failed to generate dispute pack: " + (error.message || error));
    } finally {
      setGeneratingDispute(false);
    }
  };

  const handleSimulate = async (endpoint, statusText) => {
    setSimulating(true);
    setSimulationStatus(statusText);
    try {
      const res = await api.post(endpoint);
      setSimulationStatus(`Success: ${res.message || 'Operation succeeded'}`);
      await fetchData(); // Refresh table
      
      // If details drawer is open, refresh timeline
      if (selectedShipment) {
        // Use timeout to allow database update processing
        setTimeout(() => {
          fetchTimeline(selectedShipment.id);
        }, 500);
      }
      
      setTimeout(() => setSimulationStatus(''), 4000);
    } catch (error) {
      setSimulationStatus(`Error: ${error.message || 'Simulation failed'}`);
      setTimeout(() => setSimulationStatus(''), 5000);
    } finally {
      setSimulating(false);
    }
  };

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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', position: 'relative' }}>
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
        {/* Compact Guided Simulator Section */}
        <div className="table-panel" style={{ marginBottom: '24px', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 className="table-panel-title" style={{ margin: 0 }}>Step-by-Step Guided Simulator</h3>
            {simulationStatus && (
              <span style={{ 
                fontSize: '13px', 
                color: simulationStatus.startsWith('Error') ? 'var(--badge-danger-text)' : 'var(--color-saffron)', 
                fontWeight: 700, 
                fontFamily: 'var(--font-display)' 
              }}>
                {simulationStatus}
              </span>
            )}
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '12px' }}>
              <div className="sim-step-card" style={{ border: '1px solid var(--color-border)', borderRadius: '8px', padding: '12px', background: '#f8fafc', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-text-secondary)' }}>STEP 1</div>
                <div style={{ fontSize: '12px', fontWeight: 600 }}>Intake Request</div>
                <button 
                  id="btn-sim-booking" 
                  className="btn-refresh" 
                  onClick={() => handleSimulate('/demo/simulate-booking', 'Simulating incoming operator booking...')} 
                  disabled={simulating}
                  style={{ width: '100%', fontSize: '11px', padding: '6px', fontWeight: 700 }}
                >
                  Book Load
                </button>
              </div>
              
              <div className="sim-step-card" style={{ border: '1px solid var(--color-border)', borderRadius: '8px', padding: '12px', background: '#f8fafc', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-text-secondary)' }}>STEP 2</div>
                <div style={{ fontSize: '12px', fontWeight: 600 }}>Confirm Truck</div>
                <button 
                  id="btn-sim-confirm" 
                  className="btn-refresh" 
                  onClick={() => handleSimulate('/demo/simulate-confirm', 'Simulating truck selection confirmation...')} 
                  disabled={simulating}
                  style={{ width: '100%', fontSize: '11px', padding: '6px', fontWeight: 700 }}
                >
                  Confirm Choice
                </button>
              </div>

              <div className="sim-step-card" style={{ border: '1px solid var(--color-border)', borderRadius: '8px', padding: '12px', background: '#f8fafc', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-text-secondary)' }}>STEP 3</div>
                <div style={{ fontSize: '12px', fontWeight: 600 }}>Load Cargo</div>
                <button 
                  id="btn-sim-loaded" 
                  className="btn-refresh" 
                  onClick={() => handleSimulate('/demo/simulate-loaded', 'Simulating driver loaded status...')} 
                  disabled={simulating}
                  style={{ width: '100%', fontSize: '11px', padding: '6px', fontWeight: 700 }}
                >
                  Set Loaded
                </button>
              </div>

              <div className="sim-step-card" style={{ border: '1px solid var(--color-border)', borderRadius: '8px', padding: '12px', background: '#f8fafc', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-text-secondary)' }}>STEP 4</div>
                <div style={{ fontSize: '12px', fontWeight: 600 }}>Start Transit</div>
                <button 
                  id="btn-sim-transit" 
                  className="btn-refresh" 
                  onClick={() => handleSimulate('/demo/simulate-transit', 'Simulating transit status...')} 
                  disabled={simulating}
                  style={{ width: '100%', fontSize: '11px', padding: '6px', fontWeight: 700 }}
                >
                  Depart Origin
                </button>
              </div>

              <div className="sim-step-card" style={{ border: '1px solid var(--color-border)', borderRadius: '8px', padding: '12px', background: '#f8fafc', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-text-secondary)' }}>STEP 5 (Risk)</div>
                <div style={{ fontSize: '12px', fontWeight: 600 }}>Simulate Delay</div>
                <button 
                  id="btn-trigger-delay" 
                  className="btn-refresh" 
                  onClick={() => handleSimulate('/demo/trigger-delay', 'Simulating pickup deadline delay...')} 
                  disabled={simulating}
                  style={{ width: '100%', fontSize: '11px', padding: '6px', fontWeight: 700, color: 'var(--badge-danger-text)' }}
                >
                  Flag Delay
                </button>
              </div>

              <div className="sim-step-card" style={{ border: '1px solid var(--color-border)', borderRadius: '8px', padding: '12px', background: '#f8fafc', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--color-text-secondary)' }}>STEP 6</div>
                <div style={{ fontSize: '12px', fontWeight: 600 }}>Deliver & POD</div>
                <button 
                  id="btn-sim-delivered" 
                  className="btn-refresh" 
                  onClick={() => handleSimulate('/demo/simulate-delivered', 'Simulating delivery & POD receipt...')} 
                  disabled={simulating}
                  style={{ width: '100%', fontSize: '11px', padding: '6px', fontWeight: 700 }}
                >
                  Complete Trip
                </button>
              </div>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px dashed var(--color-border)', paddingTop: '12px' }}>
              <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                Reset database and seed demo data:
              </span>
              <button 
                id="btn-seed-demo" 
                className="btn-refresh" 
                onClick={() => handleSimulate('/demo/seed', 'Resetting and seeding demo...')} 
                disabled={simulating}
                style={{ fontSize: '12px', fontWeight: 700 }}
              >
                Reset & Seed Database
              </button>
            </div>
          </div>
        </div>

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
                  <th>Delay Risk</th>
                  <th>E-Way Bill Draft</th>
                  <th>Last Update</th>
                </tr>
              </thead>
              <tbody>
                {shipments.length === 0 ? (
                  <tr>
                    <td colSpan="8" style={{ textAlign: 'center', color: 'var(--color-text-secondary)', padding: '40px' }}>
                      No active shipments found.
                    </td>
                  </tr>
                ) : (
                  shipments.map((s) => (
                    <tr 
                      key={s.id} 
                      onClick={() => handleShipmentClick(s)} 
                      style={{ cursor: 'pointer' }}
                      id={`shipment-row-${s.id.substring(0, 4)}`}
                    >
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
                        {s.trucks || s.truck ? (
                          <div style={{ fontWeight: 600 }}>{(s.trucks || s.truck).truck_number}</div>
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
                        <span className={`badge-pill ${
                          (s.delay_risk_level || 'Low').toLowerCase() === 'critical' ? 'badge-pill-danger' :
                          (s.delay_risk_level || 'Low').toLowerCase() === 'high' ? 'badge-pill-amber' :
                          (s.delay_risk_level || 'Low').toLowerCase() === 'medium' ? 'badge-pill-info' :
                          'badge-pill-success'
                        }`}>
                          {s.delay_risk_level || 'Low'} ({s.delay_risk_score || 0}%)
                        </span>
                      </td>
                      <td>
                        {s.ewb_pdf_url ? (
                          <a 
                            href={s.ewb_pdf_url} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            className="ewb-link"
                            onClick={(e) => e.stopPropagation()} // Stop row click
                          >
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

      {/* Slide-over Right Side Panel */}
      {selectedShipment && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            backgroundColor: 'rgba(15, 23, 42, 0.4)',
            zIndex: 100,
            display: 'flex',
            justifyContent: 'flex-end',
            transition: 'opacity 0.3s ease'
          }} 
          onClick={() => setSelectedShipment(null)}
          id="shipment-detail-drawer"
        >
          <div 
            style={{
              width: '480px',
              height: '100%',
              backgroundColor: '#ffffff',
              borderLeft: '1px solid var(--color-border)',
              boxShadow: '-4px 0 24px rgba(0, 0, 0, 0.1)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden'
            }} 
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div style={{
              padding: '24px',
              borderBottom: '1px solid var(--color-border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <div>
                <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Shipment Details</span>
                <h3 className="page-title" style={{ marginTop: '4px' }}>SHP_{selectedShipment.id.substring(0, 4).toUpperCase()}</h3>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span className={`badge-pill ${getStatusClass(selectedShipment.status)}`}>
                  {selectedShipment.status}
                </span>
                <button 
                  onClick={() => setSelectedShipment(null)} 
                  style={{
                    background: 'none',
                    border: 'none',
                    fontSize: '24px',
                    color: 'var(--color-text-muted)',
                    cursor: 'pointer',
                    lineHeight: 1
                  }}
                  id="btn-close-drawer"
                >
                  &times;
                </button>
              </div>
            </div>

            {/* Drawer Content Area */}
            <div style={{ padding: '24px', overflowY: 'auto', flexGrow: 1, display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Route & Cargo */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', background: '#f8fafc', padding: '16px', borderRadius: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                  <span style={{ color: 'var(--color-text-secondary)', fontWeight: 600 }}>Route</span>
                  <span style={{ fontWeight: 700 }}>{selectedShipment.origin} ➔ {selectedShipment.destination}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                  <span style={{ color: 'var(--color-text-secondary)', fontWeight: 600 }}>Cargo</span>
                  <span style={{ fontWeight: 600 }}>{selectedShipment.cargo_type} ({selectedShipment.weight_tons} Tons)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                  <span style={{ color: 'var(--color-text-secondary)', fontWeight: 600 }}>Date</span>
                  <span style={{ fontWeight: 600 }}>{selectedShipment.scheduled_date || 'N/A'}</span>
                </div>
              </div>

              {/* Delay Risk Badge */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f8fafc', padding: '12px 16px', borderRadius: '8px', fontSize: '13px' }}>
                <span style={{ color: 'var(--color-text-secondary)', fontWeight: 600 }}>Delay Risk Assessment</span>
                <span className={`badge-pill ${
                  (selectedShipment.delay_risk_level || 'Low').toLowerCase() === 'critical' ? 'badge-pill-danger' :
                  (selectedShipment.delay_risk_level || 'Low').toLowerCase() === 'high' ? 'badge-pill-amber' :
                  (selectedShipment.delay_risk_level || 'Low').toLowerCase() === 'medium' ? 'badge-pill-info' :
                  'badge-pill-success'
                }`} style={{ fontWeight: 700 }}>
                  {selectedShipment.delay_risk_level || 'Low'} ({selectedShipment.delay_risk_score || 0}%)
                </span>
              </div>

              {/* AI Confidence & Extraction Panel */}
              <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '16px' }} id="ai-confidence-panel">
                <h4 style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-secondary)', marginBottom: '8px', fontWeight: 700 }}>AI Confidence & Extraction Panel</h4>
                <div style={{ 
                  background: selectedShipment.ai_confidence === 'HIGH' ? '#f0fdf4' : selectedShipment.ai_confidence === 'MEDIUM' ? '#fef3c7' : '#fef2f2',
                  border: `1px solid ${selectedShipment.ai_confidence === 'HIGH' ? '#bbf7d0' : selectedShipment.ai_confidence === 'MEDIUM' ? '#fde68a' : '#fca5a5'}`,
                  padding: '12px',
                  borderRadius: '8px',
                  fontSize: '13px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong>Confidence Level:</strong>
                    <span style={{ 
                      fontWeight: 'bold', 
                      color: selectedShipment.ai_confidence === 'HIGH' ? '#16a34a' : selectedShipment.ai_confidence === 'MEDIUM' ? '#d97706' : '#dc2626'
                    }}>
                      {selectedShipment.ai_confidence || 'LOW'}
                    </span>
                  </div>
                  {selectedShipment.ai_metadata && (
                    <>
                      {selectedShipment.ai_metadata.extracted_fields && (
                        <div>
                          <strong>Extracted Details:</strong>
                          <ul style={{ margin: '4px 0', paddingLeft: '20px', listStyleType: 'disc' }}>
                            {Object.entries(selectedShipment.ai_metadata.extracted_fields).map(([k, v]) => (
                              v !== null && <li key={k}><strong>{k.replace('_', ' ')}:</strong> {String(v)}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {selectedShipment.ai_metadata.missing_fields && selectedShipment.ai_metadata.missing_fields.length > 0 && (
                        <div style={{ color: '#dc2626' }}>
                          <strong>Missing Fields:</strong> {selectedShipment.ai_metadata.missing_fields.join(', ')}
                        </div>
                      )}
                      {selectedShipment.ai_metadata.match_reason && (
                        <div style={{ fontStyle: 'italic', background: 'rgba(255,255,255,0.6)', padding: '6px', borderRadius: '4px', marginTop: '4px' }}>
                          <strong>Match Reason:</strong> {selectedShipment.ai_metadata.match_reason}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Operator */}
              <div>
                <h4 style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-secondary)', marginBottom: '8px', fontWeight: 700 }}>Operator (Sender)</h4>
                {selectedShipment.operators || selectedShipment.operator ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px' }}>
                    <div><strong>Business:</strong> {(selectedShipment.operators || selectedShipment.operator).business_name || 'N/A'}</div>
                    <div><strong>Phone:</strong> {(selectedShipment.operators || selectedShipment.operator).phone}</div>
                    <div><strong>Location:</strong> {(selectedShipment.operators || selectedShipment.operator).city || 'N/A'}</div>
                  </div>
                ) : (
                  <div style={{ color: 'var(--color-text-muted)' }}>No Operator Details</div>
                )}
              </div>

              {/* Driver & Truck */}
              <div>
                <h4 style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-secondary)', marginBottom: '8px', fontWeight: 700 }}>Truck & Driver</h4>
                {selectedShipment.trucks || selectedShipment.truck ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '13px' }}>
                    <div><strong>Truck Number:</strong> {(selectedShipment.trucks || selectedShipment.truck).truck_number}</div>
                    <div><strong>Driver:</strong> {(selectedShipment.trucks || selectedShipment.truck).driver_name} ({(selectedShipment.trucks || selectedShipment.truck).driver_phone})</div>
                    <div><strong>Type / Capacity:</strong> {(selectedShipment.trucks || selectedShipment.truck).truck_type} / {(selectedShipment.trucks || selectedShipment.truck).capacity_tons} Tons</div>
                  </div>
                ) : (
                  <div style={{ color: 'var(--color-text-muted)' }}>No Truck Details</div>
                )}
              </div>

              {/* E-Way Bill Download Link */}
              {selectedShipment.ewb_pdf_url && (
                <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '16px' }}>
                  <h4 style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-secondary)', marginBottom: '8px', fontWeight: 700 }}>E-Way Bill</h4>
                  <a href={selectedShipment.ewb_pdf_url} target="_blank" rel="noopener noreferrer" className="ewb-link" style={{ fontSize: '13px' }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
                    </svg>
                    Download Generated EWB Draft PDF
                  </a>
                </div>
              )}

              {/* Proof of Delivery (POD) */}
              <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '16px' }} id="shipment-pod-section">
                <h4 style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-secondary)', marginBottom: '8px', fontWeight: 700 }}>Proof of Delivery (POD)</h4>
                {selectedShipment.pod_status === 'RECEIVED' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px', background: '#f0fdf4', padding: '12px', borderRadius: '8px', border: '1px solid #bbf7d0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#15803d', fontWeight: 700 }}>
                      <span>✅ Proof of Delivery Received</span>
                    </div>
                    {selectedShipment.pod_received_at && (
                      <div style={{ color: 'var(--color-text-secondary)', fontSize: '11px' }}>
                        <strong>Received:</strong> {new Date(selectedShipment.pod_received_at).toLocaleString()}
                      </div>
                    )}
                    {selectedShipment.pod_note && (
                      <div>
                        <strong>Driver Note:</strong> "{selectedShipment.pod_note}"
                      </div>
                    )}
                    {selectedShipment.pod_media_url && (
                      <div style={{ marginTop: '8px' }}>
                        <strong>Proof Document:</strong>
                        <div style={{ marginTop: '4px' }}>
                          <a href={selectedShipment.pod_media_url} target="_blank" rel="noopener noreferrer" style={{ display: 'block' }}>
                            <img 
                              src={selectedShipment.pod_media_url.includes('dummy.supabase.co') ? 'https://images.unsplash.com/photo-1554415707-6e8cfc93fe23?w=300&auto=format&fit=crop&q=60' : selectedShipment.pod_media_url} 
                              alt="Proof of Delivery Receipt" 
                              style={{ maxWidth: '100%', maxHeight: '180px', borderRadius: '6px', border: '1px solid var(--color-border)', display: 'block', objectFit: 'cover' }} 
                            />
                          </a>
                          <a href={selectedShipment.pod_media_url} target="_blank" rel="noopener noreferrer" className="ewb-link" style={{ marginTop: '6px', fontSize: '12px' }}>View Full Image</a>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ color: 'var(--color-text-muted)', fontSize: '13px' }}>
                    Pending delivery confirmation from driver.
                  </div>
                )}
              </div>

              {/* Dispute Resolution */}
              {selectedShipment.status === 'DELIVERED' && (
                <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '16px' }} id="shipment-dispute-section">
                  <h4 style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-secondary)', marginBottom: '8px', fontWeight: 700 }}>Dispute Resolution</h4>
                  <button 
                    onClick={() => handleDownloadDisputePack(selectedShipment.id)} 
                    className="btn-refresh" 
                    disabled={generatingDispute}
                    style={{ fontSize: '13px', width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
                    </svg>
                    {generatingDispute ? 'Generating Dispute Pack...' : 'Download Verified Dispute Pack PDF'}
                  </button>
                </div>
              )}

              {/* Trust Timeline */}
              <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '16px' }} id="shipment-timeline-section">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h4 style={{ fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-secondary)', fontWeight: 700 }}>Trust Timeline / Audit Trail</h4>
                  <button className="btn-refresh" onClick={() => fetchTimeline(selectedShipment.id)} style={{ padding: '4px 8px', fontSize: '10px' }}>
                    Refresh
                  </button>
                </div>

                {/* Visual Trip Stages Stepper */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid var(--color-border)', marginBottom: '16px' }}>
                  {['BOOKED', 'CONFIRMED', 'LOADED', 'IN_TRANSIT', 'DELIVERED'].map((stage, idx) => {
                    const currentStatus = selectedShipment.status;
                    const stagesOrder = ['PENDING', 'CONFIRMED', 'LOADED', 'IN_TRANSIT', 'DELIVERED'];
                    const activeIdx = stagesOrder.indexOf(currentStatus);
                    const isCompleted = stagesOrder.indexOf(stage) <= activeIdx;
                    
                    return (
                      <div key={stage} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px', flex: 1, position: 'relative' }}>
                        {/* Connector Line */}
                        {idx < 4 && (
                          <div style={{ 
                            position: 'absolute', 
                            top: '8px', 
                            left: '50%', 
                            right: '-50%', 
                            height: '2px', 
                            backgroundColor: stagesOrder.indexOf(stagesOrder[idx+1]) <= activeIdx ? 'var(--color-saffron)' : 'var(--color-border)',
                            zIndex: 0
                          }} />
                        )}
                        <div style={{ 
                          width: '18px', 
                          height: '18px', 
                          borderRadius: '50%', 
                          backgroundColor: isCompleted ? 'var(--color-saffron)' : '#ffffff', 
                          border: `2px solid ${isCompleted ? 'var(--color-saffron)' : 'var(--color-border)'}`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '9px',
                          color: isCompleted ? '#ffffff' : 'var(--color-text-muted)',
                          fontWeight: 'bold',
                          zIndex: 1
                        }}>
                          {isCompleted ? '✓' : idx + 1}
                        </div>
                        <span style={{ fontSize: '9px', fontWeight: 600, color: isCompleted ? 'var(--color-text-primary)' : 'var(--color-text-muted)', textAlign: 'center' }}>
                          {stage}
                        </span>
                      </div>
                    );
                  })}
                </div>
                
                {timelineLoading ? (
                  <div style={{ color: 'var(--color-text-secondary)', fontSize: '13px' }}>Loading timeline...</div>
                ) : timelineError ? (
                  <div style={{ color: 'var(--badge-danger-text)', fontSize: '13px' }}>{timelineError}</div>
                ) : timeline.length === 0 ? (
                  <div style={{ color: 'var(--color-text-muted)', fontSize: '13px' }}>No timeline events found.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', position: 'relative', paddingLeft: '20px' }}>
                    {/* Vertical connector line */}
                    <div style={{
                      position: 'absolute',
                      top: '6px',
                      bottom: '6px',
                      left: '6px',
                      width: '2px',
                      backgroundColor: 'var(--color-border)',
                      zIndex: 0
                    }}></div>
                    
                    {timeline.map((event) => {
                      const isDelay = event.event_type === 'delay_alert_triggered';
                      const isConfirmed = event.event_type === 'shipment_confirmed' || event.event_type === 'shipment_confirmed_manual';
                      const isPod = event.event_type === 'proof_of_delivery_received';
                      const isDelivered = event.event_type === 'shipment_delivered';
                      const isOnboarded = event.event_type === 'operator_onboarded';
                      
                      let markerBg = 'var(--color-border)';
                      if (isDelay) markerBg = 'var(--badge-danger-text)';
                      else if (isConfirmed || isPod || isDelivered || isOnboarded) markerBg = 'var(--badge-success-text)';
                      else if (event.event_type.startsWith('ai_') || event.event_type.startsWith('booking_')) markerBg = 'var(--color-saffron)';
                      
                      return (
                        <div key={event.id} style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }} className="timeline-event-item">
                          {/* Circle marker */}
                          <div style={{
                            position: 'absolute',
                            left: '-20px',
                            top: '4px',
                            width: '12px',
                            height: '12px',
                            borderRadius: '50%',
                            backgroundColor: markerBg,
                            border: '2px solid #ffffff',
                            boxShadow: '0 0 0 2px rgba(0, 0, 0, 0.05)'
                          }}></div>
                          
                          <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                            {event.title}
                          </div>
                          {event.description && (
                            <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', lineHeight: 1.3 }}>
                              {event.description}
                            </div>
                          )}
                          <div style={{ fontSize: '10px', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
                            {new Date(event.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} | {new Date(event.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import api from '../lib/api';

export default function Trucks() {
  const [trucks, setTrucks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showAvailableOnly, setShowAvailableOnly] = useState(false);
  
  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    driver_name: '',
    driver_phone: '',
    truck_number: '',
    truck_type: 'open',
    capacity_tons: '',
    home_city: '',
    notes: ''
  });
  const [formError, setFormError] = useState('');

  const fetchTrucks = async () => {
    try {
      const data = await api.get('/trucks', { page: 1, limit: 100 });
      setTrucks(data.trucks || []);
      setLoading(false);
    } catch (error) {
      console.error("Failed to load trucks:", error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrucks();
  }, []);

  const handleToggleAvailability = async (truckId, currentStatus, currentCity) => {
    try {
      const updatedTruck = await api.put(`/trucks/${truckId}/availability`, {
        is_available: !currentStatus,
        current_city: currentCity
      });
      // Update local state
      setTrucks(prev => prev.map(t => t.id === truckId ? { ...t, is_available: updatedTruck.truck.is_available } : t));
    } catch (error) {
      console.error("Failed to toggle availability:", error);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'capacity_tons' ? parseFloat(value) || '' : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    
    // Validations
    if (!formData.driver_name || !formData.driver_phone || !formData.truck_number || !formData.capacity_tons || !formData.home_city) {
      setFormError('All fields marked * are required');
      return;
    }
    
    // Indian truck format validation
    const truckNoRegex = /^[A-Z]{2}-\d{2}-[A-Z]{1,2}-\d{4}$/;
    if (!truckNoRegex.test(formData.truck_number)) {
      setFormError('Truck number must follow valid Indian format, e.g. MH-12-AB-1234');
      return;
    }
    
    try {
      await api.post('/trucks', formData);
      setIsModalOpen(false);
      // Reset form
      setFormData({
        driver_name: '',
        driver_phone: '',
        truck_number: '',
        truck_type: 'open',
        capacity_tons: '',
        home_city: '',
        notes: ''
      });
      fetchTrucks();
    } catch (error) {
      setFormError('Failed to add truck. Check console or verify inputs.');
    }
  };

  // Filter trucks based on search and availability filter
  const filteredTrucks = trucks.filter(t => {
    const matchesSearch = 
      t.truck_number.toLowerCase().includes(search.toLowerCase()) ||
      t.driver_name.toLowerCase().includes(search.toLowerCase()) ||
      t.home_city.toLowerCase().includes(search.toLowerCase()) ||
      t.current_city.toLowerCase().includes(search.toLowerCase());
      
    const matchesAvailability = showAvailableOnly ? t.is_available : true;
    
    return matchesSearch && matchesAvailability;
  });

  if (loading) {
    return <div style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-display)' }}>Loading Truck Registry...</div>;
  }

  return (
    <div>
      {/* Search & Actions Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '20px', marginBottom: '24px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '16px', flexGrow: 1, maxWidth: '600px' }}>
          <input
            type="text"
            className="input"
            placeholder="Search by vehicle number, driver, or city..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '12px', whiteSpace: 'nowrap' }}>
            <input
              type="checkbox"
              checked={showAvailableOnly}
              onChange={(e) => setShowAvailableOnly(e.target.checked)}
              style={{ accentColor: 'var(--color-saffron)' }}
            />
            Show Available Only
          </label>
        </div>
        
        <button className="btn-primary" onClick={() => setIsModalOpen(true)}>
          ➕ Add Truck
        </button>
      </div>

      {/* Grid of Truck Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px' }}>
        {filteredTrucks.length === 0 ? (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px', color: 'var(--color-text-secondary)' }}>
            No trucks match your filters.
          </div>
        ) : (
          filteredTrucks.map(t => (
            <div className="card" key={t.id} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--color-navy-light)', paddingBottom: '8px' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: '15px' }}>{t.truck_number}</span>
                <span className={`badge ${t.is_available ? 'badge-confirmed' : 'badge-pending'}`}>
                  {t.is_available ? 'Available' : 'On Trip'}
                </span>
              </div>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '13px' }}>
                <div><span style={{ color: 'var(--color-text-secondary)' }}>Driver:</span> {t.driver_name}</div>
                <div><span style={{ color: 'var(--color-text-secondary)' }}>Phone:</span> <span style={{ fontFamily: 'var(--font-mono)' }}>{t.driver_phone}</span></div>
                <div><span style={{ color: 'var(--color-text-secondary)' }}>Type / Cap:</span> {t.truck_type.toUpperCase()} / {t.capacity_tons} Tons</div>
                <div><span style={{ color: 'var(--color-text-secondary)' }}>Home / Current:</span> {t.home_city} / {t.current_city}</div>
                {t.notes && <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '4px', fontStyle: 'italic' }}>Note: {t.notes}</div>}
              </div>
              
              <div style={{ marginTop: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>Toggle Availability:</span>
                <input
                  type="checkbox"
                  checked={t.is_available}
                  onChange={() => handleToggleAvailability(t.id, t.is_available, t.current_city)}
                  style={{ 
                    cursor: 'pointer',
                    width: '16px',
                    height: '16px',
                    accentColor: 'var(--color-saffron)'
                  }}
                />
              </div>
            </div>
          ))
        )}
      </div>

      {/* Add Truck Modal */}
      {isModalOpen && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3 className="modal-title">Register New Truck</h3>
              <button 
                onClick={() => setIsModalOpen(false)}
                style={{ background: 'none', border: 'none', color: 'var(--color-text-secondary)', cursor: 'pointer', fontSize: '18px' }}
              >
                ✕
              </button>
            </div>
            
            <form onSubmit={handleSubmit}>
              {formError && (
                <div style={{ color: 'var(--color-danger)', fontSize: '12px', marginBottom: '16px', background: 'rgba(231,76,60,0.1)', padding: '8px', borderRadius: '4px' }}>
                  ⚠️ {formError}
                </div>
              )}
              
              <div className="form-group">
                <label className="form-label">Driver Name *</label>
                <input
                  type="text"
                  name="driver_name"
                  className="input"
                  placeholder="e.g. Ramesh Kumar"
                  value={formData.driver_name}
                  onChange={handleInputChange}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Driver Phone *</label>
                <input
                  type="text"
                  name="driver_phone"
                  className="input"
                  placeholder="e.g. +919876543210"
                  value={formData.driver_phone}
                  onChange={handleInputChange}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Truck Number (Indian Format) *</label>
                <input
                  type="text"
                  name="truck_number"
                  className="input"
                  placeholder="e.g. MH-12-AB-1234"
                  value={formData.truck_number}
                  onChange={handleInputChange}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Truck Type *</label>
                <select
                  name="truck_type"
                  className="input"
                  style={{ background: 'var(--color-navy)', color: 'var(--color-text-primary)' }}
                  value={formData.truck_type}
                  onChange={handleInputChange}
                  required
                >
                  <option value="open">Open Body</option>
                  <option value="closed">Closed Container</option>
                  <option value="refrigerated">Refrigerated</option>
                  <option value="flatbed">Flatbed</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Capacity (Tons) *</label>
                <input
                  type="number"
                  step="0.1"
                  name="capacity_tons"
                  className="input"
                  placeholder="e.g. 10"
                  value={formData.capacity_tons}
                  onChange={handleInputChange}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Home City *</label>
                <input
                  type="text"
                  name="home_city"
                  className="input"
                  placeholder="e.g. Nashik"
                  value={formData.home_city}
                  onChange={handleInputChange}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Notes (Optional)</label>
                <input
                  type="text"
                  name="notes"
                  className="input"
                  placeholder="e.g. Prefers short routes"
                  value={formData.notes}
                  onChange={handleInputChange}
                />
              </div>

              <div className="form-actions">
                <button type="button" className="btn-secondary" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Save Registry
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

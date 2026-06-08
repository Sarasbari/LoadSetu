import React, { useState } from 'react';
import Dashboard from './pages/Dashboard';
import Trucks from './pages/Trucks';
import Conversations from './pages/Conversations';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard />;
      case 'trucks':
        return <Trucks />;
      case 'conversations':
        return <Conversations />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div>
          <div className="sidebar-header">
            <h1 className="sidebar-logo">
              Load<span>Setu</span>
            </h1>
          </div>
          
          <ul className="sidebar-menu">
            <li 
              className={`sidebar-item ${activeTab === 'dashboard' ? 'active' : ''}`}
              onClick={() => setActiveTab('dashboard')}
            >
              📊 Dashboard
            </li>
            <li 
              className={`sidebar-item ${activeTab === 'trucks' ? 'active' : ''}`}
              onClick={() => setActiveTab('trucks')}
            >
              🚛 Truck Registry
            </li>
            <li 
              className={`sidebar-item ${activeTab === 'conversations' ? 'active' : ''}`}
              onClick={() => setActiveTab('conversations')}
            >
              💬 Agent Chat Logs
            </li>
          </ul>
        </div>
        
        <div className="sidebar-footer">
          <div>LOADSETU HACKATHON</div>
          <div>FAR AWAY 2026</div>
        </div>
      </aside>

      {/* Main Panel Content Area */}
      <main className="main-content">
        {renderContent()}
      </main>
    </div>
  );
}

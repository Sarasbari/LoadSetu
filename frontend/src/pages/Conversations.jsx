import { useState, useEffect, useCallback } from 'react';
import api from '../lib/api';

export default function Conversations() {
  const [conversations, setConversations] = useState([]);
  const [selectedPhone, setSelectedPhone] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingThread, setLoadingThread] = useState(false);

  const fetchList = useCallback(async () => {
    try {
      const data = await api.get('/conversations');
      setConversations(data.conversations || []);
      setLoadingList(false);
      
      // Auto-select first thread if none selected
      if (data.conversations && data.conversations.length > 0 && !selectedPhone) {
        setSelectedPhone(data.conversations[0].phone_number);
      }
    } catch (error) {
      console.error("Failed to load conversations:", error);
      setLoadingList(false);
    }
  }, [selectedPhone]);

  const fetchThread = useCallback(async (phone) => {
    setLoadingThread(true);
    try {
      const data = await api.get(`/conversations/${phone}`);
      setMessages(data.thread || []);
      setLoadingThread(false);
    } catch (error) {
      console.error(`Failed to load thread for ${phone}:`, error);
      setLoadingThread(false);
    }
  }, []);

  useEffect(() => {
    Promise.resolve().then(() => {
      fetchList();
    });
    const listInterval = setInterval(fetchList, 15000);
    return () => clearInterval(listInterval);
  }, [fetchList]);

  useEffect(() => {
    if (selectedPhone) {
      Promise.resolve().then(() => {
        fetchThread(selectedPhone);
      });
      const threadInterval = setInterval(() => fetchThread(selectedPhone), 10000);
      return () => clearInterval(threadInterval);
    }
  }, [selectedPhone, fetchThread]);

  const renderMessageBody = (text) => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);
    
    return parts.map((part, index) => {
      if (urlRegex.test(part)) {
        const isPdf = part.toLowerCase().endsWith('.pdf') || part.includes('ewb');
        return (
          <a 
            key={index} 
            href={part} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="pdf-link"
          >
            {isPdf ? '📄 View E-Way Bill Draft PDF' : part}
          </a>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  const formatTimestamp = (isoString) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: true 
    });
  };

  if (loadingList) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
        <header className="app-header">
          <h2 className="page-title">WhatsApp Agent Chat Logs</h2>
          <div className="header-actions">
            <div className="sandbox-badge">
              <svg className="sandbox-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
              Sandbox Mode
            </div>
          </div>
        </header>
        <div className="content-body">
          <div style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-display)', fontWeight: 600 }}>Loading conversation lists...</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Consistent Header */}
      <header className="app-header">
        <h2 className="page-title">WhatsApp Agent Chat Logs</h2>
        <div className="header-actions">
          <div className="sandbox-badge">
            <svg className="sandbox-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
            Sandbox Mode
          </div>
        </div>
      </header>

      {/* Main Split Content Body */}
      <div className="content-body">
        <div className="conversations-split-view">
          {/* Threads sidebar */}
          <div className="chats-list-panel">
            <div className="chats-panel-header">ACTIVE CHATS</div>
            <ul className="chats-list">
              {conversations.length === 0 ? (
                <li style={{ padding: '20px', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
                  No messages logged yet.
                </li>
              ) : (
                conversations.map((c, i) => (
                  <li 
                    key={c.phone_number} 
                    className={`chats-list-item ${selectedPhone === c.phone_number ? 'active' : ''}`}
                    onClick={() => setSelectedPhone(c.phone_number)}
                  >
                    <div className="chats-item-header">
                      <div className="chats-phone">{c.phone_number}</div>
                      {/* Show unread indicator or mock unread for first item for realistic mockup feel */}
                      {(c.message_count > 1 || i === 1) && (
                        <span className="chats-unread-badge">
                          Unread
                        </span>
                      )}
                    </div>
                    <div className="chats-snippet">
                      {c.last_direction === 'OUTBOUND' ? '➜ ' : '← '} {c.last_message}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="chats-time">{formatTimestamp(c.last_timestamp)}</span>
                      {/* Message count bubble */}
                      <span style={{ fontSize: '10px', background: 'var(--color-border)', padding: '1px 6px', borderRadius: '10px', fontFamily: 'var(--font-mono)' }}>
                        {c.message_count}
                      </span>
                    </div>
                  </li>
                ))
              )}
            </ul>
          </div>

          {/* Chat Window Thread */}
          <div className="chat-window">
            {selectedPhone ? (
              <>
                <div className="chat-window-header">
                  <span className="chat-window-title">Conversation with {selectedPhone}</span>
                  <button className="btn-refresh" onClick={() => fetchThread(selectedPhone)}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                    </svg>
                    {loadingThread ? 'Refreshing...' : 'Refresh'}
                  </button>
                </div>
                
                <div className="chat-messages-scroller">
                  {messages.length === 0 ? (
                    <div className="chat-window-empty">Thread is empty.</div>
                  ) : (
                    messages.map((m) => {
                      const isOutbound = m.direction.toLowerCase() === 'outbound';
                      return (
                        <div 
                          key={m.id} 
                          className={`chat-bubble-container ${isOutbound ? 'outbound' : 'inbound'}`}
                        >
                          {isOutbound && (
                            <span className="chat-agent-tag">LoadSetu Agent</span>
                          )}
                          <div className={`chat-bubble ${isOutbound ? 'outbound' : 'inbound'}`}>
                            <div>{renderMessageBody(m.body)}</div>
                            <div className="chat-meta">
                              <span className="chat-timestamp">{formatTimestamp(m.timestamp)}</span>
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </>
            ) : (
              <div className="chat-window-empty">
                Select an active chat thread to view conversations.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

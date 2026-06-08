import React, { useState, useEffect } from 'react';
import api from '../lib/api';

export default function Conversations() {
  const [conversations, setConversations] = useState([]);
  const [selectedPhone, setSelectedPhone] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingThread, setLoadingThread] = useState(false);

  const fetchList = async () => {
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
  };

  const fetchThread = async (phone) => {
    setLoadingThread(true);
    try {
      const data = await api.get(`/conversations/${phone}`);
      setMessages(data.thread || []);
      setLoadingThread(false);
    } catch (error) {
      console.error(`Failed to load thread for ${phone}:`, error);
      setLoadingThread(false);
    }
  };

  useEffect(() => {
    fetchList();
    const listInterval = setInterval(fetchList, 15000);
    return () => clearInterval(listInterval);
  }, []);

  useEffect(() => {
    if (selectedPhone) {
      fetchThread(selectedPhone);
      const threadInterval = setInterval(() => fetchThread(selectedPhone), 10000);
      return () => clearInterval(threadInterval);
    }
  }, [selectedPhone]);

  const renderMessageBody = (text) => {
    // Detect URLs (specifically for EWB draft PDF links)
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
    return <div style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-display)' }}>Loading Conversation Logs...</div>;
  }

  return (
    <div className="conversations-container">
      {/* List of active numbers */}
      <div className="threads-sidebar">
        <div className="threads-header">ACTIVE CHATS</div>
        <ul className="threads-list">
          {conversations.length === 0 ? (
            <li style={{ padding: '20px', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
              No messages logged yet.
            </li>
          ) : (
            conversations.map(c => (
              <li 
                key={c.phone_number} 
                className={`thread-item ${selectedPhone === c.phone_number ? 'active' : ''}`}
                onClick={() => setSelectedPhone(c.phone_number)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div className="thread-phone">{c.phone_number}</div>
                  <span style={{ fontSize: '10px', background: 'var(--color-navy-light)', padding: '2px 6px', borderRadius: '10px', fontFamily: 'var(--font-mono)' }}>
                    {c.message_count}
                  </span>
                </div>
                <div className="thread-last-msg">
                  {c.last_direction === 'OUTBOUND' ? '➜ ' : '← '} {c.last_message}
                </div>
                <div className="thread-meta">
                  <span className="thread-time">{formatTimestamp(c.last_timestamp)}</span>
                </div>
              </li>
            ))
          )}
        </ul>
      </div>

      {/* Chat Thread Panel */}
      <div className="chat-viewer">
        {selectedPhone ? (
          <>
            <div className="chat-header">
              <span className="chat-title">Conversation with {selectedPhone}</span>
              <button 
                className="btn-secondary" 
                onClick={() => fetchThread(selectedPhone)}
                style={{ padding: '4px 10px', fontSize: '11px' }}
              >
                {loadingThread ? 'Refreshing...' : '🔄 Refresh'}
              </button>
            </div>
            
            <div className="chat-thread-container">
              {messages.length === 0 ? (
                <div className="chat-empty">Thread is empty.</div>
              ) : (
                messages.map(m => (
                  <div 
                    key={m.id} 
                    className={`chat-message ${m.direction.toLowerCase()}`}
                  >
                    <div>{renderMessageBody(m.body)}</div>
                    <span className="msg-time">{formatTimestamp(m.timestamp)}</span>
                  </div>
                ))
              )}
            </div>
          </>
        ) : (
          <div className="chat-empty">Select a phone number from the list to view chat logs.</div>
        )}
      </div>
    </div>
  );
}

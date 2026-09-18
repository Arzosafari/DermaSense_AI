// App.tsx
import React, { useState, useEffect } from "react";
import ChatPage from "./ChatPage";
import AuthPage from "./AuthPage";
import ProfilePage from "./ProfilePage";
import AnalysisHistoryPage from "./AnalysisHistoryPage";
import { logoutUser, checkAuth } from "./api";
import "./App.css";

// ============================================================
// SVG Icons
// ============================================================

const LogoIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2v20M2 12h20" />
  </svg>
);

const SunIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="5"/>
    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
  </svg>
);

const MoonIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
);

const UserIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
    <circle cx="12" cy="7" r="4"/>
  </svg>
);

const ProfileEditIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
  </svg>
);

// ============================================================
// Helper Functions
// ============================================================

const getStorageKey = (username?: string) => {
  return username ? `smarthealth_sessions_${username}` : "smarthealth_sessions_guest";
};

const getSessions = (username?: string): Array<{ id: string; title: string; lastMessage: string; date: string }> => {
  try {
    const key = getStorageKey(username);
    const sessions = localStorage.getItem(key);
    return sessions ? JSON.parse(sessions) : [];
  } catch {
    return [];
  }
};

const saveSession = (id: string, title: string, lastMessage: string, username?: string) => {
  try {
    const key = getStorageKey(username);
    const sessions = getSessions(username);
    const existing = sessions.findIndex(s => s.id === id);
    const sessionData = {
      id,
      title: title || "New Consultation",
      lastMessage: lastMessage?.substring(0, 100) || "",
      date: new Date().toISOString()
    };
    if (existing >= 0) { sessions[existing] = sessionData; }
    else { sessions.unshift(sessionData); }
    if (sessions.length > 50) sessions.pop();
    localStorage.setItem(key, JSON.stringify(sessions));
  } catch (e) {
    console.error("Failed to save session:", e);
  }
};

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ============================================================
// App Component
// ============================================================

export default function App() {
  const [started, setStarted] = useState(false);
  const [isDark, setIsDark] = useState(true);
  const [activeSession, setActiveSession] = useState<string>("");
  const [showHistory, setShowHistory] = useState(false);
  
  // Auth state
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showAuth, setShowAuth] = useState(false);
  const [showProfile, setShowProfile] = useState(false);  // 🆕
  const [isEditingProfile, setIsEditingProfile] = useState(false);  // 🆕
  const [showAnalysisHistory, setShowAnalysisHistory] = useState(false);  // 🆕
  const [username, setUsername] = useState<string>("");
  const [userProfile, setUserProfile] = useState<any>({});
  const [token, setToken] = useState<string>("");
  const [authChecked, setAuthChecked] = useState(false);
  
  const [sessions, setSessions] = useState<Array<any>>([]);

  useEffect(() => {
    document.body.className = isDark ? 'dark' : 'light';
  }, [isDark]);

  useEffect(() => {
    setSessions(getSessions(username || undefined));
  }, [username]);

  useEffect(() => {
    const checkExistingAuth = async () => {
      const savedToken = localStorage.getItem("smarthealth_token");
      const savedUsername = localStorage.getItem("smarthealth_username");
      const savedProfile = localStorage.getItem("smarthealth_profile");
      
      if (savedToken && savedUsername) {
        setToken(savedToken);
        try {
          const authResult = await checkAuth();
          if (authResult.authenticated) {
            setUsername(savedUsername);
            setUserProfile(authResult.profile || {});
            setIsAuthenticated(true);
          } else {
            localStorage.removeItem("smarthealth_token");
            localStorage.removeItem("smarthealth_username");
            localStorage.removeItem("smarthealth_profile");
          }
        } catch {
          setUsername(savedUsername);
          if (savedProfile) {
            try { setUserProfile(JSON.parse(savedProfile)); } catch {}
          }
          setIsAuthenticated(true);
        }
      }
      setAuthChecked(true);
    };
    checkExistingAuth();
  }, []);

  // Handle login
  const handleLogin = (newToken: string, newUsername: string, profile: any) => {
    if (newToken && newUsername) {
      localStorage.setItem("smarthealth_token", newToken);
      localStorage.setItem("smarthealth_username", newUsername);
      if (profile && Object.keys(profile).length > 0) {
        localStorage.setItem("smarthealth_profile", JSON.stringify(profile));
      }
      setToken(newToken);
      setUsername(newUsername);
      setUserProfile(profile || {});
      setIsAuthenticated(true);
      setSessions(getSessions(newUsername));
    }
    setShowAuth(false);
  };

  // Handle logout
  const handleLogout = async () => {
    try { await logoutUser(); } catch {}
    localStorage.removeItem("smarthealth_token");
    localStorage.removeItem("smarthealth_username");
    localStorage.removeItem("smarthealth_profile");
    setUsername("");
    setUserProfile({});
    setIsAuthenticated(false);
    setStarted(false);
    setShowHistory(false);
    setSessions(getSessions());
  };

  // Start chat
  const startChat = (sessionId?: string) => {
    const newId = sessionId || `user-${crypto.randomUUID()}`;
    setActiveSession(newId);
    localStorage.setItem("smarthealth_session_id", newId);
    setStarted(true);
    setShowHistory(false);
    setShowProfile(false);
  };

  // New chat from within chat page
  const handleNewChat = () => {
    const newId = `user-${crypto.randomUUID()}`;
    setActiveSession(newId);
    localStorage.setItem("smarthealth_session_id", newId);
  };

  // Go back to landing
  const handleBack = () => {
    setStarted(false);
    setShowHistory(false);
    setShowProfile(false);
    setSessions(getSessions(username || undefined));
  };

  // Save session on new message
  const handleNewMessage = (message: string) => {
    if (activeSession) {
      const title = message?.substring(0, 50) || "New Consultation";
      saveSession(activeSession, title, message, username || undefined);
      setSessions(getSessions(username || undefined));
    }
  };

  // 🆕 باز کردن صفحه پروفایل برای ویرایش
  const handleOpenProfile = () => {
    setIsEditingProfile(true);
    setShowProfile(true);
    setStarted(false);
  };

  // 🆕 باز کردن صفحه تاریخچه تحلیل‌ها
  const handleOpenAnalysisHistory = () => {
    setShowAnalysisHistory(true);
    setStarted(false);
  };

  // 🆕 بستن صفحه تاریخچه تحلیل‌ها
  const handleCloseAnalysisHistory = () => {
    setShowAnalysisHistory(false);
    setStarted(true);
  };

  // 🆕 تکمیل/ویرایش پروفایل
  const handleProfileComplete = () => {
    setIsEditingProfile(false);
    setShowProfile(false);
    setStarted(true);
    // رفرش پروفایل
    const savedProfile = localStorage.getItem("smarthealth_profile");
    if (savedProfile) {
      try { setUserProfile(JSON.parse(savedProfile)); } catch {}
    }
  };

  // Loading
  if (!authChecked) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: isDark ? '#0f172a' : '#f8fafc' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '3rem', marginBottom: '20px' }}>🩺</div>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  // Auth page
  if (showAuth) {
    return <AuthPage onLogin={handleLogin} isDark={isDark} />;
  }

  // 🆕 Profile page
  if (showProfile) {
    return (
      <div className="landing-wrap">
        <nav className="nav">
          <div className="logo"><LogoIcon /> MediChat AI</div>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button className="icon-btn" style={{ width: 'auto', padding: '8px 16px' }} onClick={handleBack}>
              ← Back
            </button>
            <button className="icon-btn" style={{ width: 'auto' }} onClick={() => setIsDark(!isDark)}>
              {isDark ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>
        </nav>
        <ProfilePage
          userId={username}
          token={token}
          onComplete={handleProfileComplete}
          onSkip={() => { setShowProfile(false); startChat(); }}
          isEditing={isEditingProfile}
        />
      </div>
    );
  }

  // Analysis History page
  if (showAnalysisHistory) {
    return (
      <div className="app-wrap">
        <nav className="nav">
          <div className="logo"><LogoIcon /> MediChat AI</div>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button className="icon-btn" style={{ width: 'auto' }} onClick={() => setIsDark(!isDark)}>
              {isDark ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>
        </nav>
        <AnalysisHistoryPage
          token={token}
          userId={username}
          onBack={handleCloseAnalysisHistory}
        />
      </div>
    );
  }

  // Chat page
  if (started) {
    return (
      <ChatPage 
        onBack={handleBack} 
        isDark={isDark} 
        toggleTheme={() => setIsDark(!isDark)}
        sessionId={activeSession}
        onNewMessage={handleNewMessage}
        onShowHistory={() => setShowHistory(true)}
        onNewChat={handleNewChat}
        isAuthenticated={isAuthenticated}
        username={username}
        userProfile={userProfile}
        onOpenProfile={handleOpenProfile}  // 🆕
        onOpenAnalysisHistory={handleOpenAnalysisHistory}  // 🆕
      />
    );
  }

  // Landing page
  return (
    <div className="landing-wrap">
      <nav className="nav">
        <div className="logo"><LogoIcon /> MediChat AI</div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          {isAuthenticated ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '14px', color: isDark ? '#94a3b8' : '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <UserIcon /> {username}
              </span>
              <button className="icon-btn" style={{ width: 'auto', padding: '8px 14px', fontSize: '13px' }} onClick={() => { setIsEditingProfile(true); setShowProfile(true); }}>
                <ProfileEditIcon /> Edit Profile
              </button>
              <button className="icon-btn" style={{ width: 'auto', padding: '8px 14px', fontSize: '13px' }} onClick={handleLogout}>Logout</button>
            </div>
          ) : (
            <button className="icon-btn" style={{ width: 'auto', padding: '8px 16px' }} onClick={() => setShowAuth(true)}>
              🔐 Login / Register
            </button>
          )}
          <button className="icon-btn" style={{ width: 'auto', padding: '8px 16px' }} onClick={() => { setSessions(getSessions(username || undefined)); setShowHistory(!showHistory); }}>
            📜 History ({sessions.length})
          </button>
          <button className="icon-btn" style={{ width: 'auto', padding: '8px 12px' }} onClick={() => setIsDark(!isDark)}>
            {isDark ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>
      </nav>

      {/* History Panel */}
      {showHistory && (
        <>
          <div onClick={() => setShowHistory(false)} style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 99 }} />
          <div style={{ position: 'fixed', top: '80px', right: '20px', width: '380px', maxHeight: '70vh', background: isDark ? '#1e293b' : 'white', borderRadius: '16px', boxShadow: isDark ? '0 20px 60px rgba(0,0,0,0.5)' : '0 20px 60px rgba(0,0,0,0.15)', zIndex: 100, overflow: 'hidden', display: 'flex', flexDirection: 'column', border: `1px solid ${isDark ? '#334155' : '#e2e8f0'}` }}>
            <div style={{ padding: '16px 20px', borderBottom: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, color: isDark ? '#f1f5f9' : '#0f172a', fontSize: '16px' }}>📜 {isAuthenticated ? `${username}'s` : 'Guest'} History</h3>
              <button onClick={() => setShowHistory(false)} style={{ background: 'none', border: 'none', color: isDark ? '#94a3b8' : '#64748b', cursor: 'pointer', fontSize: '20px', padding: '4px 8px', borderRadius: '6px' }}>✕</button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
              {sessions.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px 20px', opacity: 0.6 }}>
                  <p style={{ fontSize: '16px', marginBottom: '8px', color: isDark ? '#94a3b8' : '#64748b' }}>📭 No previous conversations</p>
                  <p style={{ fontSize: '13px', color: isDark ? '#64748b' : '#94a3b8' }}>Start a new consultation to see it here</p>
                </div>
              ) : (
                sessions.map(session => (
                  <div key={session.id} onClick={() => { setShowHistory(false); startChat(session.id); }} style={{ padding: '14px 16px', borderRadius: '12px', cursor: 'pointer', transition: 'all 0.15s ease', border: '1px solid transparent', marginBottom: '6px' }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)'; e.currentTarget.style.borderColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'transparent'; }}>
                    <div style={{ fontWeight: 600, marginBottom: '4px', fontSize: '14px', color: isDark ? '#f1f5f9' : '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{session.title || "New Consultation"}</div>
                    <div style={{ fontSize: '12px', color: isDark ? '#94a3b8' : '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: '6px' }}>{session.lastMessage?.substring(0, 80) || "No messages"}</div>
                    <div style={{ fontSize: '11px', color: isDark ? '#64748b' : '#94a3b8' }}>{formatDate(session.date)}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}

      <main className="hero">
        <div className="pill">AI-POWERED SKIN DIAGNOSTICS</div>
        <h1>DermaSense AI <br /></h1>
        <p className="subtext">Instant skin analysis, symptom matching, and personalized health guidance. Powered by advanced medical AI.</p>
        <div style={{ display: 'flex', gap: '15px', justifyContent: 'center', flexWrap: 'wrap' }}>
          <button className="cta-btn" onClick={() => startChat()}>🆕 New Consultation</button>
          {isAuthenticated && (
            <button className="cta-btn" onClick={() => { setIsEditingProfile(false); setShowProfile(true); }} style={{ background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.3)' }}>
              👤 Complete Profile
            </button>
          )}
          {sessions.length > 0 && (
            <button className="cta-btn" onClick={() => startChat(sessions[0].id)} style={{ background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.3)' }}>
              📜 Continue Last Chat
            </button>
          )}
        </div>
        <div style={{ display: 'flex', gap: '20px', justifyContent: 'center', flexWrap: 'wrap', marginTop: '60px' }}>
          {['🔬 Image Analysis', '🩻 Symptom Matching', '📚 Disease Info'].map((feature, i) => (
            <div key={i} style={{ background: isDark ? 'rgba(30,41,59,0.8)' : 'rgba(255,255,255,0.8)', padding: '20px', borderRadius: '12px', maxWidth: '200px', textAlign: 'center', border: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}` }}>
              <div style={{ fontSize: '32px', marginBottom: '10px' }}>{feature.split(' ')[0]}</div>
              <div style={{ fontWeight: 600, marginBottom: '6px', color: isDark ? '#f1f5f9' : '#0f172a' }}>{feature.split(' ').slice(1).join(' ')}</div>
              <div style={{ fontSize: '12px', color: isDark ? '#94a3b8' : '#64748b' }}>Advanced AI-powered dermatology tools</div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
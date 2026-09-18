// ChatPage.tsx
import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { askBackend, onConnectionStatusChange, checkHealth, getChatHistory, clearChatHistory, downloadAnalysisReport } from "./api";
import "./App.css";

// --- SVGs ---
const BotIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2 2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/><path d="M4 11a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-7z"/><rect x="8" y="13" width="2" height="2"/><rect x="14" y="13" width="2" height="2"/></svg>;
const UserIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>;
const PlusIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>;
const SendIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>;
const ClipIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>;
const ExitIcon = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>;
const TrashIcon = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>;
const MessageIcon = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>;
const ProfileEditIcon = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>;
const HistoryIcon = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>;

// --- Helpers ---

// Language detection function for RTL support
const detectLanguage = (text: string): 'persian' | 'english' => {
  // Persian Unicode range and common Persian characters
  const persianPattern = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;
  return persianPattern.test(text) ? 'persian' : 'english';
};
const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = (error) => reject(error);
  });
};

const formatHistoryToMessages = (history: any[]): any[] => {
  if (!history || !Array.isArray(history)) return [];
  const messages: any[] = [];
  history.forEach((item: any) => {
    if (item.user_message) {
      messages.push({
        type: "user",
        content: item.user_message,
        isImage: !!item.image_data,
        previewUrl: item.image_data || null,
        timestamp: item.timestamp
      });
    }
    if (item.agent_output) {
      messages.push({
        type: "bot",
        content: item.agent_output,
        isImage: false,
        previewUrl: null,
        analysis: item.analysis_data || null,
        timestamp: item.timestamp
      });
    }
  });
  return messages;
};

// Enhanced message renderer for improved medical analysis display
const renderMedicalAnalysis = (content: string) => {
  // Check if content contains structured analysis markers
  if (content.includes("🔬") || content.includes("📊") || content.includes("👤")) {
    // This is the new structured format - render as-is with markdown
    return content;
  }
  return content;
};

const formatDate = (dateStr: string): string => {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

// --- Interface ---
interface ChatPageProps {
  onBack: () => void;
  isDark: boolean;
  toggleTheme: () => void;
  sessionId: string;
  onNewMessage: (message: string) => void;
  onShowHistory: () => void;
  onNewChat?: () => void;
  isAuthenticated?: boolean;
  username?: string;
  userProfile?: any;
  onOpenProfile?: () => void;  // 🆕
  onOpenAnalysisHistory?: () => void;  // 🆕
}

export default function ChatPage({ 
  onBack, isDark, toggleTheme, sessionId, onNewMessage, onShowHistory,
  onNewChat, isAuthenticated = false, username = "", userProfile = {},
  onOpenProfile,  // 🆕
  onOpenAnalysisHistory  // 🆕
}: ChatPageProps) {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("connecting");
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState(sessionId);
  const [stagedImage, setStagedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Only sync with parent prop when it actually changes, not when local state changes
  useEffect(() => { setCurrentSessionId(sessionId); }, [sessionId]);

  const getStorageKey = () => isAuthenticated && username ? `smarthealth_sessions_${username}` : "smarthealth_sessions_guest";

  const getCurrentUserSessions = (): any[] => {
    try {
      const sessions = localStorage.getItem(getStorageKey());
      return sessions ? JSON.parse(sessions) : [];
    } catch { return []; }
  };

  const saveCurrentUserSession = (id: string, title: string, lastMessage: string) => {
    try {
      const sessions = getCurrentUserSessions();
      const existing = sessions.findIndex((s: any) => s.id === id);
      const sessionData = { id, title: title || "New Consultation", lastMessage: lastMessage?.substring(0, 100) || "", date: new Date().toISOString() };
      if (existing >= 0) sessions[existing] = sessionData;
      else sessions.unshift(sessionData);
      if (sessions.length > 50) sessions.pop();
      localStorage.setItem(getStorageKey(), JSON.stringify(sessions));
    } catch (e) { console.error("Failed to save session:", e); }
  };

  const loadHistory = async (sid: string) => {
    setLoadingHistory(true);
    setMessages([]);
    try {
      const history = await getChatHistory(sid);
      if (history && Array.isArray(history) && history.length > 0) setMessages(formatHistoryToMessages(history));
    } catch (error) { console.error("Failed to load history:", error); }
    finally { setLoadingHistory(false); }
  };

  useEffect(() => { if (currentSessionId) loadHistory(currentSessionId); }, [currentSessionId]);

  const handleClearHistory = async () => {
    if (window.confirm("Clear current chat history?")) {
      try { await clearChatHistory(currentSessionId); setMessages([]); }
      catch (error) { console.error("Failed to clear history:", error); }
    }
  };

  const handleLoadSession = (sid: string) => {
    localStorage.setItem("smarthealth_session_id", sid);
    setCurrentSessionId(sid);
  };

  const handleNewChat = () => {
    if (onNewChat) onNewChat();
    else {
      const newId = `user-${crypto.randomUUID()}`;
      localStorage.setItem("smarthealth_session_id", newId);
      setCurrentSessionId(newId);
    }
  };

  useEffect(() => { const sub = onConnectionStatusChange(setStatus); checkHealth().catch(() => {}); return sub; }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  const handleSend = async () => {
    if (!query.trim() && !stagedImage) return;
    const text = query.trim();
    const imageToSend = stagedImage;
    const previewUrlToSend = imagePreview;
    setMessages(prev => [...prev, { type: "user", content: text || "Analyze this image", isImage: !!imageToSend, previewUrl: previewUrlToSend }]);
    setQuery(""); setStagedImage(null); setImagePreview(null); setLoading(true);
    try {
      let imageBase64: string | undefined = undefined;
      if (imageToSend) imageBase64 = await fileToBase64(imageToSend);
      const res = await askBackend(text || "Analyze this image", currentSessionId, imageBase64);

      // Handle new return type (object with reply and analysis)
      const replyText = typeof res === 'string' ? res : res.reply;

      // Check if response contains structured analysis data
      const enhancedResponse = renderMedicalAnalysis(replyText);

      // Store analysis data for potential structured display
      const analysisData = typeof res === 'object' && res.analysis ? res.analysis : null;

      setMessages(prev => [...prev, {
        type: "bot",
        content: enhancedResponse,
        analysis: analysisData ? {
          ...analysisData,
          analysis_id: analysisData.analysis_id || `analysis-${Date.now()}`  // Ensure analysis_id exists
        } : null
      }]);
      saveCurrentUserSession(currentSessionId, text || "Image analysis", enhancedResponse);
      onNewMessage(text || "Image analysis");
    } catch (e: any) {
      setMessages(prev => [...prev, { type: "bot", content: `⚠️ ${e.message || 'System Error. Please retry.'}` }]);
    } finally { setLoading(false); }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) { setStagedImage(file); setImagePreview(URL.createObjectURL(file)); }
    if (fileRef.current) fileRef.current.value = "";
  };

  const cancelImage = () => { setStagedImage(null); setImagePreview(null); };

  const handleDownloadReport = async (analysisId: string) => {
    try {
      await downloadAnalysisReport(analysisId);
    } catch (e: any) {
      console.error("Failed to download report:", e);
      alert("Failed to download report. Please try again.");
    }
  };

  const sidebarSessions = getCurrentUserSessions();

  return (
    <div className="chat-layout">
      <aside className="sidebar" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
        {isAuthenticated && (
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'linear-gradient(135deg, #0d9488, #14b8a6)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '16px', color: 'white', fontWeight: 600, flexShrink: 0 }}>
              {username?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-main)' }}>{username || 'User'}</div>
              {userProfile?.skin_type && <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Skin: {userProfile.skin_type}</div>}
            </div>
          </div>
        )}

        <div style={{ padding: '16px', borderBottom: '1px solid var(--border)' }}>
          <button className="new-chat" onClick={handleNewChat}><PlusIcon /> New Consultation</button>
        </div>

        {/* 🆕 دکمه Edit Profile */}
        {isAuthenticated && onOpenProfile && (
          <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--border)' }}>
            <button className="new-chat" onClick={onOpenProfile} style={{ background: 'rgba(13, 148, 136, 0.15)', color: 'var(--primary)' }}>
              <ProfileEditIcon /> {userProfile && Object.keys(userProfile).length > 0 ? 'Update Profile' : 'Complete Profile'}
            </button>
          </div>
        )}

        {/* 🆕 دکمه Analysis History */}
        {isAuthenticated && onOpenAnalysisHistory && (
          <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--border)' }}>
            <button className="new-chat" onClick={onOpenAnalysisHistory} style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6' }}>
              <HistoryIcon /> Analysis History
            </button>
          </div>
        )}

        <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>📜 Recent Chats</span>
          </div>
          {sidebarSessions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px 10px', color: 'var(--text-muted)', fontSize: '12px', opacity: 0.6 }}><MessageIcon /><p style={{ marginTop: '8px' }}>No conversations yet</p></div>
          ) : (
            sidebarSessions.map((session: any) => (
              <div key={session.id} onClick={() => handleLoadSession(session.id)}
                style={{ padding: '10px 12px', marginBottom: '4px', borderRadius: '8px', cursor: 'pointer', background: session.id === currentSessionId ? 'rgba(13, 148, 136, 0.15)' : 'transparent', border: session.id === currentSessionId ? '1px solid var(--primary)' : '1px solid transparent', transition: 'all 0.15s ease' }}
                onMouseEnter={(e) => { if (session.id !== currentSessionId) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
                onMouseLeave={(e) => { if (session.id !== currentSessionId) e.currentTarget.style.background = 'transparent'; }}>
                <div style={{ fontSize: '13px', fontWeight: session.id === currentSessionId ? 600 : 500, color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: '2px' }}>{session.title || "New Consultation"}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{session.lastMessage?.substring(0, 60) || "No messages"}</div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', opacity: 0.5, marginTop: '4px' }}>{formatDate(session.date)}</div>
              </div>
            ))
          )}
        </div>

        <div style={{ padding: '16px', borderTop: '1px solid var(--border)' }}>
          <div className="icon-btn" style={{ cursor: 'default', marginBottom: '4px' }}>
            <span style={{ color: status === 'connected' ? '#22c55e' : '#ef4444', marginRight: '8px' }}>●</span>
            {status === 'connected' ? 'Operational' : 'Offline'}
          </div>
          <button className="icon-btn" onClick={handleClearHistory} style={{ color: '#ef4444' }}><TrashIcon /> Clear Current Chat</button>
          <button className="icon-btn" onClick={toggleTheme}>{isDark ? "☀️ Light Mode" : "🌙 Dark Mode"}</button>
          <button className="icon-btn" onClick={onBack}><ExitIcon /> End Session</button>
        </div>
      </aside>

      <main className="main-area">
        <div className="chat-scroll">
          <div className="chat-width">
            {loadingHistory ? (
              <div style={{ textAlign: 'center', marginTop: '10vh', opacity: 0.7 }}><p>⏳ Loading conversation...</p></div>
            ) : messages.length === 0 ? (
              <div style={{ textAlign: 'center', marginTop: '10vh', opacity: 0.5 }}>
                <div style={{ fontSize: '3rem', marginBottom: '20px' }}>🩺</div>
                <h2>How can I assist you today?</h2>
                <p>Describe your skin symptoms or upload an image for analysis.</p>
              </div>
            ) : (
              messages.map((m, i) => (
                <div key={i} className="msg">
                  <div className={`avatar ${m.type}`}>{m.type === 'bot' ? <BotIcon /> : <UserIcon />}</div>
                  <div className="bubble" dir={detectLanguage(m.content) === 'persian' ? 'rtl' : 'ltr'} lang={detectLanguage(m.content) === 'persian' ? 'fa' : 'en'} style={{ unicodeBidi: 'plaintext' }}>
                    {m.isImage && m.previewUrl && (
                      <div style={{ marginBottom: '12px' }}>
                        <img 
                          src={m.previewUrl} 
                          alt="upload" 
                          style={{ 
                            maxWidth: '100%', 
                            maxHeight: '300px', 
                            borderRadius: '12px', 
                            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                            objectFit: 'contain'
                          }} 
                        />
                        {m.content === "Analyze this image" && (
                          <div style={{ 
                            marginTop: '8px', 
                            fontSize: '13px', 
                            color: 'var(--text-muted)', 
                            fontStyle: 'italic',
                            textAlign: 'center'
                          }}>
                            🔍 Image uploaded for analysis
                          </div>
                        )}
                      </div>
                    )}
                    {m.type === 'bot' ? (
                      <>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                        {m.analysis && (
                          <div dir={detectLanguage(m.content) === 'persian' ? 'rtl' : 'ltr'} style={{ marginTop: '15px', padding: '12px', background: 'rgba(13, 148, 136, 0.1)', borderRadius: '8px', fontSize: '12px', unicodeBidi: 'plaintext' }}>
                            <div style={{ fontWeight: 600, marginBottom: '8px', color: 'var(--primary)' }}>📊 Analysis Details</div>
                            <div>Predicted: <span dir="ltr">{m.analysis.model?.predicted_class || 'N/A'}</span></div>
                            <div>Confidence: <span dir="ltr">{m.analysis.model?.confidence ? `${(m.analysis.model.confidence * 100).toFixed(1)}%` : 'N/A'}</span></div>
                            {m.analysis.risk_assessment?.screening_level && (
                              <div>Risk Level: {m.analysis.risk_assessment.screening_level}</div>
                            )}
                            
                            {/* All Probabilities */}
                            {m.analysis.model?.all_probabilities && Object.keys(m.analysis.model.all_probabilities).length > 0 && (
                              <div style={{ marginTop: '10px' }}>
                                <div style={{ fontWeight: 600, marginBottom: '5px' }}>All Model Probabilities:</div>
                                {Object.entries(m.analysis.model.all_probabilities)
                                  .sort(([,a], [,b]) => (b as number) - (a as number))
                                  .map(([className, prob]) => (
                                    <div key={className} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                                      <span>{className}</span>
                                      <span>{((prob as number) * 100).toFixed(2)}%</span>
                                    </div>
                                  ))}
                              </div>
                            )}
                            
                            {/* Top 3 Predictions */}
                            {m.analysis.model?.top3_predictions && m.analysis.model.top3_predictions.length > 0 && (
                              <div style={{ marginTop: '10px' }}>
                                <div style={{ fontWeight: 600, marginBottom: '5px' }}>Top 3 Predictions:</div>
                                {m.analysis.model.top3_predictions.map((pred: any, idx: number) => (
                                  <div key={idx} style={{ fontSize: '11px' }}>
                                    {idx + 1}. {pred.class} — {pred.probability ? `${(pred.probability * 100).toFixed(2)}%` : 'N/A'}
                                  </div>
                                ))}
                              </div>
                            )}
                            
                            {/* Explainability Visualization */}
                            {m.analysis.explainability?.available && (
                              <div style={{ marginTop: '15px', padding: '12px', background: 'rgba(13, 148, 136, 0.1)', borderRadius: '8px', fontSize: '12px' }}>
                                <div style={{ fontWeight: 600, marginBottom: '8px', color: 'var(--primary)' }}>🔍 Explainability Visualization</div>
                                <div style={{ fontSize: '11px', marginBottom: '8px', color: '#666' }}>
                                  The heatmap highlights image regions that contributed more strongly to the model prediction.
                                  This is an AI explainability visualization and is not a clinical diagnostic finding.
                                </div>
                                {m.analysis.explainability.overlay_path && (
                                  <div style={{ textAlign: 'center' }}>
                                    <img 
                                      src={`http://localhost:8000/chat/files/${m.analysis.explainability.overlay_path.split(/\\|\//).pop()}`}
                                      alt="Explainability Heatmap Overlay"
                                      style={{ maxWidth: '100%', maxHeight: '300px', borderRadius: '4px' }}
                                      onError={(e) => {
                                        console.error('Failed to load heatmap:', e);
                                        (e.target as HTMLImageElement).style.display = 'none';
                                      }}
                                      onLoad={() => {
                                        console.log('Heatmap loaded successfully');
                                      }}
                                    />
                                  </div>
                                )}
                              </div>
                            )}
                            
                            {/* PDF Download Button */}
                            {m.analysis.report?.available && m.analysis.analysis_id && (
                              <div style={{ marginTop: '12px' }}>
                                <button
                                  onClick={() => handleDownloadReport(m.analysis.analysis_id)}
                                  style={{
                                    padding: '8px 16px',
                                    background: 'var(--primary)',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontSize: '12px',
                                    fontWeight: 600
                                  }}
                                >
                                  📄 Download PDF Report
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </>
                    ) : m.content}
                  </div>
                </div>
              ))
            )}
            {loading && (
              <div className="msg"><div className="avatar bot"><BotIcon /></div><div className="bubble">Analyzing...</div></div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>
        
        <div className="input-area" style={{ position: 'relative', padding: '0 40px 32px' }}>
          <div className="input-float">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {imagePreview && (
                <div style={{ position: 'relative', display: 'inline-block' }}>
                  <img 
                    src={imagePreview} 
                    alt="Staged" 
                    style={{ 
                      width: '36px', 
                      height: '36px', 
                      borderRadius: '8px', 
                      objectFit: 'cover',
                      border: '2px solid var(--primary)'
                    }} 
                  />
                  <button 
                    onClick={cancelImage}
                    style={{
                      position: 'absolute',
                      top: '-8px',
                      right: '-8px',
                      background: '#ef4444',
                      border: '2px solid var(--bg-card)',
                      color: 'white',
                      cursor: 'pointer',
                      padding: '2px',
                      borderRadius: '50%',
                      fontSize: '10px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '16px',
                      height: '16px'
                    }}
                  >
                    ×
                  </button>
                </div>
              )}
              <button style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '10px' }} onClick={() => fileRef.current?.click()}><ClipIcon /></button>
            </div>
            <input placeholder="Describe your skin symptoms..." value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()} disabled={loading} />
            <button className="send-icon" onClick={handleSend} disabled={(!query.trim() && !stagedImage) || loading}><SendIcon /></button>
          </div>
        </div>
        <input type="file" hidden ref={fileRef} onChange={handleFileSelect} accept="image/*" />
      </main>
    </div>
  );
}
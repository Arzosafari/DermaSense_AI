// frontend/src/AuthPage.tsx
import React, { useState } from "react";

const API_URL = "http://localhost:8000";

interface AuthPageProps {
  onLogin: (token: string, username: string, profile: any) => void;
  isDark: boolean;
}

export default function AuthPage({ onLogin, isDark }: AuthPageProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  
  // Profile fields (for registration)
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [skinType, setSkinType] = useState("");
  const [allergies, setAllergies] = useState("");
  const [medicalConditions, setMedicalConditions] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const body: any = { username, password };
      
      if (mode === "register") {
        body.profile = {
          name: name || null,
          age: age ? parseInt(age) : null,
          gender: gender || null,
          skin_type: skinType || null,
          allergies: allergies || null,
          medical_conditions: medicalConditions || null,
        };
      }

      const response = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "Authentication failed");
      }

      localStorage.setItem("smarthealth_token", data.token);
      localStorage.setItem("smarthealth_username", data.username);
      if (data.profile) {
        localStorage.setItem("smarthealth_profile", JSON.stringify(data.profile));
      }
      
      onLogin(data.token, data.username, data.profile || {});
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '12px',
    marginBottom: '12px',
    borderRadius: '8px',
    border: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`,
    background: isDark ? '#0f172a' : '#f8fafc',
    color: isDark ? '#f1f5f9' : '#0f172a',
    fontSize: '14px',
    outline: 'none',
    boxSizing: 'border-box',
  };

  const selectStyle: React.CSSProperties = {
    ...inputStyle,
    cursor: 'pointer',
  };

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: isDark 
        ? 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)' 
        : 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)',
      padding: '20px',
    }}>
      <div style={{
        background: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
        padding: '40px',
        borderRadius: '20px',
        width: '100%',
        maxWidth: '480px',
        boxShadow: isDark 
          ? '0 25px 50px -12px rgba(0, 0, 0, 0.5)' 
          : '0 25px 50px -12px rgba(0, 0, 0, 0.15)',
        backdropFilter: 'blur(10px)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            width: '60px',
            height: '60px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, #0d9488, #14b8a6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
            fontSize: '28px',
          }}>
            🩺
          </div>
          <h2 style={{ 
            color: isDark ? '#f1f5f9' : '#0f172a',
            margin: '0 0 4px',
            fontSize: '24px',
            fontWeight: 700,
          }}>
            {mode === "login" ? "Welcome Back" : "Create Account"}
          </h2>
          <p style={{ 
            color: isDark ? '#94a3b8' : '#64748b',
            margin: 0,
            fontSize: '14px',
          }}>
            {mode === "login" 
              ? "Sign in to access your personalized health assistant" 
              : "Create a profile for personalized skin health guidance"}
          </p>
        </div>
        
        {/* Error message */}
        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#ef4444',
            padding: '12px 16px',
            borderRadius: '10px',
            marginBottom: '20px',
            fontSize: '14px',
          }}>
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={3}
            style={inputStyle}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={4}
            style={inputStyle}
          />

          {mode === "register" && (
            <>
              <div style={{ 
                color: isDark ? '#94a3b8' : '#64748b',
                fontSize: '12px',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '1px',
                marginBottom: '12px',
                marginTop: '8px',
              }}>
                📋 Health Profile (Optional)
              </div>
              
              <input
                type="text"
                placeholder="Full Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                style={inputStyle}
              />
              
              <div style={{ display: 'flex', gap: '12px' }}>
                <input
                  type="number"
                  placeholder="Age"
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  min={1}
                  max={120}
                  style={{ ...inputStyle, flex: 1 }}
                />
                <select
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  style={{ ...selectStyle, flex: 1 }}
                >
                  <option value="">Gender</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>
              
              <select
                value={skinType}
                onChange={(e) => setSkinType(e.target.value)}
                style={selectStyle}
              >
                <option value="">Skin Type</option>
                <option value="oily">Oily</option>
                <option value="dry">Dry</option>
                <option value="combination">Combination</option>
                <option value="sensitive">Sensitive</option>
                <option value="normal">Normal</option>
              </select>
              
              <input
                type="text"
                placeholder="Allergies (e.g., pollen, nuts, latex)"
                value={allergies}
                onChange={(e) => setAllergies(e.target.value)}
                style={inputStyle}
              />
              
              <input
                type="text"
                placeholder="Medical Conditions (e.g., diabetes, eczema)"
                value={medicalConditions}
                onChange={(e) => setMedicalConditions(e.target.value)}
                style={inputStyle}
              />
            </>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '14px',
              background: loading 
                ? '#94a3b8' 
                : 'linear-gradient(135deg, #0d9488, #14b8a6)',
              color: 'white',
              border: 'none',
              borderRadius: '12px',
              fontSize: '16px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              marginTop: '20px',
              transition: 'all 0.2s ease',
            }}
          >
            {loading ? (
              <span>⏳ Processing...</span>
            ) : mode === "login" ? (
              "🔐 Sign In"
            ) : (
              "✨ Create Account"
            )}
          </button>
        </form>

        {/* Toggle mode */}
        <div style={{ 
          textAlign: 'center', 
          marginTop: '20px',
          color: isDark ? '#94a3b8' : '#64748b',
          fontSize: '14px',
        }}>
          {mode === "login" ? (
            <p>
              Don't have an account?{' '}
              <button
                onClick={() => { setMode("register"); setError(""); }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#0d9488',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: '14px',
                }}
              >
                Register
              </button>
            </p>
          ) : (
            <p>
              Already have an account?{' '}
              <button
                onClick={() => { setMode("login"); setError(""); }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#0d9488',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: '14px',
                }}
              >
                Sign In
              </button>
            </p>
          )}
        </div>
        
        {/* Skip / Guest */}
        <div style={{ 
          textAlign: 'center', 
          marginTop: '12px',
          borderTop: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`,
          paddingTop: '16px',
        }}>
          <button
            onClick={() => onLogin("", "", {})}
            style={{
              background: 'none',
              border: 'none',
              color: isDark ? '#94a3b8' : '#64748b',
              cursor: 'pointer',
              fontSize: '14px',
              textDecoration: 'underline',
              opacity: 0.7,
            }}
          >
            Skip & Continue as Guest
          </button>
        </div>
      </div>
    </div>
  );
}
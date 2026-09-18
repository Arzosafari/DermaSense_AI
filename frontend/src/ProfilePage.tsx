// frontend/src/ProfilePage.tsx
import React, { useState, useEffect } from "react";

interface ProfilePageProps {
  userId: string;
  token: string;
  onComplete: () => void;
  onSkip: () => void;
  isEditing?: boolean;
}

export default function ProfilePage({ userId, token, onComplete, onSkip, isEditing = false }: ProfilePageProps) {
  const [age, setAge] = useState(30);
  const [gender, setGender] = useState("male");
  const [skinType, setSkinType] = useState("normal");
  const [allergies, setAllergies] = useState("");
  const [chronicConditions, setChronicConditions] = useState("");
  const [medications, setMedications] = useState("");
  const [smoking, setSmoking] = useState(false);
  const [alcoholConsumption, setAlcoholConsumption] = useState("none");
  const [exerciseFrequency, setExerciseFrequency] = useState("occasional");
  const [sunExposure, setSunExposure] = useState("moderate");
  const [loading, setLoading] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (isEditing && userId) loadExistingProfile();
  }, [isEditing, userId]);

  const loadExistingProfile = async () => {
    setLoadingProfile(true);
    try {
      const token = localStorage.getItem("smarthealth_token");
      console.log("Loading profile with token:", token ? "exists" : "missing");
      
      const res = await fetch(`http://localhost:8000/patient/profile`, {
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        }
      });
      console.log("Profile load response status:", res.status);
      
      const data = await res.json();
      console.log("Profile load data:", data);
      
      if (data.profile) {
        const p = data.profile;
        setAge(p.age || 30);
        setGender(p.gender || "male");
        setSkinType(p.skin_type || "normal");
        setAllergies((p.allergies || []).join(", "));
        setChronicConditions((p.chronic_conditions || []).join(", "));
        setMedications((p.current_medications || []).join(", "));
        setSmoking(p.smoking || false);
        setAlcoholConsumption(p.alcohol_consumption || "none");
        setExerciseFrequency(p.exercise_frequency || "occasional");
        setSunExposure(p.sun_exposure || "moderate");
        console.log("Profile loaded successfully:", p);
      } else {
        console.log("No profile found in response");
      }
    } catch (e) { 
      console.error("Failed to load profile:", e); 
    }
    setLoadingProfile(false);
  };

  const handleSave = async () => {
    setLoading(true); setMessage("");
    try {
      const token = localStorage.getItem("smarthealth_token");
      const res = await fetch("http://localhost:8000/patient/profile", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          profile: {
            age, gender, skin_type: skinType,
            allergies: allergies.split(",").map(s => s.trim()).filter(Boolean),
            chronic_conditions: chronicConditions.split(",").map(s => s.trim()).filter(Boolean),
            current_medications: medications.split(",").map(s => s.trim()).filter(Boolean),
            smoking, alcohol_consumption: alcoholConsumption,
            exercise_frequency: exerciseFrequency, sun_exposure: sunExposure, skin_concerns: [],
          }
        })
      });
      if (res.ok) {
        const data = await res.json();
        // 🆕 به‌روزرسانی localStorage
        if (data.profile) {
          localStorage.setItem("smarthealth_profile", JSON.stringify(data.profile));
          console.log("Profile saved to localStorage:", data.profile);
        }
        setMessage(isEditing ? "✅ Profile updated successfully!" : "✅ Profile saved successfully!");
        setTimeout(() => onComplete(), 1000);
      } else {
        const error = await res.json();
        console.error("Profile save error:", error);
        setMessage(`❌ ${error.detail || 'Failed to save profile'}`);
      }
    } catch (e) { 
      console.error("Profile save exception:", e);
      setMessage("❌ Cannot connect to server."); 
    }
    setLoading(false);
  };

  if (loadingProfile) {
    return <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}><p>Loading profile...</p></div>;
  }

  const inputStyle = { width: '100%', padding: '12px', borderRadius: '10px', border: '1px solid var(--border)', background: 'var(--bg-app)', color: 'var(--text-main)' };
  const labelStyle = { display: 'block', marginBottom: '5px', fontSize: '13px', fontWeight: 500 } as const;

  return (
    <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '20px', overflow: 'auto' }}>
      <div style={{ background: 'var(--bg-card)', padding: '30px 40px', borderRadius: '20px', width: '100%', maxWidth: '600px', border: '1px solid var(--border)', maxHeight: '90vh', overflow: 'auto' }}>
        <div style={{ textAlign: 'center', marginBottom: '25px' }}>
          <span style={{ fontSize: '2.5rem' }}>👤</span>
          <h2>{isEditing ? "Update Your Profile" : "Complete Your Profile"}</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            {isEditing ? "Update your information for better personalized recommendations" : "This helps us provide personalized skin health recommendations"}
          </p>
        </div>

        {message && (
          <div style={{ padding: '12px', borderRadius: '10px', marginBottom: '20px', fontSize: '14px', background: message.startsWith('✅') ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)', color: message.startsWith('✅') ? '#22c55e' : '#ef4444', border: `1px solid ${message.startsWith('✅') ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}` }}>
            {message}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '15px' }}>
          <div><label style={labelStyle}>Age</label><input type="number" value={age} onChange={(e) => setAge(parseInt(e.target.value) || 0)} style={inputStyle} /></div>
          <div><label style={labelStyle}>Gender</label><select value={gender} onChange={(e) => setGender(e.target.value)} style={inputStyle}><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></select></div>
        </div>

        <div style={{ marginBottom: '15px' }}><label style={labelStyle}>Skin Type</label><select value={skinType} onChange={(e) => setSkinType(e.target.value)} style={inputStyle}><option value="normal">Normal</option><option value="dry">Dry</option><option value="oily">Oily</option><option value="combination">Combination</option><option value="sensitive">Sensitive</option></select></div>
        <div style={{ marginBottom: '15px' }}><label style={labelStyle}>Allergies (comma separated)</label><input placeholder="e.g., penicillin, latex, peanuts" value={allergies} onChange={(e) => setAllergies(e.target.value)} style={inputStyle} /></div>
        <div style={{ marginBottom: '15px' }}><label style={labelStyle}>Chronic Conditions</label><input placeholder="e.g., diabetes, eczema, asthma" value={chronicConditions} onChange={(e) => setChronicConditions(e.target.value)} style={inputStyle} /></div>
        <div style={{ marginBottom: '15px' }}><label style={labelStyle}>Current Medications</label><input placeholder="e.g., metformin, ibuprofen" value={medications} onChange={(e) => setMedications(e.target.value)} style={inputStyle} /></div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '15px' }}>
          <div><label style={labelStyle}>Alcohol</label><select value={alcoholConsumption} onChange={(e) => setAlcoholConsumption(e.target.value)} style={inputStyle}><option value="none">None</option><option value="occasional">Occasional</option><option value="regular">Regular</option></select></div>
          <div><label style={labelStyle}>Exercise</label><select value={exerciseFrequency} onChange={(e) => setExerciseFrequency(e.target.value)} style={inputStyle}><option value="none">None</option><option value="occasional">Occasional</option><option value="regular">Regular</option><option value="daily">Daily</option></select></div>
          <div><label style={labelStyle}>Sun Exposure</label><select value={sunExposure} onChange={(e) => setSunExposure(e.target.value)} style={inputStyle}><option value="low">Low</option><option value="moderate">Moderate</option><option value="high">High</option></select></div>
        </div>

        <div style={{ marginBottom: '25px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <input type="checkbox" checked={smoking} onChange={(e) => setSmoking(e.target.checked)} style={{ width: '18px', height: '18px' }} />
          <label style={{ fontSize: '14px' }}>I smoke</label>
        </div>

        <button onClick={handleSave} disabled={loading} style={{ width: '100%', padding: '14px', background: loading ? 'var(--border)' : 'var(--primary)', color: 'white', border: 'none', borderRadius: '12px', fontSize: '16px', fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer', marginBottom: '10px' }}>
          {loading ? "Saving..." : (isEditing ? "💾 Update Profile" : "💾 Save Profile & Continue")}
        </button>
        {!isEditing && (
          <button onClick={onSkip} style={{ width: '100%', padding: '12px', background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '12px', fontSize: '14px', cursor: 'pointer' }}>
            Skip for now →
          </button>
        )}
      </div>
    </div>
  );
}
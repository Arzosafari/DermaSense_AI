// frontend/src/api.ts
import axios from "axios";

// استفاده از آدرس مستقیم به جای پروکسی
const API_URL = "http://localhost:8000";

export type ConnectionStatus = "connected" | "connecting" | "error";

let backendHealthy = false;
let connectionStatus: ConnectionStatus = "connecting";
const statusListeners: ((status: ConnectionStatus) => void)[] = [];

const notifyStatusChange = (status: ConnectionStatus) => {
  connectionStatus = status;
  statusListeners.forEach(listener => listener(status));
};

// ============================================================
// Auth Helpers
// ============================================================

const getAuthHeaders = () => {
  const token = localStorage.getItem("smarthealth_token");
  const headers: any = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

// ============================================================
// Health Check
// ============================================================

export const checkHealth = async (): Promise<boolean> => {
  notifyStatusChange("connecting");
  try {
    console.log("🩺 Checking health at:", `${API_URL}/health/status`);
    const response = await axios.get(`${API_URL}/health/status`, {
      timeout: 5000,
      headers: { 'Accept': 'application/json' }
    });
    
    backendHealthy = response.status === 200;
    
    console.log("✅ Backend health:", backendHealthy);
    notifyStatusChange(backendHealthy ? "connected" : "error");
    return backendHealthy;
    
  } catch (error: any) {
    console.error("❌ Backend not reachable:", error.message);
    backendHealthy = false;
    notifyStatusChange("error");
    return false;
  }
};

// ============================================================
// Chat API
// ============================================================

export const askBackend = async (message: string, userId: string, image?: string) => {
  if (!backendHealthy) {
    const isHealthy = await checkHealth();
    if (!isHealthy) {
      throw new Error("Backend service is unavailable. Please make sure it's running on port 8000.");
    }
  }

  try {
    // frontend/src/api.ts - توی askBackend
   const payload: any = {
    session_id: userId,  // این userId همون sessionId هست
    message: message || "Analyze this image",
   };

    if (image) {
      if (image.includes("base64,")) {
        payload.image = image.split("base64,")[1];
      } else {
        payload.image = image;
      }
    }

    const chatUrl = `${API_URL}/chat/send`;

    console.log("📤 Sending to:", chatUrl);

    const response = await axios.post(chatUrl, payload, {
      timeout: 300000, // Increased from 180s to 300s (5 minutes) for complex image analysis
      headers: getAuthHeaders(),
    });

    let replyText = "";

    if (typeof response.data?.reply === 'string' && response.data.reply.length > 0) {
      replyText = response.data.reply;
    } else if (response.data?.final_output) {
      replyText = response.data.final_output;
    } else {
      throw new Error("Invalid response format from backend");
    }

    notifyStatusChange("connected");

    // Return both reply and structured analysis if available
    return {
      reply: replyText,
      analysis: response.data?.analysis || null
    };

  } catch (error: any) {
    console.error("❌ Error:", error.message);

    if (error.code === 'ECONNABORTED') {
      throw new Error("Request timed out. Please try again.");
    }

    backendHealthy = false;
    notifyStatusChange("error");
    throw new Error(`Backend error: ${error.message}`);
  }
};

// ============================================================
// Chat History API
// ============================================================

export const getChatHistory = async (userId: string) => {
  try {
    console.log("📜 Fetching chat history for:", userId);
    const response = await axios.post(`${API_URL}/chat/history`, {
      session_id: userId
    }, {
      timeout: 10000,
      headers: getAuthHeaders(),
    });
    
    console.log("📜 History response:", response.data);
    return response.data?.history || [];
    
  } catch (error: any) {
    console.error("❌ Failed to get history:", error.message);
    return [];
  }
};

export const clearChatHistory = async (userId: string) => {
  try {
    console.log("🗑️ Clearing chat history for:", userId);
    const response = await axios.post(`${API_URL}/chat/clear`, {
      session_id: userId
    }, {
      timeout: 10000,
      headers: getAuthHeaders(),
    });
    
    console.log("🗑️ Clear response:", response.data);
    return response.data?.message || "Chat cleared";
    
  } catch (error: any) {
    console.error("❌ Failed to clear history:", error.message);
    throw new Error("Failed to clear chat history");
  }
};

// ============================================================
// Auth API
// ============================================================

export const loginUser = async (username: string, password: string) => {
  try {
    const response = await axios.post(`${API_URL}/auth/login`, {
      username,
      password
    }, {
      timeout: 10000,
      headers: { 'Content-Type': 'application/json' }
    });
    return response.data;
  } catch (error: any) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error("Login failed. Please try again.");
  }
};

export const registerUser = async (username: string, password: string, profile?: any) => {
  try {
    const response = await axios.post(`${API_URL}/auth/register`, {
      username,
      password,
      profile: profile || {}
    }, {
      timeout: 10000,
      headers: { 'Content-Type': 'application/json' }
    });
    return response.data;
  } catch (error: any) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error("Registration failed. Please try again.");
  }
};

export const logoutUser = async () => {
  try {
    await axios.post(`${API_URL}/auth/logout`, {}, {
      headers: getAuthHeaders()
    });
  } catch (e) {
    // ignore errors on logout
    console.log("Logout API call failed (ignored):", e);
  }
  // Clear local storage regardless
  localStorage.removeItem("smarthealth_token");
  localStorage.removeItem("smarthealth_username");
  localStorage.removeItem("smarthealth_profile");
};

export const checkAuth = async () => {
  try {
    const response = await axios.get(`${API_URL}/auth/check`, {
      timeout: 5000,
      headers: getAuthHeaders()
    });
    return response.data;
  } catch {
    return { authenticated: false, user: null, profile: null };
  }
};

export const updateProfile = async (profile: any) => {
  try {
    const response = await axios.put(`${API_URL}/auth/profile`, 
      { profile },
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error: any) {
    if (error.response?.data?.detail) {
      throw new Error(error.response.data.detail);
    }
    throw new Error("Failed to update profile");
  }
};

// ============================================================
// Connection Status
// ============================================================

export const testConnection = async (): Promise<{ success: boolean; message: string }> => {
  try {
    const isHealthy = await checkHealth();
    return {
      success: isHealthy,
      message: isHealthy 
        ? "✅ Backend connected successfully" 
        : "❌ Backend not healthy"
    };
  } catch (error: any) {
    return {
      success: false,
      message: `❌ Cannot reach backend: ${error.message}`
    };
  }
};

export const onConnectionStatusChange = (listener: (status: ConnectionStatus) => void) => {
  statusListeners.push(listener);
  // Immediately notify with current status
  listener(connectionStatus);
  // Return unsubscribe function
  return () => {
    const index = statusListeners.indexOf(listener);
    if (index > -1) statusListeners.splice(index, 1);
  };
};

export const getConnectionStatus = (): ConnectionStatus => connectionStatus;
export const getBackendHealth = () => backendHealthy;

// ============================================================
// Analysis History API
// ============================================================

export const getAnalysisHistory = async (limit: number = 20) => {
  try {
    const response = await axios.get(`${API_URL}/patient/analysis-history?limit=${limit}`, {
      timeout: 10000,
      headers: getAuthHeaders()
    });
    return response.data;
  } catch (error: any) {
    console.error("❌ Failed to get analysis history:", error.message);
    return { history: [], total: 0 };
  }
};

export const downloadAnalysisReport = async (analysisId: string) => {
  try {
    const response = await axios.get(`${API_URL}/patient/analysis-history/${analysisId}/report/download`, {
      timeout: 30000,
      headers: getAuthHeaders(),
      responseType: 'blob'
    });

    // Determine file extension from content type
    const contentType = response.headers['content-type'];
    const extension = contentType === 'application/pdf' ? 'pdf' : 'txt';

    // Create download link
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `smarthealth_report_${analysisId}.${extension}`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    
    return { success: true };
  } catch (error: any) {
    console.error("❌ Failed to download report:", error.message);
    throw new Error("Failed to download report");
  }
};

export const compareAnalyses = async (analysisId1: string, analysisId2: string) => {
  try {
    const response = await axios.post(`${API_URL}/patient/analysis-history/compare`, {
      analysis_id_1: analysisId1,
      analysis_id_2: analysisId2
    }, {
      timeout: 10000,
      headers: getAuthHeaders()
    });
    return response.data;
  } catch (error: any) {
    console.error("❌ Failed to compare analyses:", error.message);
    // Preserve the full error object for better error handling
    if (error.response) {
      throw error; // Throw the full error with response data
    } else {
      throw new Error("Failed to compare analyses");
    }
  }
};

// Auto health check on load
setTimeout(() => {
  checkHealth().catch(console.error);
}, 1000);
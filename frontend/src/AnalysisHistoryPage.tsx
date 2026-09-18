// AnalysisHistoryPage.tsx
import React, { useState, useEffect } from "react";
import { getAnalysisHistory, downloadAnalysisReport, compareAnalyses } from "./api";

interface AnalysisHistoryPageProps {
  token: string;
  userId: string;
  onBack: () => void;
}

interface AnalysisRecord {
  analysis_id: string;
  timestamp: string;
  predicted_class: string;
  confidence: number;
  top3_predictions: any[];
  screening_score: number;
  screening_level: string;
  user_symptoms: string;
  medical_context?: string;
  structured_analysis?: any;
  report_available?: boolean;
}

export default function AnalysisHistoryPage({ token, userId, onBack }: AnalysisHistoryPageProps) {
  const [history, setHistory] = useState<AnalysisRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedAnalysis, setSelectedAnalysis] = useState<AnalysisRecord | null>(null);
  const [showComparison, setShowComparison] = useState(false);
  const [compareId1, setCompareId1] = useState("");
  const [compareId2, setCompareId2] = useState("");
  const [comparisonResult, setComparisonResult] = useState<any>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getAnalysisHistory(20);
      if (data.history) {
        // Process the data to ensure proper format
        const processedHistory = data.history.map((analysis: any) => ({
          ...analysis,
          // Ensure top3_predictions is properly formatted
          top3_predictions: analysis.top3_predictions || [],
          // Extract confidence from nested structure if needed
          confidence: analysis.confidence || analysis.model?.confidence || 0,
          // Extract predicted class from nested structure if needed
          predicted_class: typeof analysis.predicted_class === 'string' 
            ? analysis.predicted_class 
            : analysis.model?.predicted_class || "Unknown",
          // Extract screening level from nested structure if needed
          screening_level: analysis.screening_level || analysis.risk_assessment?.screening_level || "unknown",
          // Ensure user_symptoms is a string
          user_symptoms: typeof analysis.user_symptoms === 'string' 
            ? analysis.user_symptoms 
            : analysis.user_symptoms ? JSON.stringify(analysis.user_symptoms) : "",
          // Ensure medical_context is a string
          medical_context: typeof analysis.medical_context === 'string' 
            ? analysis.medical_context 
            : analysis.medical_context ? JSON.stringify(analysis.medical_context) : ""
        }));
        setHistory(processedHistory);
      } else {
        setError("No analysis history found");
      }
    } catch (e) {
      setError("Failed to load analysis history");
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = async () => {
    if (!compareId1 || !compareId2 || compareId1 === compareId2) {
      setError("Please select two different analyses to compare");
      return;
    }

    try {
      const data = await compareAnalyses(compareId1, compareId2);
      setComparisonResult(data);
      setShowComparison(true);
      setError(""); // Clear any previous errors
    } catch (e: any) {
      console.error("Comparison error:", e);
      if (e.response) {
        setError(`Failed to compare analyses: ${e.response.data.detail || e.response.statusText}`);
      } else if (e.message) {
        setError(`Failed to compare analyses: ${e.message}`);
      } else {
        setError("Failed to compare analyses. Please try again.");
      }
    }
  };

  const handleDownloadReport = async (analysisId: string) => {
    try {
      await downloadAnalysisReport(analysisId);
    } catch (e) {
      setError("Failed to download report");
      console.error(e);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  };

  const getScreeningLevelColor = (level: string) => {
    switch (level) {
      case "urgent": return "#ef4444";
      case "high": return "#f97316";
      case "medium": return "#eab308";
      case "low": return "#22c55e";
      default: return "#6b7280";
    }
  };

  if (loading) {
    return (
      <div style={{ 
        flex: 1, 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center',
        height: '100%',
        overflow: 'auto'
      }}>
        <p>Loading analysis history...</p>
      </div>
    );
  }

  return (
    <div style={{ 
      flex: 1, 
      display: 'flex', 
      flexDirection: 'column', 
      padding: '20px', 
      overflowY: 'auto', 
      height: '100%',
      maxHeight: 'calc(100vh - 70px)' // Subtract nav height
    }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px' }}>
        <button 
          onClick={onBack}
          style={{ 
            background: 'transparent', 
            border: 'none', 
            color: 'var(--text-main)', 
            cursor: 'pointer',
            marginRight: '15px',
            fontSize: '16px'
          }}
        >
          ← Back
        </button>
        <h2 style={{ margin: 0 }}>Analysis History</h2>
      </div>

      {error && (
        <div style={{ 
          padding: '12px', 
          borderRadius: '10px', 
          marginBottom: '20px', 
          background: 'rgba(239,68,68,0.1)', 
          color: '#ef4444',
          border: '1px solid rgba(239,68,68,0.2)'
        }}>
          {error}
        </div>
      )}

      {!showComparison ? (
        <>
          <div style={{ marginBottom: '20px' }}>
            <button 
              onClick={() => setShowComparison(true)}
              style={{
                padding: '10px 20px',
                background: 'var(--primary)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              Compare Analyses
            </button>
          </div>

          {history.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              <p>No analysis history available yet.</p>
              <p>Upload and analyze skin images to build your history.</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '15px', paddingBottom: '20px' }}>
              {history.map((analysis) => (
                <div 
                  key={analysis.analysis_id}
                  onClick={() => setSelectedAnalysis(analysis)}
                  style={{
                    background: 'var(--bg-card)',
                    padding: '20px',
                    borderRadius: '12px',
                    border: '1px solid var(--border)',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--primary)'}
                  onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border)'}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontSize: '24px' }}>🔬</span>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '16px' }}>
                          {analysis.predicted_class || 'Unknown'}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          {formatDate(analysis.timestamp)}
                        </div>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ 
                        fontWeight: 600, 
                        color: getScreeningLevelColor(analysis.screening_level),
                        fontSize: '14px'
                      }}>
                        {analysis.screening_level ? analysis.screening_level.toUpperCase() : 'N/A'}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        {analysis.confidence ? `${(analysis.confidence * 100).toFixed(1)}% confidence` : 'N/A confidence'}
                      </div>
                    </div>
                  </div>

                  {analysis.user_symptoms && (
                    <div style={{ 
                      marginTop: '10px', 
                      padding: '8px 12px', 
                      background: 'var(--bg-app)', 
                      borderRadius: '6px',
                      fontSize: '13px',
                      color: 'var(--text-muted)'
                    }}>
                      Symptoms: {typeof analysis.user_symptoms === 'string' 
                        ? (analysis.user_symptoms.length > 100 ? analysis.user_symptoms.substring(0, 100) + '...' : analysis.user_symptoms)
                        : JSON.stringify(analysis.user_symptoms).substring(0, 100) + '...'}
                    </div>
                  )}

                  {analysis.top3_predictions && analysis.top3_predictions.length > 0 && (
                    <div style={{ marginTop: '10px', fontSize: '12px' }}>
                      <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>Top predictions:</div>
                      {analysis.top3_predictions.slice(0, 3).map((pred, idx) => {
                        // Handle different possible structures for predictions
                        const className = pred.class || pred.name || pred.predicted_class || "Unknown";
                        const confidence = pred.confidence || pred.score || pred.probability || 0;
                        return (
                          <div key={idx} style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>{className}</span>
                            <span>{confidence ? `${(confidence * 100).toFixed(1)}%` : 'N/A'}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  <div style={{ marginTop: '10px', display: 'flex', gap: '8px' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDownloadReport(analysis.analysis_id);
                      }}
                      style={{
                        padding: '6px 12px',
                        background: 'var(--primary)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                    >
                      Download Report
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <div style={{ background: 'var(--bg-card)', padding: '20px', borderRadius: '12px', border: '1px solid var(--border)' }}>
          <h3 style={{ marginTop: 0 }}>Compare Analyses</h3>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: 500 }}>
                First Analysis
              </label>
              <select
                value={compareId1}
                onChange={(e) => setCompareId1(e.target.value)}
                style={{ 
                  width: '100%', 
                  padding: '10px', 
                  borderRadius: '8px', 
                  border: '1px solid var(--border)',
                  background: 'var(--bg-app)',
                  color: 'var(--text-main)'
                }}
              >
                <option value="">Select analysis...</option>
                {history.map((analysis) => (
                  <option key={analysis.analysis_id} value={analysis.analysis_id}>
                    {formatDate(analysis.timestamp)} - {analysis.predicted_class}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: 500 }}>
                Second Analysis
              </label>
              <select
                value={compareId2}
                onChange={(e) => setCompareId2(e.target.value)}
                style={{ 
                  width: '100%', 
                  padding: '10px', 
                  borderRadius: '8px', 
                  border: '1px solid var(--border)',
                  background: 'var(--bg-app)',
                  color: 'var(--text-main)'
                }}
              >
                <option value="">Select analysis...</option>
                {history.map((analysis) => (
                  <option key={analysis.analysis_id} value={analysis.analysis_id}>
                    {formatDate(analysis.timestamp)} - {analysis.predicted_class}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button 
              onClick={handleCompare}
              disabled={!compareId1 || !compareId2}
              style={{
                padding: '10px 20px',
                background: compareId1 && compareId2 ? 'var(--primary)' : 'var(--border)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: compareId1 && compareId2 ? 'pointer' : 'not-allowed',
                fontSize: '14px'
              }}
            >
              Compare
            </button>
            <button 
              onClick={() => setShowComparison(false)}
              style={{
                padding: '10px 20px',
                background: 'transparent',
                color: 'var(--text-main)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              Cancel
            </button>
          </div>

          {comparisonResult && (
            <div style={{ marginTop: '20px', padding: '15px', background: 'var(--bg-app)', borderRadius: '8px' }}>
              <h4 style={{ marginTop: 0 }}>Comparison Results</h4>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '15px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    {formatDate(comparisonResult.analysis_1.timestamp)}
                  </div>
                  <div style={{ fontWeight: 600 }}>{comparisonResult.analysis_1.predicted_class || 'Unknown'}</div>
                  <div style={{ fontSize: '14px' }}>
                    {comparisonResult.analysis_1.confidence ? `${(comparisonResult.analysis_1.confidence * 100).toFixed(1)}% confidence` : 'N/A confidence'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                    {formatDate(comparisonResult.analysis_2.timestamp)}
                  </div>
                  <div style={{ fontWeight: 600 }}>{comparisonResult.analysis_2.predicted_class || 'Unknown'}</div>
                  <div style={{ fontSize: '14px' }}>
                    {comparisonResult.analysis_2.confidence ? `${(comparisonResult.analysis_2.confidence * 100).toFixed(1)}% confidence` : 'N/A confidence'}
                  </div>
                </div>
              </div>

              {comparisonResult.differences && comparisonResult.differences.length > 0 ? (
                <div>
                  <div style={{ fontWeight: 600, marginBottom: '8px' }}>Differences:</div>
                  {comparisonResult.differences.map((diff: any, idx: number) => (
                    <div key={idx} style={{ 
                      padding: '8px', 
                      background: diff.significance === 'high' ? 'rgba(239,68,68,0.1)' : 'rgba(234,179,8,0.1)',
                      borderRadius: '4px',
                      marginBottom: '5px',
                      fontSize: '13px'
                    }}>
                      <strong>{diff.type.replace('_', ' ')}:</strong> {diff.from} → {diff.to}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: 'var(--text-muted)' }}>No significant differences detected.</div>
              )}

              {comparisonResult.time_difference_days !== undefined && (
                <div style={{ marginTop: '10px', fontSize: '13px', color: 'var(--text-muted)' }}>
                  Time between analyses: {comparisonResult.time_difference_days} days
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {selectedAnalysis && (
        <div 
          onClick={() => setSelectedAnalysis(null)}
          style={{ 
            position: 'fixed', 
            top: 0, 
            left: 0, 
            right: 0, 
            bottom: 0, 
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1000,
            padding: '20px'
          }}
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            style={{ 
              background: 'var(--bg-card)', 
              padding: '30px', 
              borderRadius: '16px', 
              maxWidth: '600px',
              width: '100%',
              maxHeight: '85vh',
              overflowY: 'auto',
              border: '1px solid var(--border)',
              boxShadow: '0 10px 40px rgba(0,0,0,0.3)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0, fontSize: '20px' }}>Analysis Details</h3>
              <button 
                onClick={() => setSelectedAnalysis(null)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  fontSize: '24px',
                  cursor: 'pointer',
                  padding: '0',
                  lineHeight: '1'
                }}
              >
                ×
              </button>
            </div>
            
            <div style={{ marginBottom: '15px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Date & Time</label>
              <div style={{ fontSize: '15px', fontWeight: 500 }}>{formatDate(selectedAnalysis.timestamp)}</div>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Predicted Class</label>
              <div style={{ fontWeight: 600, fontSize: '18px', color: 'var(--primary)' }}>{selectedAnalysis.predicted_class}</div>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Confidence</label>
              <div style={{ fontSize: '20px', fontWeight: 600 }}>
                {selectedAnalysis.confidence ? `${(selectedAnalysis.confidence * 100).toFixed(2)}%` : 'N/A'}
              </div>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Screening Level</label>
              <div style={{ 
                fontWeight: 600, 
                color: getScreeningLevelColor(selectedAnalysis.screening_level),
                fontSize: '16px',
                padding: '8px 12px',
                background: `${getScreeningLevelColor(selectedAnalysis.screening_level)}20`,
                borderRadius: '6px',
                display: 'inline-block'
              }}>
                {selectedAnalysis.screening_level ? selectedAnalysis.screening_level.toUpperCase() : 'N/A'}
              </div>
            </div>

            {selectedAnalysis.screening_score !== undefined && (
              <div style={{ marginBottom: '15px' }}>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Screening Score</label>
                <div style={{ fontSize: '16px', fontWeight: 500 }}>{selectedAnalysis.screening_score.toFixed(1)}</div>
              </div>
            )}

            {selectedAnalysis.top3_predictions && selectedAnalysis.top3_predictions.length > 0 && (
              <div style={{ marginBottom: '15px' }}>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Top Predictions</label>
                <div style={{ background: 'var(--bg-app)', padding: '12px', borderRadius: '8px' }}>
                  {selectedAnalysis.top3_predictions.map((pred, idx) => {
                    const className = pred.class || pred.name || pred.predicted_class || "Unknown";
                    const confidence = pred.confidence || pred.score || pred.probability || 0;
                    return (
                      <div key={idx} style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        padding: '8px 0',
                        borderBottom: idx < selectedAnalysis.top3_predictions.length - 1 ? '1px solid var(--border)' : 'none'
                      }}>
                        <span style={{ fontWeight: 500 }}>{className}</span>
                        <span style={{ fontWeight: 600, color: confidence > 0.7 ? '#22c55e' : confidence > 0.4 ? '#eab308' : '#ef4444' }}>
                          {confidence ? `${(confidence * 100).toFixed(2)}%` : 'N/A'}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {selectedAnalysis.user_symptoms && (
              <div style={{ marginBottom: '15px' }}>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Reported Symptoms</label>
                <div style={{ 
                  background: 'var(--bg-app)', 
                  padding: '12px', 
                  borderRadius: '8px',
                  lineHeight: '1.6',
                  fontSize: '14px'
                }}>
                  {typeof selectedAnalysis.user_symptoms === 'string' 
                    ? selectedAnalysis.user_symptoms 
                    : JSON.stringify(selectedAnalysis.user_symptoms, null, 2)}
                </div>
              </div>
            )}

            {selectedAnalysis.medical_context && (
              <div style={{ marginBottom: '15px' }}>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Medical Context</label>
                <div style={{ 
                  background: 'var(--bg-app)', 
                  padding: '12px', 
                  borderRadius: '8px',
                  lineHeight: '1.6',
                  fontSize: '14px'
                }}>
                  {typeof selectedAnalysis.medical_context === 'string' 
                    ? selectedAnalysis.medical_context 
                    : JSON.stringify(selectedAnalysis.medical_context, null, 2)}
                </div>
              </div>
            )}

            {selectedAnalysis.structured_analysis?.explainability && (
              <div style={{ marginBottom: '15px' }}>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Explainability Analysis</label>
                <div style={{ 
                  background: 'var(--bg-app)', 
                  padding: '12px', 
                  borderRadius: '8px',
                  lineHeight: '1.6',
                  fontSize: '14px'
                }}>
                  {typeof selectedAnalysis.structured_analysis.explainability === 'string'
                    ? selectedAnalysis.structured_analysis.explainability
                    : selectedAnalysis.structured_analysis.explainability.explanation || JSON.stringify(selectedAnalysis.structured_analysis.explainability, null, 2)}
                </div>
              </div>
            )}

            {selectedAnalysis.structured_analysis?.risk_assessment?.recommendations && (
              <div style={{ marginBottom: '15px' }}>
                <label style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Recommendations</label>
                <div style={{ 
                  background: 'var(--bg-app)', 
                  padding: '12px', 
                  borderRadius: '8px',
                  lineHeight: '1.6',
                  fontSize: '14px'
                }}>
                  {Array.isArray(selectedAnalysis.structured_analysis.risk_assessment.recommendations) 
                    ? selectedAnalysis.structured_analysis.risk_assessment.recommendations.map((rec: string, idx: number) => (
                      <div key={idx} style={{ marginBottom: idx < selectedAnalysis.structured_analysis.risk_assessment.recommendations.length - 1 ? '8px' : '0' }}>
                        • {rec}
                      </div>
                    ))
                    : typeof selectedAnalysis.structured_analysis.risk_assessment.recommendations === 'string'
                    ? selectedAnalysis.structured_analysis.risk_assessment.recommendations
                    : JSON.stringify(selectedAnalysis.structured_analysis.risk_assessment.recommendations, null, 2)}
                </div>
              </div>
            )}

            <div style={{ marginBottom: '15px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Analysis ID</label>
              <div style={{ 
                fontSize: '12px', 
                fontFamily: 'monospace',
                background: 'var(--bg-app)',
                padding: '8px',
                borderRadius: '6px',
                wordBreak: 'break-all'
              }}>
                {selectedAnalysis.analysis_id}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
              <button 
                onClick={() => setSelectedAnalysis(null)}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: 'var(--primary)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 600
                }}
              >
                Close
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDownloadReport(selectedAnalysis.analysis_id);
                }}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: 'transparent',
                  color: 'var(--text-main)',
                  border: '1px solid var(--border)',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 600
                }}
              >
                Download Report
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
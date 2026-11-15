import React, { useState, useEffect } from 'react';
import {
  X,
  Building,
  MapPin,
  ExternalLink,
  Sparkles,
  Quote,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Layers,
  Award,
  AlertTriangle,
  Globe,
  RefreshCw,
  Wrench,
} from 'lucide-react';
import { Lead } from '../types';
import { api } from '../services/api';

interface LeadDetailModalProps {
  lead: Lead | null;
  onClose: () => void;
  onLeadUpdated: (updatedLead: Lead) => void;
}

export const LeadDetailModal: React.FC<LeadDetailModalProps> = ({
  lead,
  onClose,
  onLeadUpdated,
}) => {
  const [evaluating, setEvaluating] = useState(false);
  const [verifyingSource, setVerifyingSource] = useState(false);
  const [sourceVerifyMsg, setSourceVerifyMsg] = useState<{ text: string; isError: boolean } | null>(null);
  const [selectedProvider, setSelectedProvider] = useState('auto');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!lead) return null;

  const handleVerifySource = async () => {
    if (!lead.source_url) {
      setSourceVerifyMsg({ text: 'This lead has no source URL to verify.', isError: true });
      return;
    }
    setVerifyingSource(true);
    setSourceVerifyMsg(null);
    try {
      const res = await api.verifySource(lead.id);
      onLeadUpdated(res.lead);
      setSourceVerifyMsg({ text: res.message || 'Source page verified successfully.', isError: false });
    } catch (err: any) {
      setSourceVerifyMsg({ text: err.message || 'Source page verification failed.', isError: true });
    } finally {
      setVerifyingSource(false);
    }
  };

  const handleReanalyze = async () => {
    setEvaluating(true);
    setError(null);
    try {
      const res = await api.analyzeSingleLead(lead.id, selectedProvider);
      onLeadUpdated(res.lead);
    } catch (err: any) {
      setError(err.message || 'Analysis failed.');
    } finally {
      setEvaluating(false);
    }
  };

  const breakdown = lead.score_breakdown || {};
  const isProcessed = lead.status === 'processed';

  // 5-Factor Score points
  const fRelevance = breakdown.service_relevance ?? 0;
  const fIntent = breakdown.buying_intent ?? 0;
  const fClarity = breakdown.requirement_clarity ?? 0;
  const fFeatures = breakdown.specific_features ?? 0;
  const fTimeline = breakdown.timeline_urgency ?? 0;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-header-titles">
            <div className="modal-eyebrow">Lead Intelligence &amp; Procurement Audit · ID #{lead.id}</div>
            <h2 className="modal-title">{lead.business_name}</h2>
            <div className="modal-meta-row">
              {lead.record_type === 'live_discovery' ? (
                <span className="meta-pill badge-live">
                  <Sparkles size={12} /> Live Discovered Opportunity
                </span>
              ) : lead.verification_status === 'official_tender' ? (
                <span className="meta-pill badge-verified">
                  <ShieldCheck size={12} /> Official-Source-Confirmed Tender
                </span>
              ) : lead.verification_status === 'source_domain_confirmed_tender_unverified' ? (
                <span className="meta-pill badge-domain-confirmed" title="Portal domain confirmed official, but tender document and closing date not independently verified">
                  <ShieldCheck size={12} /> Domain Confirmed · Tender Unverified
                </span>
              ) : lead.verification_status === 'demo' || lead.record_type === 'demo' ? (
                <span className="meta-pill badge-demo">Demo Benchmark</span>
              ) : (
                <span className="meta-pill badge-unverified">
                  <AlertTriangle size={12} /> Unverified Source
                </span>
              )}
              {lead.location && (
                <span className="meta-pill">
                  <MapPin size={13} /> {lead.location}
                </span>
              )}
              {lead.category && (
                <span className="meta-pill" style={{ fontWeight: 600 }}>
                  <Wrench size={13} /> Service: {lead.category}
                </span>
              )}
              <span className="meta-pill">
                <Building size={13} /> Source: {lead.source_name || 'Public Web'}
              </span>
              {lead.date_found && (
                <span className="meta-pill">
                  <Clock size={13} /> Reference Date: {lead.date_found}
                </span>
              )}
              {lead.source_url && (
                <a
                  href={lead.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="meta-link-btn"
                >
                  <ExternalLink size={13} /> Official Source Link
                </a>
              )}
            </div>
          </div>
          <button onClick={onClose} className="modal-close-btn" aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {error && <div className="alert-banner alert-error mb-4">{error}</div>}

          {/* GROUP 1: VERIFIED SOURCE FACTS (GROUND TRUTH) */}
          <div className="intelligence-group-card" style={{ marginBottom: '1.75rem', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: '10px', background: 'rgba(59, 130, 246, 0.02)', padding: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid rgba(59, 130, 246, 0.2)', paddingBottom: '0.625rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ShieldCheck size={18} style={{ color: '#2563eb' }} />
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#1e40af' }}>
                  Verified Source Facts (Ground Truth)
                </h3>
              </div>
              <span className="badge badge-verified badge-xs">
                Direct Source Public Record
              </span>
            </div>

            {/* Original Requirement */}
          <div className="detail-section">
            <h3 className="section-heading">Original Requirement Text</h3>
            <div className="requirement-box">
              <p>{lead.requirement}</p>
            </div>
          </div>

          {/* Provenance & Source Verification Audit */}
          <div className="detail-section">
            <h3 className="section-heading">Provenance &amp; Source Verification</h3>
            <div className="provenance-audit-card">
              <div className="provenance-row">
                <div className="provenance-item">
                  <span className="provenance-label">Record Classification:</span>
                  <span className="provenance-val">
                    {lead.record_type === 'live_discovery'
                      ? 'Live Discovered Commercial Opportunity'
                      : lead.record_type === 'official_tender'
                      ? 'Official-Source-Confirmed Public Tender'
                      : lead.record_type === 'demo'
                      ? 'Pre-seeded Demonstration Benchmark'
                      : lead.record_type === 'uploaded'
                      ? 'User-Uploaded Dataset'
                      : lead.record_type === 'sample'
                      ? 'Historical Sample Directory'
                      : 'Commercial Lead / Opportunity'}
                  </span>
                </div>
                <div className="provenance-item">
                  <span className="provenance-label">Verification Status:</span>
                  {lead.record_type === 'live_discovery' ? (
                    <span className="badge badge-live">
                      <Sparkles size={12} /> Live Discovered Opportunity
                    </span>
                  ) : lead.verification_status === 'official_tender' ? (
                    <span className="badge badge-verified">
                      <ShieldCheck size={12} /> Official-Source-Confirmed Tender
                    </span>
                  ) : lead.verification_status === 'source_domain_confirmed_tender_unverified' ? (
                    <span className="badge badge-domain-confirmed" title="Portal domain confirmed official, but tender document and closing date not independently verified">
                      <ShieldCheck size={12} /> Domain Confirmed · Tender Unverified
                    </span>
                  ) : lead.verification_status === 'demo' || lead.record_type === 'demo' ? (
                    <span className="badge badge-demo">Demo Benchmark</span>
                  ) : (
                    <span className="badge badge-unverified">
                      <AlertTriangle size={12} /> Unverified Source
                    </span>
                  )}
                </div>
              </div>

              {lead.source_title && (
                <div className="provenance-field">
                  <strong>Notice / Document Title: </strong>
                  <span>{lead.source_title}</span>
                </div>
              )}

              <div className="provenance-meta-grid">
                <div>
                  <strong>Originating Authority: </strong>
                  <span>{lead.source_name || 'Unspecified'}</span>
                </div>
                {lead.publication_date && (
                  <div>
                    <strong>Publication Date: </strong>
                    <span>{lead.publication_date}</span>
                  </div>
                )}
                {lead.verified_at && (
                  <div>
                    <strong>Verified Timestamp: </strong>
                    <span>{lead.verified_at}</span>
                  </div>
                )}
              </div>

              {lead.verification_notes && (
                <div className="verification-audit-box">
                  <ShieldCheck size={14} className="text-emerald" />
                  <span>{lead.verification_notes}</span>
                </div>
              )}
            </div>
          </div>

          {/* Phase 4: Source-Page Inspection & Intent Verification */}
          <div className="detail-section">
            <div className="section-header-flex" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <h3 className="section-heading" style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Globe size={16} className="text-blue" /> Source-Page Inspection &amp; Intent Verification
              </h3>
              <button
                type="button"
                onClick={handleVerifySource}
                disabled={verifyingSource || !lead.source_url}
                className="btn btn-secondary btn-sm"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8125rem' }}
                title={lead.source_url ? "Fetch destination page, verify SSRF security, and inspect HTML DOM for buyer vs seller signals" : "No source URL available"}
              >
                <RefreshCw size={13} className={verifyingSource ? "spinner-icon" : ""} />
                {verifyingSource ? "Inspecting Source..." : "Re-verify Source Page"}
              </button>
            </div>

            {sourceVerifyMsg && (
              <div
                style={{
                  padding: '0.625rem 0.875rem',
                  borderRadius: '6px',
                  marginBottom: '0.75rem',
                  fontSize: '0.8125rem',
                  background: sourceVerifyMsg.isError ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                  color: sourceVerifyMsg.isError ? '#ef4444' : '#10b981',
                  border: `1px solid ${sourceVerifyMsg.isError ? 'rgba(239, 68, 68, 0.25)' : 'rgba(16, 185, 129, 0.25)'}`,
                }}
              >
                {sourceVerifyMsg.text}
              </div>
            )}

            <div className="provenance-audit-card">
              <div className="provenance-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                <div className="provenance-item">
                  <span className="provenance-label">Page Classification:</span>
                  {lead.source_page_type === 'buyer_procurement' ? (
                    <span className="badge badge-verified" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <ShieldCheck size={12} /> Confirmed Buyer Procurement
                    </span>
                  ) : lead.source_page_type === 'seller_agency' ? (
                    <span className="badge" style={{ background: 'rgba(249, 115, 22, 0.15)', color: '#f97316', border: '1px solid rgba(249, 115, 22, 0.3)' }}>
                      Disqualified: IT Agency / Seller
                    </span>
                  ) : lead.source_page_type === 'portfolio' ? (
                    <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#a855f7', border: '1px solid rgba(168, 85, 247, 0.3)' }}>
                      Disqualified: Portfolio / Case Study
                    </span>
                  ) : lead.source_page_type === 'directory' ? (
                    <span className="badge" style={{ background: 'rgba(234, 179, 8, 0.15)', color: '#eab308', border: '1px solid rgba(234, 179, 8, 0.3)' }}>
                      Disqualified: Directory / Aggregator
                    </span>
                  ) : lead.source_page_type === 'unknown' ? (
                    <span className="badge badge-unverified">Inconclusive / Unknown</span>
                  ) : (
                    <span className="badge badge-neutral">Not Yet Inspected</span>
                  )}
                </div>

                <div className="provenance-item">
                  <span className="provenance-label">HTTP Fetch Status:</span>
                  <span className="provenance-val font-mono" style={{ fontSize: '0.8125rem' }}>
                    {lead.source_fetch_status === '200_ok' ? (
                      <span style={{ color: '#10b981' }}>200 OK (HTML Verified)</span>
                    ) : lead.source_fetch_status === 'timeout' ? (
                      <span style={{ color: '#f59e0b' }}>Timed Out (&gt;4.0s)</span>
                    ) : lead.source_fetch_status === 'blocked_403' ? (
                      <span style={{ color: '#ef4444' }}>403 Forbidden (Origin Blocked)</span>
                    ) : lead.source_fetch_status === 'not_found_404' ? (
                      <span style={{ color: '#ef4444' }}>404 Not Found</span>
                    ) : lead.source_fetch_status === 'ssrf_blocked' ? (
                      <span style={{ color: '#ef4444' }}>SSRF Blocked (Restricted Target)</span>
                    ) : lead.source_fetch_status === 'oversized' ? (
                      <span style={{ color: '#f59e0b' }}>Oversized (&gt;512 KB Cap)</span>
                    ) : lead.source_fetch_status === 'static_benchmark' ? (
                      <span style={{ color: '#6366f1' }}>Static Benchmark</span>
                    ) : (
                      lead.source_fetch_status || 'Not yet inspected'
                    )}
                  </span>
                </div>

                <div className="provenance-item">
                  <span className="provenance-label">Last Source Inspection:</span>
                  <span className="provenance-val text-muted" style={{ fontSize: '0.8125rem' }}>
                    {lead.source_page_type && lead.source_verified_at ? new Date(lead.source_verified_at).toLocaleString() : 'Not yet inspected'}
                  </span>
                </div>
              </div>

              {lead.source_evidence_snippet ? (
                <div style={{ marginTop: '0.875rem', paddingTop: '0.875rem', borderTop: '1px solid var(--border-color, #e2e8f0)' }}>
                  <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted, #64748b)', marginBottom: '0.35rem', fontWeight: 600 }}>
                    Extracted Source Document Evidence
                  </div>
                  <blockquote style={{ margin: 0, padding: '0.5rem 0.75rem', background: 'rgba(0,0,0,0.02)', borderLeft: '3px solid #3b82f6', borderRadius: '4px', fontStyle: 'italic', fontSize: '0.875rem' }}>
                    "{lead.source_evidence_snippet}"
                  </blockquote>
                </div>
              ) : (
                <div style={{ marginTop: '0.75rem', fontSize: '0.8125rem', color: 'var(--text-muted, #64748b)' }}>
                  {lead.source_url ? "No HTML snippet extracted yet. Click 'Re-verify Source Page' to inspect the live website." : "No source URL associated with this record."}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* GROUP 2: AI PROCUREMENT ASSESSMENT & SCORING (ALGORITHMIC) */}
        <div className="intelligence-group-card" style={{ border: '1px solid rgba(147, 51, 234, 0.3)', borderRadius: '10px', background: 'rgba(147, 51, 234, 0.02)', padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid rgba(147, 51, 234, 0.2)', paddingBottom: '0.625rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Sparkles size={18} style={{ color: '#9333ea' }} />
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#7e22ce' }}>
                AI Procurement Assessment &amp; Scoring (Algorithmic)
              </h3>
            </div>
            <span className="badge badge-live badge-xs">
              Deterministic 5-Factor Rubric
            </span>
          </div>

          {/* Top Score Banner */}
          <div className="score-overview-banner" style={{ marginBottom: '1.25rem' }}>
            <div className="score-overview-left">
              <div className="score-circle-large">
                <span className="score-num">{isProcessed ? lead.lead_score : '-'}</span>
                <span className="score-denom">/100</span>
              </div>
              <div className="score-banner-text">
                <div className="priority-badge-row">
                  <span
                    className={`badge badge-lg ${
                      lead.priority === 'High'
                        ? 'badge-high'
                        : lead.priority === 'Medium'
                        ? 'badge-medium'
                        : 'badge-low'
                    }`}
                  >
                    {lead.priority || 'Low'} Priority
                  </span>
                  <span
                    className={`badge badge-lg ${
                      lead.buying_intent === 'Active'
                        ? 'badge-active'
                        : lead.buying_intent === 'Potential'
                        ? 'badge-potential'
                        : 'badge-neutral'
                    }`}
                  >
                    {lead.buying_intent || 'Unclear'} Intent
                  </span>
                  {lead.is_exported === 1 ? (
                    <span className="badge badge-exported badge-lg">
                      <CheckCircle2 size={13} /> Exported
                    </span>
                  ) : (
                    <span className="badge badge-not-exported badge-lg">
                      <Clock size={13} /> Not Yet Exported
                    </span>
                  )}
                </div>
                <p className="score-caption text-sm text-muted">
                  Deterministic 5-factor procurement rubric score based on service relevance, buying intent, scope clarity, features, and timeline evidence.
                </p>
              </div>
            </div>

            <div className="score-overview-actions">
              <select
                className="form-select form-select-sm"
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
                disabled={evaluating}
              >
                <option value="auto">Auto AI Provider</option>
                <option value="openai">OpenAI (gpt-4o-mini)</option>
                <option value="gemini">Google Gemini</option>
                <option value="fallback">Rule-Based NLP (Deterministic)</option>
              </select>
              <button
                onClick={handleReanalyze}
                disabled={evaluating}
                className="btn btn-primary btn-sm btn-reanalyze"
              >
                {evaluating ? (
                  <>
                    <span className="spinner-icon"></span> Evaluating...
                  </>
                ) : (
                  <>
                    <Sparkles size={14} /> {isProcessed ? 'Re-Evaluate Lead' : 'Evaluate with AI'}
                  </>
                )}
              </button>
            </div>
          </div>

          {/* AI Extracted Verbatim Evidence */}
          <div className="detail-section">
            <div className="verbatim-evidence-card">
              <div className="evidence-header">
                <div className="evidence-title-group">
                  <Quote size={18} className="text-blue" />
                  <h4>Verbatim Evidence Extracted</h4>
                </div>
                <span className="evidence-guarantee">
                  <ShieldCheck size={14} /> Zero-Fabrication Substring Proof
                </span>
              </div>
              <blockquote className="evidence-quote">
                "{lead.evidence || (isProcessed ? 'No explicit timeline or feature substring isolated.' : 'Pending evaluation.')}"
              </blockquote>
              {lead.summary && (
                <div className="ai-summary-note">
                  <strong>Executive Summary: </strong>
                  <span>{lead.summary}</span>
                </div>
              )}
            </div>
          </div>

          {/* 5-Factor Lead Scoring Rubric */}
          <div className="detail-section">
            <h3 className="section-heading">5-Factor Scoring Rubric Audit Trail</h3>
            <div className="rubric-grid">
              {/* Factor 1: Service Relevance (30 pts) */}
              <div className="rubric-card">
                <div className="rubric-header">
                  <span className="rubric-name">1. Service Relevance</span>
                  <span className="rubric-score font-mono">{fRelevance} / 30 pts</span>
                </div>
                <div className="rubric-track">
                  <div
                    className="rubric-fill bg-blue"
                    style={{ width: `${(fRelevance / 30) * 100}%` }}
                  ></div>
                </div>
                <p className="rubric-note text-xs text-muted">
                  {lead.relevance === 'Relevant' ? 'Matches requested service scope (+30)' : 'Out of scope (+0)'}
                </p>
              </div>

              {/* Factor 2: Buying Intent (30 pts) */}
              <div className="rubric-card">
                <div className="rubric-header">
                  <span className="rubric-name">2. Buying Intent</span>
                  <span className="rubric-score font-mono">{fIntent} / 30 pts</span>
                </div>
                <div className="rubric-track">
                  <div
                    className="rubric-fill bg-purple"
                    style={{ width: `${(fIntent / 30) * 100}%` }}
                  ></div>
                </div>
                <p className="rubric-note text-xs text-muted">
                  Active RFP/quote request (+30), potential (+15), or unclear (+0)
                </p>
              </div>

              {/* Factor 3: Requirement Clarity (20 pts) */}
              <div className="rubric-card">
                <div className="rubric-header">
                  <span className="rubric-name">3. Requirement Clarity</span>
                  <span className="rubric-score font-mono">{fClarity} / 20 pts</span>
                </div>
                <div className="rubric-track">
                  <div
                    className="rubric-fill bg-emerald"
                    style={{ width: `${(fClarity / 20) * 100}%` }}
                  ></div>
                </div>
                <p className="rubric-note text-xs text-muted">
                  High clarity &gt;120 chars (+20), moderate (+10), minimal (+0)
                </p>
              </div>

              {/* Factor 4: Technical Features (10 pts) */}
              <div className="rubric-card">
                <div className="rubric-header">
                  <span className="rubric-name">4. Technical Features</span>
                  <span className="rubric-score font-mono">{fFeatures} / 10 pts</span>
                </div>
                <div className="rubric-track">
                  <div
                    className="rubric-fill bg-amber"
                    style={{ width: `${(fFeatures / 10) * 100}%` }}
                  ></div>
                </div>
                <p className="rubric-note text-xs text-muted">
                  &gt;=2 specific features (+10), 1 feature (+5), none (+0)
                </p>
              </div>

              {/* Factor 5: Timeline & Urgency (10 pts) */}
              <div className="rubric-card">
                <div className="rubric-header">
                  <span className="rubric-name">5. Timeline / Urgency</span>
                  <span className="rubric-score font-mono">{fTimeline} / 10 pts</span>
                </div>
                <div className="rubric-track">
                  <div
                    className="rubric-fill bg-rose"
                    style={{ width: `${(fTimeline / 10) * 100}%` }}
                  ></div>
                </div>
                <p className="rubric-note text-xs text-muted">
                  Verified explicit deadline/urgency evidence (+10), none (+0)
                </p>
              </div>
            </div>

            {/* Audit Trail Explanation */}
            {lead.score_explanation && (
              <div className="score-explanation-box">
                <h4 className="explanation-title">Scoring Audit Trail</h4>
                <p className="explanation-text">{lead.score_explanation}</p>
              </div>
            )}
          </div>
        </div>
      </div>

        {/* Modal Footer */}
        <div className="modal-footer">
          <div className="modal-footer-left text-muted text-xs">
            {lead.analyzed_at && <span>Evaluated: {lead.analyzed_at}</span>}
          </div>
          <button onClick={onClose} className="btn btn-secondary">
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

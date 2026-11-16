import React, { useState, useEffect } from 'react';
import {
  Search,
  MapPin,
  Building,
  Wrench,
  Sparkles,
  ShieldCheck,
  ArrowRight,
  Check,
  AlertCircle,
  ExternalLink,
  AlertTriangle,
  Layers,
  BookmarkCheck,
} from 'lucide-react';
import { DiscoveryResult, DiscoveredLead } from '../types';
import { api } from '../services/api';

interface DiscoverySectionProps {
  onDiscoveryComplete: () => void;
  onInspectLead?: (id: number) => void;
  isLiveConnected?: boolean;
  state?: string;
  setState?: React.Dispatch<React.SetStateAction<string>>;
  category?: string;
  setCategory?: React.Dispatch<React.SetStateAction<string>>;
  service?: string;
  setService?: React.Dispatch<React.SetStateAction<string>>;
  result?: DiscoveryResult | null;
  setResult?: React.Dispatch<React.SetStateAction<DiscoveryResult | null>>;
}

// 28 Indian States & 8 Union Territories (Exclusively Indian Markets)
export const INDIAN_STATES_AND_UTS = [
  'Andaman and Nicobar Islands',
  'Andhra Pradesh',
  'Arunachal Pradesh',
  'Assam',
  'Bihar',
  'Chandigarh',
  'Chhattisgarh',
  'Dadra and Nagar Haveli and Daman and Diu',
  'Delhi',
  'Goa',
  'Gujarat',
  'Haryana',
  'Himachal Pradesh',
  'Jammu and Kashmir',
  'Jharkhand',
  'Karnataka',
  'Kerala',
  'Ladakh',
  'Lakshadweep',
  'Madhya Pradesh',
  'Maharashtra',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Odisha',
  'Puducherry',
  'Punjab',
  'Rajasthan',
  'Sikkim',
  'Tamil Nadu',
  'Telangana',
  'Tripura',
  'Uttar Pradesh',
  'Uttarakhand',
  'West Bengal',
];

export const BUSINESS_CATEGORIES = [
  'Healthcare',
  'Medical & Life Sciences',
  'Financial Services',
  'Legal & Professional Services',
  'Logistics & Supply Chain',
  'Retail & E-commerce',
  'Education & EdTech',
  'Manufacturing & Industrial',
  'Real Estate & Construction',
  'Hospitality & Tourism',
  'Agriculture & AgTech',
];

export const REQUESTED_SERVICES = [
  'Website Development',
  'Mobile Application Development',
  'Web Application Development',
  'SEO Services',
  'Digital Marketing',
];

export const DiscoverySection: React.FC<DiscoverySectionProps> = ({
  onDiscoveryComplete,
  onInspectLead,
  isLiveConnected = false,
  state: propState,
  setState: propSetState,
  category: propCategory,
  setCategory: propSetCategory,
  service: propService,
  setService: propSetService,
  result: propResult,
  setResult: propSetResult,
}) => {
  // Support lifted state from App.tsx or fallback to local state with session cache
  const [internalState, setInternalState] = useState<string>(() => sessionStorage.getItem('discovery_state') || '');
  const [internalCategory, setInternalCategory] = useState<string>(() => sessionStorage.getItem('discovery_category') || '');
  const [internalService, setInternalService] = useState<string>(() => sessionStorage.getItem('discovery_service') || '');
  const [internalResult, setInternalResult] = useState<DiscoveryResult | null>(() => {
    try {
      const saved = sessionStorage.getItem('discovery_result');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const state = propState !== undefined ? propState : internalState;
  const setState = propSetState || setInternalState;
  const category = propCategory !== undefined ? propCategory : internalCategory;
  const setCategory = propSetCategory || setInternalCategory;
  const service = propService !== undefined ? propService : internalService;
  const setService = propSetService || setInternalService;
  const result = propResult !== undefined ? propResult : internalResult;
  const setResult = propSetResult || setInternalResult;

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Synchronization helpers for browser refresh persistence
  const updateState = (val: string) => {
    setState(val);
    if (val) {
      sessionStorage.setItem('discovery_state', val);
    } else {
      sessionStorage.removeItem('discovery_state');
    }
  };

  const updateCategory = (val: string) => {
    setCategory(val);
    if (val) {
      sessionStorage.setItem('discovery_category', val);
    } else {
      sessionStorage.removeItem('discovery_category');
    }
  };

  const updateService = (val: string) => {
    setService(val);
    if (val) {
      sessionStorage.setItem('discovery_service', val);
    } else {
      sessionStorage.removeItem('discovery_service');
    }
  };

  const updateResult = (val: DiscoveryResult | null) => {
    setResult(val);
    if (val) {
      try {
        sessionStorage.setItem('discovery_result', JSON.stringify(val));
      } catch (e) {
        console.warn('Failed to cache discovery result in sessionStorage:', e);
      }
    } else {
      sessionStorage.removeItem('discovery_result');
    }
  };

  // Handlers enforcing strict parent-child dependency
  const handleStateChange = (selectedState: string) => {
    updateState(selectedState);
    updateCategory('');
    updateService('');
    setError(null);
  };

  const handleCategoryChange = (selectedCategory: string) => {
    updateCategory(selectedCategory);
    updateService('');
    setError(null);
  };

  const handleServiceChange = (selectedService: string) => {
    updateService(selectedService);
    setError(null);
  };

  const isLive = Boolean(isLiveConnected || result?.stats?.live_provider_connected);

  // 3. Automated Discovery Search
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!state.trim() || !category.trim() || !service.trim()) {
      setError('Please select a State, Business Category, and Requested Service before starting discovery.');
      return;
    }

    setLoading(true);
    setError(null);
    setSaveMessage(null);
    setSaveError(null);

    try {
      const res = await api.discoverLeads({
        location: state,
        category,
        service,
        auto_ingest: false, // Discovered results are staged for review & 1-click batch save
        auto_analyze: true, // Fully automated AI evaluation and scoring
        limit: 10,
      });

      // Filter out any demo/static benchmark records
      const liveCandidates = (res.candidates || []).filter(
        (c: DiscoveredLead) => c.is_live_discovery && c.record_type !== 'demo' && c.verification_status !== 'demo'
      );
      if (liveCandidates.length > 0) {
        const cleanRes: DiscoveryResult = { ...res, candidates: liveCandidates };
        updateResult(cleanRes);
      } else {
        updateResult(null);
        if (res.candidates && res.candidates.length > 0 && liveCandidates.length === 0) {
          setError('No live external opportunities found. Static demonstration benchmarks are disabled.');
        } else {
          setError(res.stats?.message || `No matching public opportunities surfaced for ${state}, ${category}, and ${service}. This does not mean no businesses need the service. Try a nearby location or broader search phrase.`);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Discovery search failed.');
    } finally {
      setLoading(false);
    }
  };

  // 4. "Save & Start New Search" Action
  const handleSaveAndStartNewSearch = async () => {
    if (!result || !result.candidates || result.candidates.length === 0) return;
    setSaving(true);
    setSaveError(null);
    setSaveMessage(null);

    // Requirement B.1 & B.2: Filter strictly for eligible genuine live discoveries
    const eligibleCandidates = result.candidates.filter(
      (c: DiscoveredLead) =>
        c.is_live_discovery &&
        c.record_type !== 'demo' &&
        c.record_type !== 'sample' &&
        c.verification_status !== 'demo' &&
        c.relevance !== 'Not Relevant' &&
        c.buying_intent !== 'Unqualified'
    );

    if (eligibleCandidates.length === 0) {
      setSaveError('No eligible genuine live discoveries found to save. Unqualified or demo records cannot be saved.');
      setSaving(false);
      return;
    }

    try {
      const saveRes = await api.saveDiscoveryBatch(eligibleCandidates);

      // Display persistent success notification
      setSaveMessage(
        saveRes.message ||
          `Saved ${saveRes.saved_count} new lead(s) to pipeline (${saveRes.duplicates_skipped} duplicate(s) skipped).`
      );

      // Requirements B.3, B.4, B.5, B.7: Return Discovery form and results to completely blank initial state ONLY after successful save
      updateResult(null);
      updateState('');
      updateCategory('');
      updateService('');
      setError(null);

      // Clear relevant Discovery storage entries
      sessionStorage.removeItem('discovery_state');
      sessionStorage.removeItem('discovery_category');
      sessionStorage.removeItem('discovery_service');
      sessionStorage.removeItem('discovery_result');
      localStorage.removeItem('discovery_state');
      localStorage.removeItem('discovery_category');
      localStorage.removeItem('discovery_service');
      localStorage.removeItem('discovery_current_batch');

      // Refresh parent system data (KPIs, Lead Explorer)
      onDiscoveryComplete();

      // Auto-hide success message after 8 seconds
      setTimeout(() => {
        setSaveMessage(null);
      }, 8000);
    } catch (err: any) {
      // Requirement B.9: Do not clear the form if saving fails; show a clear error so the user can retry
      setSaveError(err.message || 'Failed to save leads to pipeline. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="discovery-container">
      {/* Save Success Banner */}
      {saveMessage && (
        <div
          className="alert-banner alert-success"
          style={{
            background: '#ecfdf5',
            border: '1px solid #a7f3d0',
            color: '#065f46',
            borderRadius: '8px',
            padding: '12px 18px',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontWeight: 500,
          }}
        >
          <BookmarkCheck size={20} className="text-emerald" />
          <span>{saveMessage}</span>
        </div>
      )}

      {/* Save Error Banner */}
      {saveError && (
        <div
          className="alert-banner alert-error"
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#991b1b',
            borderRadius: '8px',
            padding: '12px 18px',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontWeight: 500,
          }}
        >
          <AlertCircle size={20} />
          <span>{saveError}</span>
        </div>
      )}

      {/* Provider & Mode Status Banners */}
      {result?.stats?.credit_exhausted ? (
        <div
          className="discovery-exhausted-card"
          style={{
            background: '#fffbeb',
            border: '1px solid #fde68a',
            borderRadius: '8px',
            padding: '14px 18px',
            marginBottom: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#b45309' }}>
            <AlertCircle size={18} />
            <h4 style={{ margin: 0, fontWeight: 600 }}>FREE SEARCH CREDITS EXHAUSTED</h4>
          </div>
          <p style={{ margin: '6px 0 0 0', fontSize: '0.875rem', color: '#92400e' }}>
            {result.stats.message ||
              'Free API search credits have been exhausted for the current monthly period. You can wait for monthly quota renewal or select another free provider.'}
          </p>
        </div>
      ) : isLive ? (
        <div
          className="discovery-live-notice-card"
          style={{
            background: '#eff6ff',
            border: '1px solid #bfdbfe',
            borderRadius: '8px',
            padding: '14px 18px',
            marginBottom: '16px',
          }}
        >
          <div
            className="benchmark-notice-header"
            style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#1d4ed8' }}
          >
            <Sparkles size={18} />
            <h4 className="benchmark-notice-title" style={{ margin: 0, fontWeight: 600 }}>
              LIVE EXTERNAL DISCOVERY MODE
            </h4>
          </div>
          <p
            className="benchmark-notice-desc"
            style={{ margin: '6px 0 0 0', fontSize: '0.875rem', color: '#1e40af' }}
          >
            {result?.stats?.notice ||
              'Active live discovery engine connected via official API. Real-time business opportunities are discovered with provenance tracking, source page verification, and automatic AI intent scoring.'}
          </p>
        </div>
      ) : (
        <div className="discovery-benchmark-notice-card">
          <div className="benchmark-notice-header">
            <AlertTriangle size={18} className="text-amber" />
            <h4 className="benchmark-notice-title">DEMONSTRATION / STATIC BENCHMARK MODE</h4>
          </div>
          <p className="benchmark-notice-desc">
            Live external procurement search is not connected. These records are predefined demonstration
            benchmarks and are not confirmed active commercial opportunities.
          </p>
        </div>
      )}

      {/* Discovery Form Header Card */}
      <div className="discovery-header-card">
        <div className="discovery-header-top">
          <div>
            <h2 className="discovery-title">Business Discovery</h2>
            <p className="discovery-desc">
              Discover authentic commercial buyers, RFPs, and project requirements across Indian states with
              automated AI evaluation and deterministic 5-factor scoring.
            </p>
          </div>
          <div className="discovery-provenance-badge">
            {isLive ? (
              <>
                <Sparkles size={16} className="text-blue-500" />
                <span>{result?.stats?.provider || 'Live Search Engine'}</span>
              </>
            ) : (
              <>
                <ShieldCheck size={16} className="text-emerald" />
                <span>Predefined Benchmark Architecture</span>
              </>
            )}
          </div>
        </div>

        {/* Simplified 3-Input Discovery Form */}
        <form onSubmit={handleSearch} className="discovery-form">
          <div className="discovery-inputs-grid">
            {/* Field A: State (Indian States & UTs Only) */}
            <div className="form-group">
              <label className="form-label" htmlFor="state-select">
                <MapPin size={14} /> State
              </label>
              <select
                id="state-select"
                className="form-input"
                value={state}
                onChange={(e) => handleStateChange(e.target.value)}
                style={{ cursor: 'pointer' }}
              >
                <option value="">Select State</option>
                {INDIAN_STATES_AND_UTS.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
            </div>

            {/* Field B: Business Category */}
            <div className="form-group">
              <label className="form-label" htmlFor="category-select">
                <Building size={14} /> Business Category
              </label>
              <select
                id="category-select"
                className="form-input"
                value={category}
                onChange={(e) => handleCategoryChange(e.target.value)}
                disabled={!state}
                style={{
                  cursor: state ? 'pointer' : 'not-allowed',
                  backgroundColor: state ? '#ffffff' : '#f8fafc',
                  opacity: state ? 1 : 0.65,
                }}
              >
                <option value="">Select Category</option>
                {state &&
                  BUSINESS_CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
              </select>
            </div>

            {/* Field C: Requested Service */}
            <div className="form-group">
              <label className="form-label" htmlFor="service-select">
                <Wrench size={14} /> Requested Service
              </label>
              <select
                id="service-select"
                className="form-input"
                value={service}
                onChange={(e) => handleServiceChange(e.target.value)}
                disabled={!category}
                style={{
                  cursor: category ? 'pointer' : 'not-allowed',
                  backgroundColor: category ? '#ffffff' : '#f8fafc',
                  opacity: category ? 1 : 0.65,
                }}
              >
                <option value="">Select Service</option>
                {category &&
                  REQUESTED_SERVICES.map((srv) => (
                    <option key={srv} value={srv}>
                      {srv}
                    </option>
                  ))}
              </select>
            </div>
          </div>

          <div className="discovery-actions-bar">
            <button
              type="submit"
              disabled={loading || !state || !category || !service}
              className="btn btn-primary discovery-search-btn"
              style={{
                cursor: loading || !state || !category || !service ? 'not-allowed' : 'pointer',
                opacity: loading || !state || !category || !service ? 0.65 : 1,
              }}
            >
              {loading ? (
                <>
                  <span className="spinner-icon"></span> Discovering Businesses...
                </>
              ) : (
                <>
                  <Search size={16} /> Discover Businesses
                </>
              )}
            </button>
          </div>
        </form>

        {error && <div className="alert-banner alert-error mt-3">{error}</div>}
      </div>

      {/* Discovery Results Workspace */}
      {result && (
        <div className="discovery-results-card">
          <div
            className="results-summary-header"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div>
              <div className="flex items-center gap-2">
                <h3 className="results-title">
                  {result.stats.mode === 'static_benchmark'
                    ? `Demonstration Benchmarks (${result.candidates.length})`
                    : `Discovered Opportunities (${result.candidates.length})`}
                </h3>
                <span className="badge badge-demo badge-xs">
                  {result.stats.mode === 'static_benchmark' ? 'Static Benchmark' : 'Live Discovery'}
                </span>
              </div>
              <p className="text-muted text-sm mt-1">
                Provider: <strong>{result.stats.provider}</strong>
                {typeof result.stats.raw_results_count === 'number' && (
                  <>
                    {' '}
                    · Raw Found: <strong>{result.stats.raw_results_count}</strong> · Relevant:{' '}
                    <strong>{result.candidates.length}</strong> · Unqualified:{' '}
                    <strong>{result.stats.unqualified_count ?? 0}</strong>
                  </>
                )}
                {' '}· State: <strong>{result.stats.query?.location || state}</strong> · Category: <strong>{result.stats.query?.category || category}</strong> · All evaluated with AI scoring
              </p>
            </div>

            {/* Save & Start New Search Button */}
            {result.candidates.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleSaveAndStartNewSearch}
                  disabled={saving}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    backgroundColor: '#059669',
                    borderColor: '#059669',
                    fontWeight: 600,
                  }}
                >
                  {saving ? (
                    <>
                      <span className="spinner-icon"></span> Saving to Pipeline...
                    </>
                  ) : (
                    <>
                      <Check size={16} /> Save & Start New Search
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {result.candidates.length === 0 ? (
            <div className="discovery-empty-state">
              <div className="empty-state-icon text-muted">
                <AlertCircle size={36} />
              </div>
              <h4 className="empty-state-title">No matching opportunities surfaced this time</h4>
              <p className="empty-state-description">
                {result.stats.message ||
                  `No matching public opportunities surfaced for State "${state}", Category "${category}", and Service "${service}". This does not mean no businesses need the service.`}
              </p>
              <div className="empty-state-guarantee">
                <ShieldCheck size={14} className="text-emerald" />
                <span>
                  <strong>Source-quality check:</strong> Only public-source results that pass the current relevance checks are shown. A zero-result search is not proof that no potential buyers exist.
                </span>
              </div>
            </div>
          ) : (
            <div className="candidates-list">
              {result.candidates.map((cand: DiscoveredLead, idx: number) => {
                const isCandidateLive = cand.record_type === 'live_discovery' && cand.is_live_discovery;
                const isOfficialTender = cand.verification_status === 'official_tender';
                const isDomainConfirmed =
                  cand.verification_status === 'source_domain_confirmed_tender_unverified';
                const hasExistingLead = Boolean(cand.existing_lead_id || (cand.ingest_status === 'already_exists' && cand.id));
                const targetLeadId = cand.existing_lead_id || cand.id;

                return (
                  <div key={idx} className="candidate-item">
                    <div className="candidate-header">
                      <div>
                        <div className="candidate-title-row">
                          <h4 className="candidate-name">{cand.business_name}</h4>

                          {/* Verification Badge */}
                          {isCandidateLive ? (
                            <span
                              className="badge badge-live"
                              title="Live discovered commercial opportunity via external search"
                            >
                              <Sparkles size={11} /> Live Discovered Opportunity
                            </span>
                          ) : isOfficialTender ? (
                            <span
                              className="badge badge-verified"
                              title="Official-source-confirmed tender notice"
                            >
                              <ShieldCheck size={11} /> Official-Source-Confirmed Tender
                            </span>
                          ) : isDomainConfirmed ? (
                            <span
                              className="badge badge-domain-confirmed"
                              title="Portal domain confirmed official, but tender document is unverified"
                            >
                              <ShieldCheck size={11} /> Domain Confirmed · Tender Unverified
                            </span>
                          ) : cand.record_type === 'demo' || cand.record_type === 'sample' ? (
                            <span className="badge badge-demo" title="Predefined demonstration benchmark">
                              <Layers size={11} /> Static Demonstration Benchmark
                            </span>
                          ) : (
                            <span className="badge badge-unverified" title="Unverified external source">
                              <AlertCircle size={11} /> Unverified Source
                            </span>
                          )}

                          {/* Buying Intent Badge */}
                          {cand.buying_intent === 'Active' && (
                            <span
                              className="badge badge-accent badge-xs"
                              title="Explicit active buying or tender submission intent"
                            >
                              Active Buying Intent
                            </span>
                          )}
                          {cand.buying_intent === 'Potential' && (
                            <span
                              className="badge badge-warning badge-xs"
                              title="Evidence-supported potential requirement"
                            >
                              Potential Need
                            </span>
                          )}

                          {/* Deterministic Lead Score Pill */}
                          {cand.lead_score !== undefined && (
                            <span
                              className={`badge ${
                                cand.priority === 'High'
                                  ? 'badge-danger'
                                  : cand.priority === 'Medium'
                                  ? 'badge-warning'
                                  : 'badge-neutral'
                              }`}
                              style={{ fontWeight: 600 }}
                              title={`Deterministic Lead Score: ${cand.lead_score}/100`}
                            >
                              Score: {cand.lead_score}/100 ({cand.priority || 'Low'})
                            </span>
                          )}
                        </div>

                        {/* Metadata Tags */}
                        <div className="candidate-meta">
                          <span className="meta-tag">
                            <MapPin size={12} /> {cand.location}
                          </span>
                          <span className="meta-tag">
                            <Building size={12} /> {cand.category}
                          </span>
                          <span className="meta-tag tag-service">
                            <Wrench size={12} /> {cand.service}
                          </span>
                          {cand.source_domain && (
                            <span className="meta-tag text-muted">Domain: {cand.source_domain}</span>
                          )}
                        </div>
                      </div>

                      {/* Right-Side Actions: Ingest/Pipeline Status & Clickable Inspection */}
                      <div className="candidate-right" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {hasExistingLead ? (
                          <>
                            <button
                              type="button"
                              className="badge badge-neutral"
                              onClick={() => targetLeadId && onInspectLead?.(targetLeadId)}
                              title="Click to inspect this lead in the pipeline"
                              style={{
                                cursor: 'pointer',
                                border: '1px solid var(--border-color)',
                                padding: '4px 8px',
                                textDecoration: 'underline',
                              }}
                            >
                              Already In Pipeline
                            </button>
                            {onInspectLead && targetLeadId && (
                              <button
                                type="button"
                                onClick={() => onInspectLead(targetLeadId)}
                                className="btn btn-secondary btn-sm"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                              >
                                Inspect Lead <ArrowRight size={14} />
                              </button>
                            )}
                          </>
                        ) : (
                          <span className="badge badge-success">
                            <Check size={11} /> Ready to Save
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Source Notice / Title */}
                    {cand.source_title && (
                      <div className="candidate-source-title">
                        <strong>Notice / Reference: </strong>
                        <span>{cand.source_title}</span>
                      </div>
                    )}

                    {/* Verbatim Requirement Text */}
                    <p className="candidate-requirement">{cand.requirement}</p>

                    {/* Automated AI Evaluation & Verbatim Evidence */}
                    {cand.summary && (
                      <div
                        style={{
                          margin: '8px 0',
                          padding: '10px 14px',
                          background: 'var(--bg-subtle)',
                          borderRadius: '6px',
                          fontSize: '0.85rem',
                          borderLeft: '3px solid var(--primary)',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            fontWeight: 600,
                            color: 'var(--text-main)',
                            marginBottom: '4px',
                          }}
                        >
                          <Sparkles size={13} className="text-primary" /> AI Evaluation:
                        </div>
                        <p style={{ margin: 0, color: 'var(--text-muted)' }}>{cand.summary}</p>
                        {cand.evidence && (
                          <div
                            style={{
                              marginTop: '6px',
                              fontStyle: 'italic',
                              fontSize: '0.8rem',
                              color: 'var(--text-muted)',
                            }}
                          >
                            <strong>Evidence: </strong>"{cand.evidence}"
                          </div>
                        )}
                      </div>
                    )}

                    {/* Verification Notes */}
                    {cand.verification_notes && (
                      <div className="candidate-verification-notes">
                        <ShieldCheck size={13} className="text-emerald" />
                        <span>{cand.verification_notes}</span>
                      </div>
                    )}

                    {/* Footer Details & Source Link */}
                    <div className="candidate-footer">
                      <span className="text-muted text-xs">
                        Authority: <strong>{cand.source_name}</strong> ·{' '}
                        {cand.publication_date ? (
                          <>
                            Published: <strong>{cand.publication_date}</strong>
                          </>
                        ) : (
                          <span className="text-muted">Publication Date: Unknown</span>
                        )}{' '}
                        · Discovered:{' '}
                        <strong>
                          {cand.discovered_at ? cand.discovered_at.split('T')[0] : cand.date_found}
                        </strong>
                        {cand.provider_name ? ` · Source Engine: ${cand.provider_name}` : ''}
                      </span>
                      {cand.source_url && (
                        <a
                          href={cand.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="source-link text-xs flex items-center gap-1"
                        >
                          Source Link <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

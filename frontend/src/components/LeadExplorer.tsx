import React, { useState } from 'react';
import {
  Search,
  Filter,
  RotateCcw,
  Sparkles,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Eye,
  CheckCircle,
  Check,
  Clock,
  AlertCircle,
  Download,
  ShieldCheck,
  Compass,
} from 'lucide-react';
import { Lead, LeadFilterState } from '../types';

interface LeadExplorerProps {
  leads: Lead[];
  total: number;
  loading: boolean;
  filters: LeadFilterState;
  onFilterChange: (newFilters: Partial<LeadFilterState>) => void;
  onSelectLead: (lead: Lead) => void;
  onBatchAnalyze: (provider?: string) => void;
  onNavigateToDiscovery?: () => void;
  onNavigateToExport?: () => void;
  selectedLeadIds?: number[];
  onSelectionChange?: (ids: number[]) => void;
  isEvaluating?: boolean;
}

const CATEGORIES = [
  'All',
  'Financial Services',
  'Healthcare',
  'Medical & Life Sciences',
  'Legal & Professional Services',
  'Logistics & Supply Chain',
  'Retail & E-commerce',
  'Education & EdTech',
  'Manufacturing & Industrial',
  'Website Development',
  'Mobile Application Development',
  'Web Application Development',
  'SEO Services',
  'Digital Marketing',
  'Not Relevant',
];

export const LeadExplorer: React.FC<LeadExplorerProps> = ({
  leads,
  total,
  loading,
  filters,
  onFilterChange,
  onSelectLead,
  onBatchAnalyze,
  onNavigateToDiscovery,
  onNavigateToExport,
  selectedLeadIds = [],
  onSelectionChange,
  isEvaluating,
}) => {
  const [selectedProvider, setSelectedProvider] = useState('auto');

  const allPageSelected =
    leads.length > 0 && leads.every((l) => selectedLeadIds.includes(l.id));
  const somePageSelected =
    leads.some((l) => selectedLeadIds.includes(l.id)) && !allPageSelected;

  const handleToggleSelectAll = () => {
    if (!onSelectionChange) return;
    if (allPageSelected) {
      const pageIds = new Set(leads.map((l) => l.id));
      onSelectionChange(selectedLeadIds.filter((id) => !pageIds.has(id)));
    } else {
      const combined = new Set([...selectedLeadIds, ...leads.map((l) => l.id)]);
      onSelectionChange(Array.from(combined));
    }
  };

  const handleToggleSelectOne = (id: number) => {
    if (!onSelectionChange) return;
    if (selectedLeadIds.includes(id)) {
      onSelectionChange(selectedLeadIds.filter((i) => i !== id));
    } else {
      onSelectionChange([...selectedLeadIds, id]);
    }
  };

  const handleResetFilters = () => {
    onFilterChange({
      search: '',
      category: 'All',
      priority: 'All',
      buying_intent: 'All',
      relevance: 'All',
      status: 'All',
      is_exported: 'All',
      record_type: 'All',
      verification_status: 'All',
      source_page_type: 'All',
      order_by: 'score_desc',
      page: 1,
      live_only: false,
    });
  };

  const totalPages = Math.max(1, Math.ceil(total / filters.page_size));

  return (
    <div className="lead-explorer-container">
      {/* Search and Filter Controls */}
      <div className="explorer-controls-card">
        <div className="search-row">
          <div className="search-input-box">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              className="search-field"
              placeholder="Search leads by company name, requirement, or summary..."
              value={filters.search}
              onChange={(e) => onFilterChange({ search: e.target.value, page: 1 })}
            />
          </div>

          <div className="batch-actions-group">
            <select
              className="form-select provider-select"
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              title="Select AI Provider for Batch Evaluation"
            >
              <option value="auto">Auto AI Provider</option>
              <option value="openai">OpenAI (gpt-4o-mini)</option>
              <option value="gemini">Google Gemini</option>
              <option value="fallback">Rule-Based NLP (Offline)</option>
            </select>

            <button
              onClick={() => onBatchAnalyze(selectedProvider)}
              disabled={isEvaluating}
              className="btn btn-primary btn-batch"
            >
              {isEvaluating ? (
                <>
                  <span className="spinner-icon"></span> Evaluating...
                </>
              ) : (
                <>
                  <Sparkles size={15} /> Batch Evaluate Unprocessed
                </>
              )}
            </button>

            <button
              onClick={handleResetFilters}
              className="btn btn-secondary btn-icon"
              title="Reset all filters"
            >
              <RotateCcw size={15} />
            </button>
          </div>
        </div>

        {/* Filter Dropdowns Grid */}
        <div className="filters-grid">
          {/* Category */}
          <div className="filter-item">
            <label className="filter-label">Service Category</label>
            <select
              className="form-select"
              value={filters.category}
              onChange={(e) => onFilterChange({ category: e.target.value, page: 1 })}
            >
              {Array.from(new Set([...CATEGORIES, ...(filters.category && filters.category !== 'All' ? [filters.category] : [])])).map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          {/* Priority */}
          <div className="filter-item">
            <label className="filter-label">Priority</label>
            <select
              className="form-select"
              value={filters.priority}
              onChange={(e) => onFilterChange({ priority: e.target.value, page: 1 })}
            >
              <option value="All">All Priorities</option>
              <option value="High">High (80–100)</option>
              <option value="Medium">Medium (50–79)</option>
              <option value="Low">Low (0–49)</option>
            </select>
          </div>

          {/* Buying Intent */}
          <div className="filter-item">
            <label className="filter-label">Buying Intent</label>
            <select
              className="form-select"
              value={filters.buying_intent}
              onChange={(e) => onFilterChange({ buying_intent: e.target.value, page: 1 })}
            >
              <option value="All">All Intents</option>
              <option value="Active">Active Intent</option>
              <option value="Potential">Potential Intent</option>
              <option value="Unclear">Unclear Intent</option>
            </select>
          </div>

          {/* Export Status */}
          <div className="filter-item">
            <label className="filter-label">Export Status</label>
            <select
              className="form-select"
              value={
                filters.is_exported === '1' || filters.is_exported === 'Exported'
                  ? 'Exported'
                  : filters.is_exported === '0' || filters.is_exported === 'Not Exported' || filters.is_exported === 'unexported'
                  ? 'Not Exported'
                  : 'All'
              }
              onChange={(e) => onFilterChange({ is_exported: e.target.value, page: 1 })}
            >
              <option value="All">All Export States</option>
              <option value="Exported">Exported</option>
              <option value="Not Exported">Not Exported</option>
            </select>
          </div>

          {/* Dataset Record Type */}
          <div className="filter-item">
            <label className="filter-label">Record Classification</label>
            <select
              className="form-select"
              value={filters.record_type || 'All'}
              onChange={(e) => {
                const val = e.target.value;
                onFilterChange({
                  record_type: val,
                  live_only: val === 'discovered',
                  page: 1,
                });
              }}
            >
              <option value="All">All Saved Records</option>
              <option value="discovered">Live Discovered Opportunities</option>
            </select>
          </div>

          {/* Verification Status */}
          <div className="filter-item">
            <label className="filter-label">Verification Status</label>
            <select
              className="form-select"
              value={filters.verification_status || 'All'}
              onChange={(e) => onFilterChange({ verification_status: e.target.value, page: 1 })}
            >
              <option value="All">All Verification States</option>
              <option value="official_tender">Official Confirmed Tenders</option>
              <option value="source_domain_confirmed_tender_unverified">Domain Confirmed · Tender Unverified</option>
              <option value="unverified">Unverified Sources</option>
            </select>
          </div>

          {/* Source Page Verification (Phase 4) */}
          <div className="filter-item">
            <label className="filter-label">Source Page Audit</label>
            <select
              className="form-select"
              value={filters.source_page_type || 'All'}
              onChange={(e) => onFilterChange({ source_page_type: e.target.value, page: 1 })}
            >
              <option value="All">All Source Types</option>
              <option value="buyer_procurement">Confirmed Buyer Procurement</option>
              <option value="seller_agency">Disqualified: IT Agency</option>
              <option value="portfolio">Disqualified: Portfolio</option>
              <option value="directory">Disqualified: Directory</option>
              <option value="unknown">Unknown / Pending Inspection</option>
            </select>
          </div>

          {/* Processing Status */}
          <div className="filter-item">
            <label className="filter-label">Processing Status</label>
            <select
              className="form-select"
              value={filters.status}
              onChange={(e) => onFilterChange({ status: e.target.value, page: 1 })}
            >
              <option value="All">All Statuses</option>
              <option value="processed">Evaluated (Processed)</option>
              <option value="unprocessed">Pending (Unprocessed)</option>
              <option value="failed">Evaluation Failed</option>
            </select>
          </div>

          {/* Sort Order */}
          <div className="filter-item">
            <label className="filter-label">Sort By</label>
            <select
              className="form-select"
              value={filters.order_by}
              onChange={(e) => onFilterChange({ order_by: e.target.value, page: 1 })}
            >
              <option value="score_desc">Highest Score First</option>
              <option value="score_asc">Lowest Score First</option>
              <option value="id_desc">Newest Leads (ID Desc)</option>
              <option value="id_asc">Oldest Leads (ID Asc)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Leads Table Card */}
      <div className="table-card">
        <div className="table-header-info">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <span className="results-count-text">
              Showing <strong>{leads.length}</strong> of <strong>{total}</strong> leads matching filters
            </span>
            {selectedLeadIds.length > 0 && (
              <span
                className="badge badge-primary text-xs"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '4px 8px',
                  backgroundColor: '#eff6ff',
                  color: '#1d4ed8',
                  border: '1px solid #bfdbfe',
                  borderRadius: '6px',
                  fontWeight: 600,
                }}
              >
                <Check size={12} /> {selectedLeadIds.length} lead(s) selected
                {onSelectionChange && (
                  <button
                    type="button"
                    onClick={() => onSelectionChange([])}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#2563eb',
                      cursor: 'pointer',
                      fontSize: '0.75rem',
                      textDecoration: 'underline',
                      padding: '0 0 0 4px',
                    }}
                    title="Clear all selections"
                  >
                    Clear
                  </button>
                )}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {onNavigateToExport && selectedLeadIds.length > 0 && (
              <button
                type="button"
                onClick={onNavigateToExport}
                className="btn btn-primary btn-sm"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '0.8rem',
                  padding: '5px 12px',
                }}
                title="Export selected leads in Export Intelligence"
              >
                <Download size={13} /> Export Selected ({selectedLeadIds.length})
              </button>
            )}
            <div className="page-size-selector">
              <span className="text-muted text-xs">Per Page:</span>
              {[10, 25, 50].map((size) => (
                <button
                  key={size}
                  className={`page-size-btn ${filters.page_size === size ? 'active' : ''}`}
                  onClick={() => onFilterChange({ page_size: size, page: 1 })}
                >
                  {size}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="table-responsive">
          <table className="enterprise-table">
            <thead>
              <tr>
                <th style={{ width: '40px' }} className="text-center">
                  <input
                    type="checkbox"
                    aria-label="Select all leads on this page"
                    checked={allPageSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = somePageSelected;
                    }}
                    onChange={handleToggleSelectAll}
                    style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                    title={allPageSelected ? 'Deselect all on this page' : 'Select all on this page'}
                  />
                </th>
                <th style={{ width: '60px' }}>ID</th>
                <th style={{ minWidth: '180px' }}>Business Name</th>
                <th style={{ minWidth: '160px' }}>Service Category</th>
                <th style={{ width: '100px' }} className="text-center">Score</th>
                <th style={{ width: '110px' }} className="text-center">Priority</th>
                <th style={{ width: '120px' }}>Intent</th>
                <th style={{ width: '130px' }} className="text-center">Export Status</th>
                <th style={{ width: '90px' }} className="text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} className="text-center py-8">
                    <span className="spinner-icon"></span> Loading leads...
                  </td>
                </tr>
              ) : leads.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-12">
                    <div className="empty-leads-notice" style={{ maxWidth: '480px', margin: '0 auto', textAlign: 'center' }}>
                      <div style={{ fontSize: '1.75rem', marginBottom: '0.5rem' }}>🎯</div>
                      <h4 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                        No Live-Discovered Leads in Pipeline
                      </h4>
                      <p className="text-muted text-sm" style={{ marginBottom: '1rem', lineHeight: 1.5 }}>
                        Lead Explorer displays only genuine live-discovered leads with completed AI evaluation and verified evidence. Historical demonstration benchmarks and uploaded files are safely excluded.
                      </p>
                      {onNavigateToDiscovery && (
                        <button
                          onClick={onNavigateToDiscovery}
                          className="btn btn-primary btn-sm"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', margin: '0 auto' }}
                        >
                          <Compass size={14} /> Go to Business Discovery
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                leads.map((lead) => {
                  const isHigh = lead.priority === 'High';
                  const isMed = lead.priority === 'Medium';
                  const isUnprocessed = lead.status === 'unprocessed';
                  const isFailed = lead.status === 'failed';

                  return (
                    <tr
                      key={lead.id}
                      className={`lead-row ${selectedLeadIds.includes(lead.id) ? 'row-selected' : ''} ${lead.is_exported === 0 && !isUnprocessed ? 'row-unexported' : ''}`}
                      onClick={() => onSelectLead(lead)}
                    >
                      <td className="text-center" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          aria-label={`Select lead ${lead.id}`}
                          checked={selectedLeadIds.includes(lead.id)}
                          onChange={() => handleToggleSelectOne(lead.id)}
                          style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                        />
                      </td>
                      <td className="text-muted font-mono text-xs">#{lead.id}</td>
                      <td>
                        <div className="business-cell">
                          <div className="business-title-row">
                            <span className="business-title">{lead.business_name}</span>
                            {lead.record_type === 'live_discovery' ? (
                              <span className="badge badge-live badge-xs" title="Live discovered commercial opportunity">
                                <Sparkles size={10} /> Live
                              </span>
                            ) : lead.verification_status === 'official_tender' ? (
                              <span className="badge badge-verified badge-xs" title="Official-source-confirmed public tender">
                                <ShieldCheck size={10} /> Confirmed Tender
                              </span>
                            ) : lead.verification_status === 'source_domain_confirmed_tender_unverified' ? (
                              <span
                                className="badge badge-domain-confirmed badge-xs"
                                title="Portal domain confirmed official, but tender document and closing date not independently verified"
                              >
                                <ShieldCheck size={10} /> Domain Confirmed
                              </span>
                            ) : lead.verification_status === 'demo' || lead.record_type === 'demo' ? (
                              <span className="badge badge-demo badge-xs" title="Pre-seeded demonstration benchmark record">
                                Demo Benchmark
                              </span>
                            ) : (
                              <span className="badge badge-unverified badge-xs" title="Unverified source (requires independent validation)">
                                <AlertCircle size={10} /> Unverified
                              </span>
                            )}
                            {lead.record_type && (
                              <span className="record-type-pill text-xs">
                                {lead.record_type}
                              </span>
                            )}
                            {lead.source_page_type === 'buyer_procurement' ? (
                              <span className="badge badge-verified badge-xs" title="Source page verified as genuine buyer procurement notice">
                                <ShieldCheck size={9} /> Buyer Verified
                              </span>
                            ) : lead.source_page_type === 'seller_agency' ? (
                              <span className="badge badge-xs" style={{ background: 'rgba(249, 115, 22, 0.15)', color: '#f97316' }} title="Verified as digital agency / seller">
                                Seller / Agency
                              </span>
                            ) : lead.source_page_type === 'portfolio' ? (
                              <span className="badge badge-xs" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#a855f7' }} title="Verified as agency portfolio">
                                Portfolio
                              </span>
                            ) : null}
                          </div>
                          {lead.location && (
                            <span className="business-location text-xs text-muted">
                              {lead.location}
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <span className="category-cell">
                          {lead.category || 'Uncategorized'}
                        </span>
                      </td>
                      <td className="text-center">
                        {isUnprocessed ? (
                          <span className="score-badge score-pending">-</span>
                        ) : (
                          <span
                            className={`score-badge ${
                              lead.lead_score >= 80
                                ? 'score-high'
                                : lead.lead_score >= 50
                                ? 'score-med'
                                : 'score-low'
                            }`}
                          >
                            {lead.lead_score}
                          </span>
                        )}
                      </td>
                      <td className="text-center">
                        {isUnprocessed ? (
                          <span className="badge badge-unprocessed">Pending</span>
                        ) : isFailed ? (
                          <span className="badge badge-danger">Failed</span>
                        ) : isHigh ? (
                          <span className="badge badge-high">High</span>
                        ) : isMed ? (
                          <span className="badge badge-medium">Medium</span>
                        ) : (
                          <span className="badge badge-low">Low</span>
                        )}
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            lead.buying_intent === 'Active'
                              ? 'badge-active'
                              : lead.buying_intent === 'Potential'
                              ? 'badge-potential'
                              : 'badge-neutral'
                          }`}
                        >
                          {lead.buying_intent || 'Unclear'}
                        </span>
                      </td>
                      <td className="text-center">
                        {Number(lead.is_exported) === 1 ? (
                          <span className="badge badge-exported" title={lead.exported_at ? `Exported at ${lead.exported_at}` : 'Exported'}>
                            <CheckCircle size={12} /> Exported
                          </span>
                        ) : (
                          <span className="badge badge-not-exported" title="Not yet exported">
                            <Clock size={12} /> Not Exported
                          </span>
                        )}
                      </td>
                      <td className="text-center" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => onSelectLead(lead)}
                          className="btn btn-secondary btn-xs btn-inspect"
                          title="Inspect Lead & 5-Factor Scoring"
                        >
                          <Eye size={13} /> Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="pagination-bar">
          <div className="pagination-info text-sm text-muted">
            Page {filters.page} of {totalPages}
          </div>
          <div className="pagination-controls">
            <button
              disabled={filters.page <= 1}
              onClick={() => onFilterChange({ page: filters.page - 1 })}
              className="pagination-btn"
              aria-label="Previous Page"
            >
              <ChevronLeft size={16} /> Previous
            </button>
            <span className="pagination-current-page">{filters.page}</span>
            <button
              disabled={filters.page >= totalPages}
              onClick={() => onFilterChange({ page: filters.page + 1 })}
              className="pagination-btn"
              aria-label="Next Page"
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

import React from 'react';
import {
  Users,
  Target,
  Flame,
  Clock,
  Sparkles,
  ArrowRight,
  TrendingUp,
  Award,
  Layers,
  Compass,
  CheckCircle,
  ExternalLink,
  Eye,
  RefreshCw,
  AlertCircle,
  BarChart3,
  PieChart,
} from 'lucide-react';
import {
  DashboardMetrics,
  LeadFilterState,
  HighPriorityOpportunity,
  ServiceCategoryBreakdown,
} from '../types';

interface DashboardSectionProps {
  metrics: DashboardMetrics | null;
  loading: boolean;
  onNavigateToExplorer: (filters?: Partial<LeadFilterState>) => void;
  onNavigateToDiscovery: () => void;
  onInspectLead: (leadId: number) => void;
  onRefresh: () => void;
}

export const DashboardSection: React.FC<DashboardSectionProps> = ({
  metrics,
  loading,
  onNavigateToExplorer,
  onNavigateToDiscovery,
  onInspectLead,
  onRefresh,
}) => {
  // Loading skeleton state
  if (loading && !metrics) {
    return (
      <div className="dashboard-container" aria-busy="true" aria-label="Loading dashboard data">
        <div className="dashboard-header-skeleton">
          <div className="skeleton-line" style={{ width: '220px', height: '24px', marginBottom: '8px' }}></div>
          <div className="skeleton-line" style={{ width: '380px', height: '14px' }}></div>
        </div>
        <div className="dashboard-kpi-grid">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="kpi-card skeleton-card">
              <div className="skeleton-line" style={{ width: '45%', height: '14px', marginBottom: '14px' }}></div>
              <div className="skeleton-line" style={{ width: '60px', height: '32px', marginBottom: '12px' }}></div>
              <div className="skeleton-line" style={{ width: '75%', height: '12px' }}></div>
            </div>
          ))}
        </div>
        <div className="dashboard-visual-grid">
          <div className="dashboard-card skeleton-card" style={{ height: '320px' }}></div>
          <div className="dashboard-card skeleton-card" style={{ height: '320px' }}></div>
        </div>
      </div>
    );
  }

  // Error state
  if (!metrics) {
    return (
      <div className="dashboard-container">
        <div className="dashboard-empty-card">
          <AlertCircle size={44} className="text-danger" style={{ marginBottom: '12px' }} />
          <h3>Unable to Load Dashboard Statistics</h3>
          <p className="text-muted">
            The system could not retrieve business lead metrics from Neon PostgreSQL. Please check your network connection and retry.
          </p>
          <button onClick={onRefresh} className="btn btn-primary" style={{ marginTop: '16px' }}>
            <RefreshCw size={15} /> Retry Loading
          </button>
        </div>
      </div>
    );
  }

  const total = metrics.total_records || 0;
  const activeIntent = metrics.active_intent_leads || 0;
  const highPriority = metrics.high_priority_leads || 0;
  const mediumPriority = metrics.medium_priority_leads || 0;
  const potentialIntent = metrics.potential_intent_leads || 0;
  const lowPriority = metrics.low_priority_leads || 0;
  const unclearIntent = metrics.unclear_intent_leads || 0;

  // Empty state if database has zero saved leads
  if (total === 0) {
    return (
      <div className="dashboard-container">
        <div className="dashboard-banner">
          <div>
            <h2 className="dashboard-title">Lead Intelligence Dashboard</h2>
            <p className="dashboard-subtitle">
              Executive overview of discovered, evaluated, and prioritized commercial business leads.
            </p>
          </div>
          <button onClick={onRefresh} className="btn btn-secondary btn-sm" title="Refresh statistics">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        <div className="dashboard-empty-card">
          <div className="empty-icon-bubble">
            <Compass size={38} className="text-primary" />
          </div>
          <h3>No Saved Business Leads Found</h3>
          <p className="text-muted" style={{ maxWidth: '520px', margin: '0 auto 20px auto' }}>
            Your Neon PostgreSQL database currently contains no saved lead records. Launch a live business discovery
            search to find, evaluate, and save verified public RFPs and tenders into your sales pipeline.
          </p>
          <button onClick={onNavigateToDiscovery} className="btn btn-primary">
            <Compass size={16} /> Start Business Discovery
          </button>
        </div>
      </div>
    );
  }

  // Calculations for Buying Intent Donut Chart
  const intentTotal = activeIntent + potentialIntent + unclearIntent || 1;
  const activePct = Math.round((activeIntent / intentTotal) * 100);
  const potentialPct = Math.round((potentialIntent / intentTotal) * 100);
  const unclearPct = Math.max(0, 100 - activePct - potentialPct);

  // SVG Donut calculation (circumference of r=54 is 2 * PI * 54 = 339.29)
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const activeDash = (activeIntent / intentTotal) * circumference;
  const potentialDash = (potentialIntent / intentTotal) * circumference;
  const unclearDash = (unclearIntent / intentTotal) * circumference;
  const potentialOffset = -activeDash;
  const unclearOffset = -(activeDash + potentialDash);

  // Priority percentages
  const priorityTotal = highPriority + mediumPriority + lowPriority || 1;
  const highPct = Math.round((highPriority / priorityTotal) * 100);
  const medPct = Math.round((mediumPriority / priorityTotal) * 100);
  const lowPct = Math.max(0, 100 - highPct - medPct);

  // Identify service category with the highest high-priority opportunities
  const services: ServiceCategoryBreakdown[] = metrics.service_breakdown || [];
  let topServiceWithHighPriority: ServiceCategoryBreakdown | null = null;
  if (services.length > 0) {
    // Sort primarily by high_priority_leads DESC, then by total_leads DESC
    const sortedServices = [...services].sort((a, b) => {
      if (b.high_priority_leads !== a.high_priority_leads) {
        return b.high_priority_leads - a.high_priority_leads;
      }
      return b.total_leads - a.total_leads;
    });
    if (sortedServices[0] && sortedServices[0].high_priority_leads > 0) {
      topServiceWithHighPriority = sortedServices[0];
    } else {
      topServiceWithHighPriority = sortedServices[0];
    }
  }

  // High-priority opportunities list
  const highPriorityOpps: HighPriorityOpportunity[] = metrics.high_priority_opportunities || [];

  return (
    <div className="dashboard-container">
      {/* Dashboard Top Header */}
      <div className="dashboard-banner">
        <div>
          <h2 className="dashboard-title">Lead Intelligence Dashboard</h2>
          <p className="dashboard-subtitle">
            Real-time pipeline overview of saved business leads, intent classification, and procurement opportunities.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={onRefresh}
            className="btn btn-secondary btn-sm"
            title="Refresh dashboard statistics from Neon PostgreSQL"
          >
            <RefreshCw size={14} /> Refresh Stats
          </button>
          <button
            onClick={onNavigateToDiscovery}
            className="btn btn-primary btn-sm"
            title="Discover new business leads"
          >
            <Compass size={14} /> New Search
          </button>
        </div>
      </div>

      {/* REQUIREMENT 1: FIVE KPI CARDS */}
      <div className="dashboard-kpi-grid">
        {/* KPI 1: Total Leads */}
        <div
          className="kpi-card kpi-card-interactive"
          onClick={() =>
            onNavigateToExplorer({
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
              live_only: false,
              page: 1,
            })
          }
          title="Click to view all saved leads in Lead Explorer (unfiltered)"
        >
          <div className="kpi-header">
            <span className="kpi-label">Total Leads</span>
            <div className="kpi-icon-box bg-blue-subtle text-blue">
              <Users size={18} />
            </div>
          </div>
          <div className="kpi-value text-blue">{total}</div>
          <div className="kpi-footer text-muted">
            <span>
              <strong>{metrics.processed_records || total}</strong> evaluated ·{' '}
              <strong>{metrics.not_yet_exported || 0}</strong> unexported
            </span>
          </div>
          <div className="kpi-action-hint">
            <span>View all in Explorer</span>
            <ArrowRight size={12} />
          </div>
        </div>

        {/* KPI 2: Active Buying Intent */}
        <div
          className="kpi-card kpi-card-interactive"
          onClick={() =>
            onNavigateToExplorer({
              buying_intent: 'Active',
              page: 1,
            })
          }
          title="Click to filter leads with Active Buying Intent"
        >
          <div className="kpi-header">
            <span className="kpi-label">Active Buying Intent</span>
            <div className="kpi-icon-box bg-purple-subtle text-purple">
              <Target size={18} />
            </div>
          </div>
          <div className="kpi-value text-purple">{activeIntent}</div>
          <div className="kpi-footer text-muted">
            <span>Classified as active intent; source verification may still be required</span>
          </div>
          <div className="kpi-action-hint">
            <span>Filter Active Intent</span>
            <ArrowRight size={12} />
          </div>
        </div>

        {/* KPI 3: High Priority Leads */}
        <div
          className="kpi-card kpi-card-interactive kpi-card-high"
          onClick={() =>
            onNavigateToExplorer({
              priority: 'High',
              page: 1,
            })
          }
          title="Click to filter High Priority Leads (Score 80–100)"
        >
          <div className="kpi-header">
            <span className="kpi-label">High Priority Leads</span>
            <div className="kpi-icon-box bg-emerald-subtle text-emerald">
              <Flame size={18} />
            </div>
          </div>
          <div className="kpi-value text-emerald">{highPriority}</div>
          <div className="kpi-footer text-muted">
            <span>Score 80–100 · Immediate outreach</span>
          </div>
          <div className="kpi-action-hint">
            <span>Filter High Priority</span>
            <ArrowRight size={12} />
          </div>
        </div>

        {/* KPI 4: Medium Priority Leads */}
        <div
          className="kpi-card kpi-card-interactive"
          onClick={() =>
            onNavigateToExplorer({
              priority: 'Medium',
              page: 1,
            })
          }
          title="Click to filter Medium Priority Leads (Score 50–79)"
        >
          <div className="kpi-header">
            <span className="kpi-label">Medium Priority Leads</span>
            <div className="kpi-icon-box bg-amber-subtle text-amber">
              <Clock size={18} />
            </div>
          </div>
          <div className="kpi-value text-amber">{mediumPriority}</div>
          <div className="kpi-footer text-muted">
            <span>Score 50–79 · Nurture pipeline</span>
          </div>
          <div className="kpi-action-hint">
            <span>Filter Medium Priority</span>
            <ArrowRight size={12} />
          </div>
        </div>

        {/* KPI 5: Potential Buying Intent */}
        <div
          className="kpi-card kpi-card-interactive"
          onClick={() =>
            onNavigateToExplorer({
              buying_intent: 'Potential',
              page: 1,
            })
          }
          title="Click to filter Potential Buying Intent"
        >
          <div className="kpi-header">
            <span className="kpi-label">Potential Buying Intent</span>
            <div className="kpi-icon-box bg-cyan-subtle text-cyan">
              <Sparkles size={18} />
            </div>
          </div>
          <div className="kpi-value text-cyan">{potentialIntent}</div>
          <div className="kpi-footer text-muted">
            <span>Commercial requirement signals</span>
          </div>
          <div className="kpi-action-hint">
            <span>Filter Potential Intent</span>
            <ArrowRight size={12} />
          </div>
        </div>
      </div>

      {/* VISUAL SECTIONS A & B: BUYING INTENT OVERVIEW & PRIORITY DISTRIBUTION */}
      <div className="dashboard-visual-grid">
        {/* Section A: Buying Intent Overview */}
        <div className="dashboard-card">
          <div className="dashboard-card-header">
            <div className="card-header-left">
              <PieChart size={18} className="text-purple" />
              <div>
                <h3 className="card-heading">Buying Intent Overview</h3>
                <span className="card-subheading">Distribution across procurement maturity categories</span>
              </div>
            </div>
            <span className="badge badge-subtle">{total} Leads</span>
          </div>

          <div className="intent-overview-body">
            {/* Donut Chart */}
            <div className="donut-chart-container">
              <svg width="140" height="140" viewBox="0 0 140 140" className="donut-svg">
                <circle
                  cx="70"
                  cy="70"
                  r={radius}
                  fill="none"
                  stroke="var(--bg-subtle)"
                  strokeWidth="14"
                />
                {/* Active Intent Arc */}
                {activeIntent > 0 && (
                  <circle
                    cx="70"
                    cy="70"
                    r={radius}
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="14"
                    strokeDasharray={`${activeDash} ${circumference}`}
                    strokeDashoffset="0"
                    transform="rotate(-90 70 70)"
                    strokeLinecap="round"
                  />
                )}
                {/* Potential Intent Arc */}
                {potentialIntent > 0 && (
                  <circle
                    cx="70"
                    cy="70"
                    r={radius}
                    fill="none"
                    stroke="#3b82f6"
                    strokeWidth="14"
                    strokeDasharray={`${potentialDash} ${circumference}`}
                    strokeDashoffset={potentialOffset}
                    transform="rotate(-90 70 70)"
                    strokeLinecap="round"
                  />
                )}
                {/* Unclear Intent Arc */}
                {unclearIntent > 0 && (
                  <circle
                    cx="70"
                    cy="70"
                    r={radius}
                    fill="none"
                    stroke="#94a3b8"
                    strokeWidth="14"
                    strokeDasharray={`${unclearDash} ${circumference}`}
                    strokeDashoffset={unclearOffset}
                    transform="rotate(-90 70 70)"
                    strokeLinecap="round"
                  />
                )}
              </svg>
              <div className="donut-center-label">
                <span className="donut-center-value">{total}</span>
                <span className="donut-center-text">Total</span>
              </div>
            </div>

            {/* Intent Legend & Breakdown List */}
            <div className="intent-legend-list">
              {/* Active */}
              <div
                className="intent-row intent-row-interactive"
                onClick={() => onNavigateToExplorer({ buying_intent: 'Active', page: 1 })}
                title="Filter leads by Active Intent"
              >
                <div className="intent-dot bg-emerald"></div>
                <div className="intent-info">
                  <div className="intent-label-line">
                    <span className="intent-name">Active Intent</span>
                    <span className="intent-stat">
                      <strong>{activeIntent}</strong> ({activePct}%)
                    </span>
                  </div>
                  <div className="bar-track">
                    <div className="bar-fill bg-emerald" style={{ width: `${activePct}%` }}></div>
                  </div>
                  <span className="intent-desc">Formal RFPs, tenders &amp; active vendor requirements</span>
                </div>
              </div>

              {/* Potential */}
              <div
                className="intent-row intent-row-interactive"
                onClick={() => onNavigateToExplorer({ buying_intent: 'Potential', page: 1 })}
                title="Filter leads by Potential Intent"
              >
                <div className="intent-dot bg-blue"></div>
                <div className="intent-info">
                  <div className="intent-label-line">
                    <span className="intent-name">Potential Intent</span>
                    <span className="intent-stat">
                      <strong>{potentialIntent}</strong> ({potentialPct}%)
                    </span>
                  </div>
                  <div className="bar-track">
                    <div className="bar-fill bg-blue" style={{ width: `${potentialPct}%` }}></div>
                  </div>
                  <span className="intent-desc">Early planning, exploratory inquiries &amp; modernizations</span>
                </div>
              </div>

              {/* Unclear / Other */}
              <div
                className="intent-row intent-row-interactive"
                onClick={() => onNavigateToExplorer({ buying_intent: 'Unclear', page: 1 })}
                title="Filter leads by Unclear Intent"
              >
                <div className="intent-dot bg-slate"></div>
                <div className="intent-info">
                  <div className="intent-label-line">
                    <span className="intent-name">Unclear / Pending</span>
                    <span className="intent-stat">
                      <strong>{unclearIntent}</strong> ({unclearPct}%)
                    </span>
                  </div>
                  <div className="bar-track">
                    <div className="bar-fill bg-slate" style={{ width: `${unclearPct}%` }}></div>
                  </div>
                  <span className="intent-desc">Informational mentions requiring manual verification</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Section B: Priority Distribution */}
        <div className="dashboard-card">
          <div className="dashboard-card-header">
            <div className="card-header-left">
              <BarChart3 size={18} className="text-emerald" />
              <div>
                <h3 className="card-heading">Priority Distribution</h3>
                <span className="card-subheading">5-factor algorithmic scoring and lead qualification tiers</span>
              </div>
            </div>
            <span className="badge badge-success">
              <Award size={12} /> {highPriority} High Priority
            </span>
          </div>

          <div className="priority-overview-body">
            {/* Multi-segment Distribution Bar */}
            <div className="multi-bar-container">
              <div
                className="multi-bar-segment bg-emerald"
                style={{ width: `${highPct}%` }}
                title={`High Priority: ${highPriority} (${highPct}%)`}
              ></div>
              <div
                className="multi-bar-segment bg-amber"
                style={{ width: `${medPct}%` }}
                title={`Medium Priority: ${mediumPriority} (${medPct}%)`}
              ></div>
              <div
                className="multi-bar-segment bg-slate"
                style={{ width: `${lowPct}%` }}
                title={`Low Priority: ${lowPriority} (${lowPct}%)`}
              ></div>
            </div>

            {/* 3 Priority Cards */}
            <div className="priority-chips-grid">
              {/* High */}
              <div
                className="priority-chip chip-high-interactive"
                onClick={() => onNavigateToExplorer({ priority: 'High', page: 1 })}
                title="Filter High Priority Leads"
              >
                <div className="chip-header">
                  <span className="chip-tier-tag badge-priority-high">High Priority</span>
                  <Flame size={16} className="text-emerald" />
                </div>
                <div className="chip-number text-emerald">{highPriority}</div>
                <div className="chip-sub">Score 80–100</div>
                <div className="chip-detail">
                  <span>{highPct}% of saved pipeline</span>
                  <ArrowRight size={11} />
                </div>
              </div>

              {/* Medium */}
              <div
                className="priority-chip chip-medium-interactive"
                onClick={() => onNavigateToExplorer({ priority: 'Medium', page: 1 })}
                title="Filter Medium Priority Leads"
              >
                <div className="chip-header">
                  <span className="chip-tier-tag badge-priority-medium">Medium Priority</span>
                  <Clock size={16} className="text-amber" />
                </div>
                <div className="chip-number text-amber">{mediumPriority}</div>
                <div className="chip-sub">Score 50–79</div>
                <div className="chip-detail">
                  <span>{medPct}% of saved pipeline</span>
                  <ArrowRight size={11} />
                </div>
              </div>

              {/* Low */}
              <div
                className="priority-chip chip-low-interactive"
                onClick={() => onNavigateToExplorer({ priority: 'Low', page: 1 })}
                title="Filter Low Priority Leads"
              >
                <div className="chip-header">
                  <span className="chip-tier-tag badge-priority-low">Low Priority</span>
                  <Layers size={16} className="text-muted" />
                </div>
                <div className="chip-number text-muted">{lowPriority}</div>
                <div className="chip-sub">Score 0–49</div>
                <div className="chip-detail">
                  <span>{lowPct}% of saved pipeline</span>
                  <ArrowRight size={11} />
                </div>
              </div>
            </div>

            <div className="priority-insight-box">
              <TrendingUp size={16} className="text-emerald" />
              <span>
                <strong>{highPriority + mediumPriority} of {total}</strong> leads qualify for immediate business engagement
                with positive commercial intent and high relevance scores.
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* VISUAL SECTION C: SERVICE-WISE LEAD ANALYSIS */}
      <div className="dashboard-card" style={{ marginBottom: '24px' }}>
        <div className="dashboard-card-header">
          <div className="card-header-left">
            <Layers size={18} className="text-blue" />
            <div>
              <h3 className="card-heading">Service-wise Lead Analysis</h3>
              <span className="card-subheading">
                Distribution of saved business opportunities grouped by actual service category
              </span>
            </div>
          </div>
          {topServiceWithHighPriority && topServiceWithHighPriority.high_priority_leads > 0 && (
            <div className="top-opportunity-pill" title="Industry with highest number of high priority opportunities">
              <Flame size={14} className="text-emerald" />
              <span>
                Top High-Priority Sector: <strong>{topServiceWithHighPriority.service_category}</strong> (
                {topServiceWithHighPriority.high_priority_leads} High Priority)
              </span>
            </div>
          )}
        </div>

        <div className="service-analysis-body">
          {services.length === 0 ? (
            <p className="text-muted text-sm" style={{ padding: '20px 0' }}>
              No service categories categorized yet.
            </p>
          ) : (
            <div className="service-cards-grid">
              {services.map((svc) => {
                const svcTotal = svc.total_leads || 0;
                const svcHigh = svc.high_priority_leads || 0;
                const svcMed = svc.medium_priority_leads || 0;
                const svcPct = total > 0 ? Math.round((svcTotal / total) * 100) : 0;
                const isTopSector = topServiceWithHighPriority?.service_category === svc.service_category;

                return (
                  <div
                    key={svc.service_category}
                    className={`service-lead-card ${isTopSector ? 'service-card-highlight' : ''}`}
                    onClick={() =>
                      onNavigateToExplorer({
                        category: svc.service_category,
                        page: 1,
                      })
                    }
                    title={`Click to view ${svc.service_category} leads in Lead Explorer`}
                  >
                    <div className="service-card-top">
                      <div>
                        <div className="service-name-row">
                          <h4 className="service-name">{svc.service_category}</h4>
                          {isTopSector && svcHigh > 0 && (
                            <span className="badge badge-accent-star" title="Highest number of high-priority opportunities">
                              ★ Top Opportunity
                            </span>
                          )}
                        </div>
                        <span className="service-count-text">
                          <strong>{svcTotal}</strong> {svcTotal === 1 ? 'Lead' : 'Leads'} ({svcPct}% of pipeline)
                        </span>
                      </div>
                      <div className="service-kpi-badge">
                        <span className="service-high-count text-emerald">{svcHigh}</span>
                        <span className="service-high-label">High Priority</span>
                      </div>
                    </div>

                    {/* Progress track */}
                    <div className="bar-track" style={{ height: '8px', margin: '12px 0 10px 0' }}>
                      <div
                        className="bar-fill bg-blue"
                        style={{ width: `${Math.min(100, Math.max(12, svcPct))}%` }}
                      ></div>
                    </div>

                    {/* Breakdown counts */}
                    <div className="service-meta-footer">
                      <span className="service-meta-item">
                        <span className="meta-dot bg-emerald"></span> {svcHigh} High
                      </span>
                      <span className="service-meta-item">
                        <span className="meta-dot bg-amber"></span> {svcMed} Medium
                      </span>
                      <span className="service-meta-item">
                        <span className="meta-dot bg-slate"></span> {svc.low_priority_leads} Low
                      </span>
                      <span className="service-explore-link">
                        Explore <ArrowRight size={12} />
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* VISUAL SECTION D: HIGH-PRIORITY OPPORTUNITIES */}
      <div className="dashboard-card">
        <div className="dashboard-card-header">
          <div className="card-header-left">
            <Flame size={18} className="text-emerald" />
            <div>
              <h3 className="card-heading">High-Priority Opportunities</h3>
              <span className="card-subheading">
                Top actionable commercial procurement leads scored 80–100 with verified intent
              </span>
            </div>
          </div>
          <button
            onClick={() => onNavigateToExplorer({ priority: 'High', page: 1 })}
            className="btn btn-secondary btn-sm"
          >
            View All in Explorer <ArrowRight size={13} />
          </button>
        </div>

        <div className="high-priority-table-wrapper">
          {highPriorityOpps.length === 0 ? (
            <div className="empty-section-notice" style={{ padding: '30px 20px', textAlign: 'center' }}>
              <p className="text-muted">No high-priority leads currently found in the database.</p>
              <button
                onClick={onNavigateToDiscovery}
                className="btn btn-secondary btn-sm"
                style={{ marginTop: '10px' }}
              >
                <Compass size={13} /> Discover New Opportunities
              </button>
            </div>
          ) : (
            <table className="enterprise-table dashboard-opps-table">
              <thead>
                <tr>
                  <th style={{ width: '60px' }}>ID</th>
                  <th style={{ minWidth: '220px' }}>Organisation / Business</th>
                  <th style={{ minWidth: '160px' }}>Service Category</th>
                  <th style={{ width: '130px' }} className="text-center">Buying Intent</th>
                  <th style={{ width: '120px' }} className="text-center">Relevance Score</th>
                  <th style={{ width: '110px' }}>Date Found</th>
                  <th style={{ width: '130px' }} className="text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {highPriorityOpps.map((lead) => (
                  <tr
                    key={lead.id}
                    className="lead-row dashboard-opp-row"
                    onClick={() => onInspectLead(lead.id)}
                    title="Click to view complete lead analysis"
                  >
                    <td className="text-muted font-mono text-xs">#{lead.id}</td>
                    <td>
                      <div className="business-cell">
                        <span className="business-name-text">{lead.business_name}</span>
                        {lead.location && (
                          <span className="business-location-text text-muted">
                            📍 {lead.location}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-category">{lead.category}</span>
                    </td>
                    <td className="text-center">
                      <span className="badge badge-intent badge-intent-active">
                        <CheckCircle size={11} /> {lead.buying_intent || 'Active'}
                      </span>
                    </td>
                    <td className="text-center">
                      <div className="score-cell-compact">
                        <span className="score-badge score-high">{lead.lead_score}/100</span>
                        <span className="relevance-tag text-xs text-emerald">Relevant</span>
                      </div>
                    </td>
                    <td className="text-muted text-xs font-mono">
                      {lead.date_found || 'Recent'}
                    </td>
                    <td className="text-center" onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: 'inline-flex', gap: '6px' }}>
                        <button
                          type="button"
                          className="btn btn-secondary btn-xs"
                          onClick={() => onInspectLead(lead.id)}
                          title="Open detailed evaluation and verbatim evidence"
                        >
                          <Eye size={12} /> Inspect
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-xs"
                          onClick={() =>
                            onNavigateToExplorer({
                              search: lead.business_name,
                              page: 1,
                            })
                          }
                          title="Find this lead in Lead Explorer"
                        >
                          <ExternalLink size={12} /> Explorer
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

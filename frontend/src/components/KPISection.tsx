import React from 'react';
import { Users, Flame, Target, Download, CheckCircle, Clock } from 'lucide-react';
import { DashboardMetrics } from '../types';

interface KPISectionProps {
  metrics: DashboardMetrics | null;
  loading: boolean;
  onFilterUnexported?: () => void;
  onFilterHighPriority?: () => void;
}

export const KPISection: React.FC<KPISectionProps> = ({
  metrics,
  loading,
  onFilterUnexported,
  onFilterHighPriority,
}) => {
  if (loading && !metrics) {
    return (
      <div className="kpi-grid">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="kpi-card skeleton-card">
            <div className="skeleton-line" style={{ width: '40%' }}></div>
            <div className="skeleton-number"></div>
            <div className="skeleton-line" style={{ width: '70%' }}></div>
          </div>
        ))}
      </div>
    );
  }

  const total = metrics?.total_records || 0;
  const processed = metrics?.processed_records || 0;
  const highPriority = metrics?.high_priority_leads || 0;
  const activeIntent = metrics?.active_intent_leads || 0;
  const unexported = metrics?.not_yet_exported || 0;

  return (
    <section className="dashboard-section">
      <div className="kpi-grid">
        {/* Total Ingested */}
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">Total Leads</span>
            <div className="kpi-icon-box bg-blue-subtle text-blue">
              <Users size={18} />
            </div>
          </div>
          <div className="kpi-value">{total}</div>
          <div className="kpi-footer text-muted">
            <span>
              <strong className="text-success">{processed}</strong> evaluated ·{' '}
              <strong>{metrics?.unprocessed_records || 0}</strong> pending
            </span>
          </div>
        </div>

        {/* High Priority Opportunities */}
        <div
          className={`kpi-card ${onFilterHighPriority ? 'kpi-clickable' : ''}`}
          onClick={onFilterHighPriority}
          title="Filter High Priority Leads"
        >
          <div className="kpi-header">
            <span className="kpi-label">High Priority Leads</span>
            <div className="kpi-icon-box bg-emerald-subtle text-emerald">
              <Flame size={18} />
            </div>
          </div>
          <div className="kpi-value text-emerald">{highPriority}</div>
          <div className="kpi-footer text-muted">
            <span>Score 80–100 · Ready for Outreach</span>
          </div>
        </div>

        {/* Active Buying Intent */}
        <div className="kpi-card">
          <div className="kpi-header">
            <span className="kpi-label">Active Intent</span>
            <div className="kpi-icon-box bg-purple-subtle text-purple">
              <Target size={18} />
            </div>
          </div>
          <div className="kpi-value">{activeIntent}</div>
          <div className="kpi-footer text-muted">
            <span>Classified as active intent; source verification may still be required</span>
          </div>
        </div>

        {/* Not Yet Exported Leads */}
        <div
          className={`kpi-card kpi-card-highlight ${onFilterUnexported ? 'kpi-clickable' : ''}`}
          onClick={onFilterUnexported}
          title="Filter Not Yet Exported Leads"
        >
          <div className="kpi-header">
            <span className="kpi-label">Not Yet Exported</span>
            <div className="kpi-icon-box bg-amber-subtle text-amber">
              <Download size={18} />
            </div>
          </div>
          <div className="kpi-value text-amber">{unexported}</div>
          <div className="kpi-footer">
            <span className="badge-unexported">Unexported Processed Leads</span>
          </div>
        </div>
      </div>

      {/* Visual Distribution Summary */}
      {metrics && (
        <div className="metrics-distribution-row">
          {/* Category Breakdown */}
          <div className="distribution-card">
            <h3 className="distribution-title">Service Categories</h3>
            <div className="distribution-bars">
              {Object.entries(metrics.category_counts || {}).map(([cat, count]) => {
                const pct = processed > 0 ? Math.round((count / processed) * 100) : 0;
                return (
                  <div key={cat} className="bar-row">
                    <div className="bar-label-group">
                      <span className="bar-label">{cat}</span>
                      <span className="bar-count">
                        {count} ({pct}%)
                      </span>
                    </div>
                    <div className="bar-track">
                      <div className="bar-fill bg-blue" style={{ width: `${pct}%` }}></div>
                    </div>
                  </div>
                );
              })}
              {Object.keys(metrics.category_counts || {}).length === 0 && (
                <p className="text-muted text-sm">No processed categories yet.</p>
              )}
            </div>
          </div>

          {/* Priority Breakdown */}
          <div className="distribution-card">
            <h3 className="distribution-title">Priority Breakdown</h3>
            <div className="priority-summary-container">
              <div className="priority-metric-chip chip-high">
                <span className="chip-count">{metrics.high_priority_leads}</span>
                <span className="chip-label">High Priority (80–100)</span>
              </div>
              <div className="priority-metric-chip chip-medium">
                <span className="chip-count">{metrics.medium_priority_leads}</span>
                <span className="chip-label">Medium Priority (50–79)</span>
              </div>
              <div className="priority-metric-chip chip-low">
                <span className="chip-count">{metrics.low_priority_leads}</span>
                <span className="chip-label">Low Priority (0–49)</span>
              </div>
            </div>
            <div className="intent-summary-line">
              <span className="text-muted text-sm">Intent Distribution: </span>
              <span className="text-sm">
                <strong>{metrics.active_intent_leads}</strong> Active ·{' '}
                <strong>{metrics.potential_intent_leads}</strong> Potential ·{' '}
                <strong>{metrics.unclear_intent_leads}</strong> Unclear
              </span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

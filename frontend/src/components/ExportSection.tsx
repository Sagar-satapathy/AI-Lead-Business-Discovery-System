import React, { useState } from 'react';
import { Download, FileSpreadsheet, CheckCircle2, AlertCircle, Clock, ShieldCheck, Check } from 'lucide-react';
import { DashboardMetrics } from '../types';
import { api } from '../services/api';

interface ExportSectionProps {
  metrics: DashboardMetrics | null;
  onExportConfirmed: () => void;
}

export const ExportSection: React.FC<ExportSectionProps> = ({
  metrics,
  onExportConfirmed,
}) => {
  const [scope, setScope] = useState('unexported');
  const [confirming, setConfirming] = useState(false);
  const [confirmMessage, setConfirmMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const unexportedCount = metrics?.not_yet_exported || 0;
  const processedCount = metrics?.processed_records || 0;
  const highMedCount =
    (metrics?.high_priority_leads || 0) + (metrics?.medium_priority_leads || 0);
  const totalCount = metrics?.total_records || 0;

  const handleDownload = (format: 'csv' | 'excel') => {
    setError(null);
    setConfirmMessage(null);
    const url =
      format === 'csv'
        ? api.getExportCsvUrl(scope)
        : api.getExportExcelUrl(scope);
    window.open(url, '_blank');
  };

  const handleConfirmExport = async () => {
    setConfirming(true);
    setError(null);
    setConfirmMessage(null);

    try {
      // Fetch matching lead IDs to confirm - strictly live-discovered leads
      const leadsRes = await api.getLeads({
        is_exported: scope === 'unexported' ? '0' : undefined,
        status: 'processed',
        relevance: 'Relevant',
        priority: scope === 'high_medium' ? 'High' : undefined,
        live_only: true,
        page_size: 100,
      });

      const leadIds = leadsRes.leads.map((l) => l.id);
      if (leadIds.length === 0) {
        setConfirmMessage('No eligible unexported leads to mark.');
        return;
      }

      const res = await api.confirmExport(leadIds);
      setConfirmMessage(res.message);
      onExportConfirmed();
    } catch (err: any) {
      setError(err.message || 'Failed to mark leads as exported.');
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="export-container">
      <div className="export-card">
        <div className="export-header-top">
          <div>
            <h2 className="export-title">Export Intelligence &amp; Procurement Reports</h2>
            <p className="export-desc">
              Download clean, standardized datasets formatted for CRM ingestion (Salesforce, HubSpot), ERP systems, or executive reviews.
            </p>
          </div>
          <span className="badge badge-neutral">
            <ShieldCheck size={14} /> RFC-4180 &amp; OpenPyXL Formatted
          </span>
        </div>

        {/* Scope Selection Cards */}
        <div className="export-scopes-grid">
          {/* Scope 1: Not Yet Exported */}
          <label
            className={`scope-card ${scope === 'unexported' ? 'scope-card-active' : ''}`}
            onClick={() => setScope('unexported')}
          >
            <div className="scope-radio-row">
              <input
                type="radio"
                name="export-scope"
                value="unexported"
                checked={scope === 'unexported'}
                onChange={() => setScope('unexported')}
              />
              <span className="scope-name">Not Yet Exported Leads</span>
            </div>
            <p className="scope-desc">
              Exports only newly live-discovered, processed leads that have not yet been downloaded (is_exported = 0). Prevents duplicate exports.
            </p>
            <div className="scope-footer">
              <span className="badge badge-unexported">
                <Clock size={12} /> {unexportedCount} Available
              </span>
            </div>
          </label>

          {/* Scope 2: All Processed Leads */}
          <label
            className={`scope-card ${scope === 'processed' ? 'scope-card-active' : ''}`}
            onClick={() => setScope('processed')}
          >
            <div className="scope-radio-row">
              <input
                type="radio"
                name="export-scope"
                value="processed"
                checked={scope === 'processed'}
                onChange={() => setScope('processed')}
              />
              <span className="scope-name">All Processed Live Leads</span>
            </div>
            <p className="scope-desc">
              All genuine live-discovered leads with completed AI evaluation and scoring (status = 'processed').
            </p>
            <div className="scope-footer">
              <span className="badge badge-neutral">{processedCount} Leads</span>
            </div>
          </label>

          {/* Scope 3: High & Medium Priority */}
          <label
            className={`scope-card ${scope === 'high_medium' ? 'scope-card-active' : ''}`}
            onClick={() => setScope('high_medium')}
          >
            <div className="scope-radio-row">
              <input
                type="radio"
                name="export-scope"
                value="high_medium"
                checked={scope === 'high_medium'}
                onChange={() => setScope('high_medium')}
              />
              <span className="scope-name">High &amp; Medium Priority</span>
            </div>
            <p className="scope-desc">
              High and Medium priority live leads scored &gt;= 50 points ready for direct sales outreach.
            </p>
            <div className="scope-footer">
              <span className="badge badge-high">{highMedCount} Leads</span>
            </div>
          </label>

          {/* Scope 4: All Leads */}
          <label
            className={`scope-card ${scope === 'all' ? 'scope-card-active' : ''}`}
            onClick={() => setScope('all')}
          >
            <div className="scope-radio-row">
              <input
                type="radio"
                name="export-scope"
                value="all"
                checked={scope === 'all'}
                onChange={() => setScope('all')}
              />
              <span className="scope-name">All Live Discovered Leads</span>
            </div>
            <p className="scope-desc">
              All genuine live-discovered leads in the pipeline (strictly excludes historical demonstration benchmarks and sample datasets).
            </p>
            <div className="scope-footer">
              <span className="badge badge-neutral">{totalCount} Records</span>
            </div>
          </label>
        </div>

        {/* Download Buttons Bar */}
        <div className="export-actions-row">
          <div className="download-buttons-group">
            <button
              onClick={() => handleDownload('csv')}
              className="btn btn-primary btn-download"
            >
              <Download size={16} /> Download CSV (UTF-8 BOM)
            </button>

            <button
              onClick={() => handleDownload('excel')}
              className="btn btn-secondary btn-download"
            >
              <FileSpreadsheet size={16} /> Download Styled Excel (.xlsx)
            </button>
          </div>

          {scope === 'unexported' && unexportedCount > 0 && (
            <button
              onClick={handleConfirmExport}
              disabled={confirming}
              className="btn btn-confirm-export"
              title="Marks downloaded leads as exported in the database"
            >
              {confirming ? (
                <>
                  <span className="spinner-icon"></span> Marking as Exported...
                </>
              ) : (
                <>
                  <Check size={16} /> Mark Downloaded as Exported
                </>
              )}
            </button>
          )}
        </div>

        {confirmMessage && (
          <div className="alert-banner alert-success mt-4">
            <CheckCircle2 size={16} /> {confirmMessage}
          </div>
        )}

        {error && (
          <div className="alert-banner alert-error mt-4">
            <AlertCircle size={16} /> {error}
          </div>
        )}
      </div>
    </div>
  );
};

import React, { useState } from 'react';
import { Download, FileSpreadsheet, CheckCircle2, AlertCircle, Clock, ShieldCheck, Check } from 'lucide-react';
import { DashboardMetrics } from '../types';
import { api } from '../services/api';

interface ExportSectionProps {
  metrics: DashboardMetrics | null;
  onExportConfirmed: () => void;
  selectedLeadIds?: number[];
  onClearSelection?: () => void;
  onNavigateToExplorer?: () => void;
}

export const ExportSection: React.FC<ExportSectionProps> = ({
  metrics,
  onExportConfirmed,
  selectedLeadIds = [],
  onClearSelection,
  onNavigateToExplorer,
}) => {
  const [scope, setScope] = useState('unexported');
  const [confirming, setConfirming] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [confirmMessage, setConfirmMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const unexportedCount = metrics?.not_yet_exported || 0;
  const processedCount = metrics?.processed_records || 0;
  const highMedCount =
    (metrics?.high_priority_leads || 0) + (metrics?.medium_priority_leads || 0);
  const totalCount = metrics?.total_records || 0;

  const hasSelection = selectedLeadIds.length > 0;
  const selectedCount = selectedLeadIds.length;

  const handleDownload = async (format: 'csv' | 'excel') => {
    setError(null);
    setConfirmMessage(null);

    if (selectedCount === 0) {
      setError('No leads selected. Please select at least one lead.');
      return;
    }

    setDownloading(format);
    try {
      // 1. Trigger export download for selected lead IDs
      await api.downloadExport(format, scope, selectedLeadIds);

      // 2. Automatically confirm export status for ONLY the selected lead IDs upon successful download
      const confirmRes = await api.confirmExport(selectedLeadIds);
      setConfirmMessage(confirmRes.message || `Successfully marked ${selectedCount} lead(s) as exported.`);

      // 3. Immediately notify parent to refresh metrics and lead explorer data
      onExportConfirmed();
    } catch (err: any) {
      setError(err.message || 'Export download failed. Leads were not marked as exported.');
    } finally {
      setDownloading(null);
    }
  };

  const handleConfirmExport = async () => {
    if (selectedCount === 0) {
      setError('No leads selected. Please select at least one lead.');
      return;
    }

    setConfirming(true);
    setError(null);
    setConfirmMessage(null);

    try {
      const res = await api.confirmExport(selectedLeadIds);
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

        {/* Selected Leads Banner */}
        {hasSelection ? (
          <div
            className="alert-banner alert-success"
            style={{
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <CheckCircle2 size={18} />
              <div>
                <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                  {selectedCount} lead{selectedCount > 1 ? 's' : ''} selected
                </span>{' '}
                for export from Lead Explorer.
                <span
                  style={{
                    display: 'block',
                    fontSize: '0.75rem',
                    opacity: 0.85,
                    marginTop: '2px',
                  }}
                >
                  Exports will contain only these {selectedCount} selected records.
                </span>
              </div>
            </div>
            {onClearSelection && (
              <button
                type="button"
                onClick={onClearSelection}
                className="btn btn-secondary btn-xs"
                style={{ fontSize: '0.75rem', padding: '4px 10px' }}
              >
                Clear Selection
              </button>
            )}
          </div>
        ) : (
          <div
            className="alert-banner alert-warning"
            style={{
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <AlertCircle size={18} />
              <div>
                <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                  No leads selected (0 selected)
                </span>
                <span
                  style={{
                    display: 'block',
                    fontSize: '0.75rem',
                    opacity: 0.85,
                    marginTop: '2px',
                  }}
                >
                  Please select at least one lead in Lead Explorer before generating an export.
                </span>
              </div>
            </div>
            {onNavigateToExplorer && (
              <button
                type="button"
                onClick={onNavigateToExplorer}
                className="btn btn-primary btn-xs"
                style={{ fontSize: '0.75rem', padding: '5px 12px' }}
              >
                Go to Lead Explorer →
              </button>
            )}
          </div>
        )}

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
              disabled={Boolean(downloading)}
              className="btn btn-primary btn-download"
            >
              {downloading === 'csv' ? (
                <>
                  <span className="spinner-icon"></span> Downloading CSV...
                </>
              ) : (
                <>
                  <Download size={16} /> Download CSV {hasSelection ? `(${selectedCount} Selected)` : ''} (UTF-8 BOM)
                </>
              )}
            </button>

            <button
              onClick={() => handleDownload('excel')}
              disabled={Boolean(downloading)}
              className="btn btn-secondary btn-download"
            >
              {downloading === 'excel' ? (
                <>
                  <span className="spinner-icon"></span> Downloading Excel...
                </>
              ) : (
                <>
                  <FileSpreadsheet size={16} /> Download Styled Excel {hasSelection ? `(${selectedCount} Selected)` : ''} (.xlsx)
                </>
              )}
            </button>
          </div>

          {hasSelection && (
            <button
              onClick={handleConfirmExport}
              disabled={confirming}
              className="btn btn-confirm-export"
              title="Marks selected leads as exported in the database"
            >
              {confirming ? (
                <>
                  <span className="spinner-icon"></span> Marking as Exported...
                </>
              ) : (
                <>
                  <Check size={16} /> Mark Selected ({selectedCount}) as Exported
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

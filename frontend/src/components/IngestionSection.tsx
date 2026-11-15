import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react';
import { api } from '../services/api';

interface IngestionSectionProps {
  onIngestionComplete: () => void;
}

export const IngestionSection: React.FC<IngestionSectionProps> = ({
  onIngestionComplete,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [stats, setStats] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Please select a valid CSV file (.csv).');
      return;
    }

    setUploading(true);
    setError(null);
    setStats(null);

    try {
      const res = await api.uploadCsv(file);
      setStats(res);
      onIngestionComplete();
    } catch (err: any) {
      setError(err.message || 'Failed to upload and validate CSV.');
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  return (
    <div className="ingestion-container">
      <div className="ingestion-card">
        <h2 className="ingestion-title">Data Ingestion &amp; Batch CSV Upload</h2>
        <p className="ingestion-desc">
          Upload custom procurement datasets, enterprise RFPs, or CRM exports. Automatic deduplication on business name and requirement prevents duplicate records.
        </p>

        {/* Drag and Drop Zone */}
        <div
          className={`dropzone ${dragActive ? 'dropzone-active' : ''} ${uploading ? 'dropzone-uploading' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            style={{ display: 'none' }}
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFile(e.target.files[0]);
              }
            }}
          />

          <div className="dropzone-inner">
            <div className="dropzone-icon-box">
              <UploadCloud size={36} className="text-blue" />
            </div>
            <h3 className="dropzone-text">
              {uploading ? 'Validating & Ingesting Dataset...' : 'Drag and drop your CSV file here, or click to browse'}
            </h3>
            <p className="dropzone-subtext text-muted text-sm">
              Standard RFC-4180 CSV files up to 25 MB supported
            </p>
          </div>
        </div>

        {/* Required Schema Specification */}
        <div className="schema-specs-card">
          <h4 className="schema-title">Mandatory CSV Schema Columns:</h4>
          <div className="schema-tags">
            <code>business_name</code>
            <code>requirement</code>
            <code>source_name</code>
            <code>source_url</code>
            <code>location</code>
            <code>date_found</code>
          </div>
        </div>

        {error && <div className="alert-banner alert-error mt-4">{error}</div>}

        {stats && (
          <div className="ingestion-stats-banner mt-4">
            <div className="stats-header">
              <CheckCircle2 size={20} className="text-emerald" />
              <h4>{stats.message}</h4>
            </div>
            <div className="stats-grid">
              <div className="stat-pill">
                <span className="stat-num text-emerald">{stats.inserted_count}</span>
                <span className="stat-desc">New Leads Ingested</span>
              </div>
              <div className="stat-pill">
                <span className="stat-num text-amber">{stats.duplicates_skipped}</span>
                <span className="stat-desc">Duplicates Skipped</span>
              </div>
              <div className="stat-pill">
                <span className="stat-num">{stats.validation_stats?.raw_count || 0}</span>
                <span className="stat-desc">Raw Rows In File</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

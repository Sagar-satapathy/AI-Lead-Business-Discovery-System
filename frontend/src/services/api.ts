/**
 * frontend/src/services/api.ts - Typed REST API Client
 */

import {
  Lead,
  DashboardMetrics,
  HealthStatus,
  DiscoveryQuery,
  DiscoveryResult,
  DiscoveredLead,
  LeadFilterState,
} from '../types';

const API_BASE = '/api';

export const api = {
  async getHealth(): Promise<HealthStatus> {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Failed to fetch system health status.');
    return res.json();
  },

  async getMetrics(): Promise<DashboardMetrics> {
    const res = await fetch(`${API_BASE}/metrics?_t=${Date.now()}`, {
      cache: 'no-store',
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        Pragma: 'no-cache',
      },
    });
    if (!res.ok) throw new Error('Failed to fetch dashboard metrics.');
    return res.json();
  },

  async getLeads(filters: Partial<LeadFilterState>): Promise<{
    leads: Lead[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
  }> {
    const params = new URLSearchParams();
    if (filters.search) params.append('search', filters.search);
    if (filters.category && filters.category !== 'All') params.append('category', filters.category);
    if (filters.priority && filters.priority !== 'All') params.append('priority', filters.priority);
    if (filters.buying_intent && filters.buying_intent !== 'All') params.append('buying_intent', filters.buying_intent);
    if (filters.relevance && filters.relevance !== 'All') params.append('relevance', filters.relevance);
    if (filters.status && filters.status !== 'All') params.append('status', filters.status);
    if (filters.is_exported !== undefined && filters.is_exported !== 'All' && filters.is_exported !== '') {
      let expVal = filters.is_exported;
      if (expVal === 'Exported') expVal = '1';
      if (expVal === 'Not Exported' || expVal === 'Unexported') expVal = '0';
      params.append('is_exported', expVal);
    }
    if (filters.record_type && filters.record_type !== 'All') params.append('record_type', filters.record_type);
    if (filters.verification_status && filters.verification_status !== 'All') params.append('verification_status', filters.verification_status);
    if (filters.source_page_type && filters.source_page_type !== 'All') params.append('source_page_type', filters.source_page_type);
    if (filters.live_only !== undefined) params.append('live_only', String(filters.live_only));
    if (filters.is_live_discovery !== undefined && filters.is_live_discovery !== 'All' && filters.is_live_discovery !== '') {
      params.append('is_live_discovery', String(filters.is_live_discovery));
    }
    if (filters.order_by) params.append('order_by', filters.order_by);
    if (filters.page) params.append('page', String(filters.page));
    if (filters.page_size) params.append('page_size', String(filters.page_size));

    const res = await fetch(`${API_BASE}/leads?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch leads list.');
    return res.json();
  },

  async getLeadById(id: number): Promise<Lead> {
    const res = await fetch(`${API_BASE}/leads/${id}`);
    if (!res.ok) throw new Error(`Lead with ID ${id} not found.`);
    return res.json();
  },

  async createLead(data: {
    business_name: string;
    requirement: string;
    source_name?: string;
    source_url?: string;
    location?: string;
  }): Promise<{ message: string; lead: Lead }> {
    const res = await fetch(`${API_BASE}/leads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create lead.');
    }
    return res.json();
  },

  async analyzeSingleLead(
    id: number,
    provider?: string
  ): Promise<{ success: boolean; message: string; lead: Lead }> {
    const url = provider
      ? `${API_BASE}/leads/${id}/analyze?provider=${encodeURIComponent(provider)}`
      : `${API_BASE}/leads/${id}/analyze`;
    const res = await fetch(url, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.message || data.detail || 'Analysis evaluation failed.');
    }
    return data;
  },

  async verifySource(
    id: number
  ): Promise<{ success: boolean; message: string; verification: any; lead: Lead }> {
    const res = await fetch(`${API_BASE}/leads/${id}/verify-source`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.message || data.detail || 'Source verification request failed.');
    }
    return data;
  },

  async analyzeBatch(
    lead_ids?: number[],
    provider?: string,
    all_unprocessed: boolean = true
  ): Promise<{
    message: string;
    processed_count: number;
    failed_count: number;
    results: Array<{ id: number; status: string; score?: number; error?: string }>;
  }> {
    const res = await fetch(`${API_BASE}/leads/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lead_ids: lead_ids || null,
        provider: provider || null,
        all_unprocessed,
      }),
    });
    if (!res.ok) throw new Error('Batch evaluation request failed.');
    return res.json();
  },

  async discoverLeads(query: DiscoveryQuery): Promise<DiscoveryResult> {
    const res = await fetch(`${API_BASE}/discover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(query),
    });
    if (!res.ok) throw new Error('Business discovery search failed.');
    return res.json();
  },

  async getCurrentDiscoveryBatch(): Promise<{ candidates: DiscoveredLead[]; count: number }> {
    const res = await fetch(`${API_BASE}/discovery/current-batch`);
    if (!res.ok) throw new Error('Failed to fetch current discovery batch.');
    return res.json();
  },

  async saveDiscoveryBatch(candidates?: DiscoveredLead[]): Promise<{
    success: boolean;
    saved_count: number;
    duplicates_skipped: number;
    message: string;
  }> {
    const res = await fetch(`${API_BASE}/discovery/save-batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidates: candidates || null }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Failed to save discovery batch.');
    }
    return res.json();
  },

  async clearDiscoveryBatch(): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/discovery/clear-batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) throw new Error('Failed to clear discovery batch.');
    return res.json();
  },

  async uploadCsv(file: File): Promise<{
    message: string;
    validation_stats: Record<string, any>;
    inserted_count: number;
    duplicates_skipped: number;
  }> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/leads/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'CSV upload failed validation.');
    }
    return res.json();
  },

  getExportCsvUrl(scope: string, lead_ids?: number[]): string {
    let url = `${API_BASE}/export/csv?scope=${encodeURIComponent(scope)}`;
    if (lead_ids && lead_ids.length > 0) {
      url += `&lead_ids=${encodeURIComponent(lead_ids.join(','))}`;
    }
    return url;
  },

  getExportExcelUrl(scope: string, lead_ids?: number[]): string {
    let url = `${API_BASE}/export/excel?scope=${encodeURIComponent(scope)}`;
    if (lead_ids && lead_ids.length > 0) {
      url += `&lead_ids=${encodeURIComponent(lead_ids.join(','))}`;
    }
    return url;
  },

  async downloadExport(format: 'csv' | 'excel', scope: string, lead_ids?: number[]): Promise<void> {
    const url = format === 'csv' ? this.getExportCsvUrl(scope, lead_ids) : this.getExportExcelUrl(scope, lead_ids);
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'No leads selected. Please select at least one lead.');
    }
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : `leads_export.${format === 'csv' ? 'csv' : 'xlsx'}`;

    const blobUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(blobUrl);
  },

  async confirmExport(lead_ids: number[]): Promise<{
    success: boolean;
    message: string;
    exported_count: number;
  }> {
    const res = await fetch(`${API_BASE}/export/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_ids }),
    });
    if (!res.ok) throw new Error('Failed to confirm export status.');
    return res.json();
  },
};

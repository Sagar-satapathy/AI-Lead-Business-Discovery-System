import React, { useState, useEffect, useCallback } from 'react';
import {
  Users,
  Compass,
  UploadCloud,
  Download,
  AlertCircle,
  Sparkles,
} from 'lucide-react';

import {
  Lead,
  DashboardMetrics,
  HealthStatus,
  LeadFilterState,
} from './types';
import { api } from './services/api';
import { Navbar } from './components/Navbar';
import { KPISection } from './components/KPISection';
import { LeadExplorer } from './components/LeadExplorer';
import { DiscoverySection } from './components/DiscoverySection';
import { IngestionSection } from './components/IngestionSection';
import { ExportSection } from './components/ExportSection';
import { LeadDetailModal } from './components/LeadDetailModal';

export const App: React.FC = () => {
  // Theme state
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return localStorage.getItem('theme') === 'dark';
  });

  // Active Tab
  const [activeTab, setActiveTab] = useState<'explorer' | 'discovery' | 'ingestion' | 'export'>('discovery');

  // Core Data States
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [totalLeads, setTotalLeads] = useState<number>(0);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);

  // Loading States
  const [loadingLeads, setLoadingLeads] = useState<boolean>(true);
  const [loadingMetrics, setLoadingMetrics] = useState<boolean>(true);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Filters State - Default to genuine live-discovered leads
  const [filters, setFilters] = useState<LeadFilterState>({
    search: '',
    category: 'All',
    priority: 'All',
    buying_intent: 'All',
    relevance: 'Relevant',
    status: 'processed',
    is_exported: 'All',
    record_type: 'discovered',
    verification_status: 'All',
    order_by: 'score_desc',
    page: 1,
    page_size: 25,
    live_only: true,
  });

  // Theme Toggle
  const toggleTheme = () => {
    const next = !darkMode;
    setDarkMode(next);
    localStorage.setItem('theme', next ? 'dark' : 'light');
  };

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark-theme');
    } else {
      document.documentElement.classList.remove('dark-theme');
    }
  }, [darkMode]);

  // Load Health & Metrics
  const loadSystemData = useCallback(async () => {
    setLoadingMetrics(true);
    try {
      const [h, m] = await Promise.all([api.getHealth(), api.getMetrics()]);
      setHealth(h);
      setMetrics(m);
    } catch (err: any) {
      console.error('System data load error:', err);
    } finally {
      setLoadingMetrics(false);
    }
  }, []);

  // Load Leads matching current filter state
  const loadLeads = useCallback(async () => {
    setLoadingLeads(true);
    try {
      const data = await api.getLeads(filters);
      setLeads(data.leads);
      setTotalLeads(data.total);
    } catch (err: any) {
      console.error('Leads fetch error:', err);
      showNotification('error', 'Failed to retrieve leads from server.');
    } finally {
      setLoadingLeads(false);
    }
  }, [filters]);

  useEffect(() => {
    loadSystemData();
  }, [loadSystemData]);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const handleFilterChange = (newFilters: Partial<LeadFilterState>) => {
    setFilters((prev) => ({ ...prev, ...newFilters }));
  };

  // KPI Quick filter shortcuts
  const handleFilterUnexported = () => {
    setActiveTab('explorer');
    setFilters((prev) => ({
      ...prev,
      is_exported: '0',
      status: 'processed',
      relevance: 'Relevant',
      live_only: true,
      page: 1,
    }));
  };

  const handleFilterHighPriority = () => {
    setActiveTab('explorer');
    setFilters((prev) => ({
      ...prev,
      priority: 'High',
      status: 'processed',
      relevance: 'Relevant',
      live_only: true,
      page: 1,
    }));
  };

  // Batch Evaluation Action
  const handleBatchAnalyze = async (provider?: string) => {
    setIsEvaluating(true);
    try {
      const res = await api.analyzeBatch(undefined, provider, true);
      showNotification('success', res.message);
      await Promise.all([loadSystemData(), loadLeads()]);
    } catch (err: any) {
      showNotification('error', err.message || 'Batch evaluation failed.');
    } finally {
      setIsEvaluating(false);
    }
  };

  // Inspect specific lead by ID (e.g. from Discovery section)
  const handleInspectLeadById = async (id: number) => {
    try {
      const lead = await api.getLeadById(id);
      setSelectedLead(lead);
    } catch (err: any) {
      showNotification('error', err.message || 'Failed to open lead.');
    }
  };

  // Refresh all state
  const handleRefreshAll = () => {
    loadSystemData();
    loadLeads();
    showNotification('success', 'Refreshed system data and metrics.');
  };

  return (
    <div className={`app-shell ${darkMode ? 'dark-theme' : ''}`}>
      {/* Top Navbar */}
      <Navbar
        health={health}
        darkMode={darkMode}
        onToggleTheme={toggleTheme}
        onRefresh={handleRefreshAll}
        isEvaluating={isEvaluating}
      />

      <main className="main-content">
        {/* Toast Notification */}
        {notification && (
          <div className={`global-toast toast-${notification.type}`}>
            <span>{notification.message}</span>
            <button onClick={() => setNotification(null)} className="toast-close">
              ×
            </button>
          </div>
        )}

        {/* Global KPI Metrics Header */}
        <KPISection
          metrics={metrics}
          loading={loadingMetrics}
          onFilterUnexported={handleFilterUnexported}
          onFilterHighPriority={handleFilterHighPriority}
        />

        {/* Core Workflow Navigation Tabs */}
        <div className="tab-navigation-container">
          <button
            className={`nav-tab ${activeTab === 'discovery' ? 'nav-tab-active' : ''}`}
            onClick={() => setActiveTab('discovery')}
          >
            <Compass size={16} />
            <span>Business Discovery</span>
          </button>

          <button
            className={`nav-tab ${activeTab === 'explorer' ? 'nav-tab-active' : ''}`}
            onClick={() => setActiveTab('explorer')}
          >
            <Users size={16} />
            <span>Lead Explorer</span>
            <span className="tab-counter">{totalLeads}</span>
          </button>

          <button
            className={`nav-tab ${activeTab === 'export' ? 'nav-tab-active' : ''}`}
            onClick={() => setActiveTab('export')}
          >
            <Download size={16} />
            <span>Export Intelligence</span>
            {metrics && metrics.not_yet_exported > 0 && (
              <span className="tab-badge-accent">{metrics.not_yet_exported}</span>
            )}
          </button>
        </div>

        {/* Active Tab Workspace */}
        <div className="tab-workspace">
          {activeTab === 'explorer' && (
            <LeadExplorer
              leads={leads}
              total={totalLeads}
              loading={loadingLeads}
              filters={filters}
              onFilterChange={handleFilterChange}
              onSelectLead={(lead) => setSelectedLead(lead)}
              onBatchAnalyze={handleBatchAnalyze}
              onNavigateToDiscovery={() => setActiveTab('discovery')}
              isEvaluating={isEvaluating}
            />
          )}

          {activeTab === 'discovery' && (
            <DiscoverySection
              isLiveConnected={Boolean(health?.discovery?.live_search_configured)}
              onDiscoveryComplete={() => {
                loadSystemData();
                loadLeads();
              }}
              onInspectLead={handleInspectLeadById}
            />
          )}

          {activeTab === 'ingestion' && (
            <IngestionSection
              onIngestionComplete={() => {
                loadSystemData();
                loadLeads();
              }}
            />
          )}

          {activeTab === 'export' && (
            <ExportSection
              metrics={metrics}
              onExportConfirmed={() => {
                loadSystemData();
                loadLeads();
              }}
            />
          )}
        </div>
      </main>

      {/* Deep Inspection Modal */}
      {selectedLead && (
        <LeadDetailModal
          lead={selectedLead}
          onClose={() => setSelectedLead(null)}
          onLeadUpdated={(updated) => {
            setSelectedLead(updated);
            loadSystemData();
            loadLeads();
          }}
        />
      )}
    </div>
  );
};

import React, { useState, useEffect, useCallback } from 'react';
import {
  LayoutDashboard,
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
  DiscoveryResult,
} from './types';
import { api } from './services/api';
import { Navbar } from './components/Navbar';
import { DashboardSection } from './components/DashboardSection';
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

  // Active Tab: Added dedicated 'dashboard' as primary view
  const [activeTab, setActiveTab] = useState<'dashboard' | 'explorer' | 'discovery' | 'ingestion' | 'export'>('dashboard');

  // Core Data States
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [totalLeads, setTotalLeads] = useState<number>(0);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [selectedLeadIds, setSelectedLeadIds] = useState<number[]>([]);

  // Loading States
  const [loadingLeads, setLoadingLeads] = useState<boolean>(true);
  const [loadingMetrics, setLoadingMetrics] = useState<boolean>(true);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Lifted Discovery State (persists across tab navigation and browser refresh)
  const [discoveryState, setDiscoveryState] = useState<string>(() => {
    return sessionStorage.getItem('discovery_state') || '';
  });
  const [discoveryCategory, setDiscoveryCategory] = useState<string>(() => {
    return sessionStorage.getItem('discovery_category') || '';
  });
  const [discoveryService, setDiscoveryService] = useState<string>(() => {
    return sessionStorage.getItem('discovery_service') || '';
  });
  const [discoveryResult, setDiscoveryResult] = useState<DiscoveryResult | null>(() => {
    try {
      const saved = sessionStorage.getItem('discovery_result');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  // Filters State - Default to unfiltered saved records so count matches Dashboard Total Leads exactly
  const [filters, setFilters] = useState<LeadFilterState>({
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
    page_size: 25,
    live_only: false,
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

  useEffect(() => {
    if (activeTab === 'dashboard') {
      loadSystemData();
      loadLeads();
    } else if (activeTab === 'explorer') {
      loadLeads();
    }
  }, [activeTab, loadSystemData, loadLeads]);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const handleFilterChange = (newFilters: Partial<LeadFilterState>) => {
    setFilters((prev) => ({ ...prev, ...newFilters }));
  };

  // Navigate to Lead Explorer with optional custom filter criteria (e.g. from Dashboard KPI cards)
  const handleNavigateToExplorer = (customFilters?: Partial<LeadFilterState>) => {
    if (customFilters) {
      setFilters((prev) => ({
        ...prev,
        ...customFilters,
        page: 1,
      }));
    }
    setActiveTab('explorer');
  };

  // KPI Quick filter shortcuts
  const handleFilterUnexported = () => {
    handleNavigateToExplorer({
      is_exported: '0',
      status: 'processed',
      relevance: 'Relevant',
      live_only: true,
      page: 1,
    });
  };

  const handleFilterHighPriority = () => {
    handleNavigateToExplorer({
      priority: 'High',
      status: 'processed',
      relevance: 'Relevant',
      live_only: true,
      page: 1,
    });
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

        {/* Core Workflow Navigation Tabs - REQUIREMENT 1: Added Separate Dedicated Dashboard Item */}
        <div className="tab-navigation-container">
          <button
            className={`nav-tab ${activeTab === 'dashboard' ? 'nav-tab-active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <LayoutDashboard size={16} />
            <span>Dashboard</span>
          </button>

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
            {selectedLeadIds.length > 0 ? (
              <span className="tab-badge-accent" title={`${selectedLeadIds.length} lead(s) selected for export`}>
                {selectedLeadIds.length}
              </span>
            ) : metrics && metrics.not_yet_exported > 0 ? (
              <span className="tab-badge-accent">{metrics.not_yet_exported}</span>
            ) : null}
          </button>
        </div>

        {/* Active Tab Workspace */}
        <div className="tab-workspace">
          {/* REQUIREMENT 1: Dedicated Dashboard Section */}
          <div style={{ display: activeTab === 'dashboard' ? 'block' : 'none' }}>
            <DashboardSection
              metrics={metrics}
              loading={loadingMetrics}
              onNavigateToExplorer={handleNavigateToExplorer}
              onNavigateToDiscovery={() => setActiveTab('discovery')}
              onInspectLead={handleInspectLeadById}
              onRefresh={handleRefreshAll}
            />
          </div>

          <div style={{ display: activeTab === 'explorer' ? 'block' : 'none' }}>
            <LeadExplorer
              leads={leads}
              total={totalLeads}
              loading={loadingLeads}
              filters={filters}
              onFilterChange={handleFilterChange}
              onSelectLead={(lead) => setSelectedLead(lead)}
              onBatchAnalyze={handleBatchAnalyze}
              onNavigateToDiscovery={() => setActiveTab('discovery')}
              onNavigateToExport={() => setActiveTab('export')}
              selectedLeadIds={selectedLeadIds}
              onSelectionChange={setSelectedLeadIds}
              isEvaluating={isEvaluating}
            />
          </div>

          <div style={{ display: activeTab === 'discovery' ? 'block' : 'none' }}>
            <DiscoverySection
              isLiveConnected={Boolean(health?.discovery?.live_search_configured)}
              onDiscoveryComplete={() => {
                loadSystemData();
                loadLeads();
              }}
              onInspectLead={handleInspectLeadById}
              state={discoveryState}
              setState={setDiscoveryState}
              category={discoveryCategory}
              setCategory={setDiscoveryCategory}
              service={discoveryService}
              setService={setDiscoveryService}
              result={discoveryResult}
              setResult={setDiscoveryResult}
            />
          </div>

          <div style={{ display: activeTab === 'ingestion' ? 'block' : 'none' }}>
            <IngestionSection
              onIngestionComplete={() => {
                loadSystemData();
                loadLeads();
              }}
            />
          </div>

          <div style={{ display: activeTab === 'export' ? 'block' : 'none' }}>
            <ExportSection
              metrics={metrics}
              selectedLeadIds={selectedLeadIds}
              onClearSelection={() => setSelectedLeadIds([])}
              onNavigateToExplorer={() => setActiveTab('explorer')}
              onExportConfirmed={() => {
                loadSystemData();
                loadLeads();
              }}
            />
          </div>
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

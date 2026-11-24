'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence, MotionConfig } from 'framer-motion';
import { AlertCircle } from 'lucide-react';
import { ScopeLayer } from '../components/ScopeLayer';
import { LoadingScreen } from '../components/LoadingScreen';
import { SiteHeader } from '../components/SiteHeader';
import { HomeLanding } from '../components/HomeLanding';
import { MarketExplorerView } from '../components/MarketExplorerView';
import { SimulatorPage, AnalyzerView, WarehouseView } from '../components/PagesSimulatorNlp';

const EASE = [0.22, 1, 0.36, 1];

const TOP_NAV = [
  {
    id: 'home',
    short: 'HOME',
    label: 'Home',
    title: 'SkillScope Career & Market Intelligence',
    subtitle: 'Interactive AI Web Product + Multi-Year Lakehouse (2020–2025)',
  },
  {
    id: 'coach',
    short: 'COACH',
    label: 'Skill-Gap Coach',
    title: 'AI Skill-Gap Coach & Roadmap',
    subtitle: 'Mamdani Fuzzy Priority Engine + Live MySQL 8.0 Write-Back',
  },
  {
    id: 'analyzer',
    short: 'ANALYZER',
    label: 'JD Analyzer',
    title: 'Live ESCO NLP Job & Resume Analyzer',
    subtitle: '86 ESCO Skills • Context Disambiguation • 95.98% Audited F1',
  },
  {
    id: 'market',
    short: 'MARKET',
    label: 'Market & Salaries',
    title: '2020–2025 Market Trends & Global Salaries',
    subtitle: '424,980 Stack Overflow Devs • 151,439 Salaries • 32,394 Postings',
  },
  {
    id: 'warehouse',
    short: 'WAREHOUSE',
    label: 'Warehouse',
    title: 'DWBI Lakehouse, Schema & Data Marts',
    subtitle: '50/50 Quality Gate • Constellation Schema • MySQL EXPLAIN ANALYZE',
  },
];

export default function SkillScopeStudioPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('home');
  const [introDone, setIntroDone] = useState(false);

  const [selectedRoleKey, setSelectedRoleKey] = useState(1);
  const [selectedSkillKeys, setSelectedSkillKeys] = useState(() => new Set([1, 2, 24, 25, 30]));
  const titleRef = useRef(null);

  useEffect(() => {
    let active = true;
    fetch('/api/data')
      .then((res) => {
        if (!res.ok) throw new Error(`API returned HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => {
        if (active) setData(json);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleNavigate = (tabId) => {
    setActiveTab(tabId);
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });
    requestAnimationFrame(() => {
      titleRef.current?.focus({ preventScroll: true });
    });
  };

  const handleSendSkillsToSimulator = (nlpOut) => {
    const keys = (nlpOut.skills || []).map((s) => s.skill_key);
    if (keys.length > 0) setSelectedSkillKeys(new Set(keys));
    if (nlpOut.inferred_role_key && nlpOut.inferred_role_key !== 17) {
      setSelectedRoleKey(nlpOut.inferred_role_key);
    }
    handleNavigate('coach');
  };

  const activeMeta = TOP_NAV.find((t) => t.id === activeTab) || TOP_NAV[0];
  const recon = data?.etl_reconciliation || {};

  return (
    <MotionConfig reducedMotion="user">
      <ScopeLayer />

      <div className="nside-grid-lines" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </div>

      {!introDone && <LoadingScreen onFinish={() => setIntroDone(true)} />}

      <SiteHeader items={TOP_NAV} activeTab={activeTab} onNavigate={handleNavigate} />

      <main
        data-inert-when-menu=""
        className={activeTab === 'home' ? 'studio-fullbleed' : 'studio-container studio-main-padded'}
      >
        {activeTab !== 'home' && (
          <div className="view-header">
            <div>
              <AnimatePresence mode="wait">
                <motion.h2
                  key={activeMeta.id}
                  ref={titleRef}
                  tabIndex={-1}
                  className="page-title"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.34, ease: EASE }}
                >
                  {activeMeta.title}
                </motion.h2>
              </AnimatePresence>
              <p>{activeMeta.subtitle}</p>
            </div>
            <div className="badge-row">
              <span className="badge">
                {recon.overall_status
                  ? `Quality Gate: ${recon.overall_status} (${recon.checks_passed}/${recon.checks_total})`
                  : '2020–2025 Lakehouse'}
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className={activeTab === 'home' ? 'studio-container studio-main-padded' : ''}>
            <div className="status-toast err" style={{ marginBottom: 18 }}>
              <AlertCircle size={18} />
              <span>
                Could not load backend API (`/api/data`: {error}). Ensure `python frontend/app.py` is running on port 8050.
              </span>
            </div>
          </div>
        )}

        {!data && !error && (
          <div className={activeTab === 'home' ? 'studio-container studio-main-padded' : ''}>
            <div className="kpi-grid">
              {[0, 1, 2, 3, 4].map((i) => (
                <div key={i} className="skeleton-card" aria-hidden="true" />
              ))}
            </div>
          </div>
        )}

        {data && (
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.38, ease: EASE }}
            >
              {activeTab === 'home' && <HomeLanding data={data} onNavigate={handleNavigate} />}
              {activeTab === 'coach' && (
                <SimulatorPage
                  data={data}
                  selectedRoleKey={selectedRoleKey}
                  setSelectedRoleKey={setSelectedRoleKey}
                  selectedSkillKeys={selectedSkillKeys}
                  setSelectedSkillKeys={setSelectedSkillKeys}
                />
              )}
              {activeTab === 'analyzer' && (
                <AnalyzerView data={data} onSendSkillsToSimulator={handleSendSkillsToSimulator} />
              )}
              {activeTab === 'market' && <MarketExplorerView data={data} />}
              {activeTab === 'warehouse' && <WarehouseView data={data} />}
            </motion.div>
          </AnimatePresence>
        )}
      </main>

      <footer data-inert-when-menu="" className="rythm-footer">
        <div className="ns-inner rythm-footer-inner">
          <div>
            <strong className="rythm-footer-brand">SkillScope Studio</strong> ·{' '}
            <span>Next.js + React + Python Lakehouse + MySQL 8.0</span>
          </div>
          <div className="rythm-footer-meta">
            FAST-NUCES Karachi (BDS-5B) · CS-4040 Data Warehousing &amp; BI
          </div>
        </div>
      </footer>
    </MotionConfig>
  );
}

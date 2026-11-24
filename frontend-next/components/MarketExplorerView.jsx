'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MarketOverviewPage,
  SkillDemandPage,
} from './PagesOverviewDemand';
import {
  TrendsForecastPage,
  SalaryInsightsPage,
  RelationshipsPage,
  SurveyMarketPage,
} from './PagesTrendsSalary';

const SUB_TABS = [
  { id: 'trends', label: '6-Year Skill Trends & Forecast' },
  { id: 'salaries', label: '2020–2025 Global Salaries' },
  { id: 'demand', label: 'Role & ESCO Skill Demand' },
  { id: 'overview', label: 'Hiring Hubs & Market Snapshot' },
  { id: 'drivers', label: 'Skill Co-Occurrence & Survey Gap' },
];

export function MarketExplorerView({ data, motionPaused }) {
  const [subTab, setSubTab] = useState('trends');

  return (
    <div>
      <div className="slicer-row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <div className="seg-tabs" role="tablist" aria-label="Market Explorer Sections">
          {SUB_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={subTab === t.id}
              className={`seg-tab-btn ${subTab === t.id ? 'active' : ''}`}
              onClick={() => setSubTab(t.id)}
            >
              {subTab === t.id && (
                <motion.span
                  layoutId="marketSubTab"
                  className="seg-tab-pill"
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
              {t.label}
            </button>
          ))}
        </div>
        <span className="panel-sub">
          Public interactive explorer backed by Gold Parquet &amp; MySQL 8.0
        </span>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={subTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2 }}
        >
          {subTab === 'trends' && <TrendsForecastPage data={data} />}
          {subTab === 'salaries' && <SalaryInsightsPage data={data} />}
          {subTab === 'demand' && <SkillDemandPage data={data} />}
          {subTab === 'overview' && <MarketOverviewPage data={data} motionPaused={motionPaused} />}
          {subTab === 'drivers' && (
            <div>
              <RelationshipsPage data={data} />
              <SurveyMarketPage data={data} />
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

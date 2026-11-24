'use client';

import React, { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  ComposedChart,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
} from 'recharts';
import { EditorialPanel, EditorialTooltip, EditorialHeatmap, PALETTE, SERIES_COLORS } from './MotionPrimitives';

export function TrendsForecastPage({ data }) {
  const [viewMode, setViewMode] = useState('history');
  const [stackPreset, setStackPreset] = useState('ai_data');

  const stackTabs = [
    { id: 'ai_data', label: 'AI & Data Stack' },
    { id: 'cloud_devops', label: 'Cloud & DevOps' },
    { id: 'web_lang', label: 'Web & Systems' },
    { id: 'top_rising', label: 'Top 5 Risers' },
  ];

  const heroSkills = useMemo(() => {
    const presets = {
      ai_data: ['Python', 'SQL', 'Generative AI & LLMs', 'PostgreSQL', 'Pandas & NumPy', 'PyTorch'],
      cloud_devops: ['Docker', 'Kubernetes', 'AWS', 'Microsoft Azure', 'Linux', 'CI/CD & Git'],
      web_lang: ['JavaScript', 'TypeScript', 'React', 'Node.js', 'Go', 'Rust'],
    };
    if (stackPreset === 'top_rising') {
      return (data.historical_skill_growth || [])
        .filter((r) => r.comparable_2020_2025 === 1)
        .sort((a, b) => b.delta_pp - a.delta_pp)
        .slice(0, 6)
        .map((r) => r.skill_name);
    }
    return presets[stackPreset] || presets.ai_data;
  }, [data.historical_skill_growth, stackPreset]);

  const heroChartData = useMemo(() => {
    const years = [2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027];
    return years.map((yr) => {
      const point = { year: yr };
      heroSkills.forEach((sk) => {
        const hit = (data.historical_skill_forecast || []).find(
          (r) => r.skill_name === sk && r.year_num === yr && (r.adoption_pct > 0 || yr >= 2023)
        );
        if (hit) point[sk] = hit.adoption_pct;
      });
      return point;
    });
  }, [data.historical_skill_forecast, heroSkills]);

  const { smCards, divergingBars } = useMemo(() => {
    if (viewMode === 'history' && (data.historical_skill_growth || []).length > 0) {
      const comp = [...data.historical_skill_growth]
        .filter((r) => r.comparable_2020_2025 === 1)
        .sort((a, b) => b.delta_pp - a.delta_pp);

      const rising = comp.slice(0, 3).map((r) => ({
        name: r.skill_name,
        tag: `5yr +${r.delta_pp.toFixed(1)} pp`,
        color: PALETTE.teal,
        rising: true,
      }));
      const cooling = comp
        .slice(-3)
        .reverse()
        .map((r) => ({
          name: r.skill_name,
          tag: `5yr ${r.delta_pp.toFixed(1)} pp`,
          color: PALETTE.coral,
          rising: false,
        }));

      const cards = [...rising, ...cooling].map((c) => {
        const rows = (data.historical_skill_forecast || [])
          .filter((t) => t.skill_name === c.name)
          .sort((a, b) => a.year_num - b.year_num)
          .map((t) => ({
            x: t.year_num,
            hist: t.record_type === 'Historical' ? t.adoption_pct : null,
            fcst: t.record_type === 'Forecast' || t.year_num === 2025 ? t.adoption_pct : null,
          }));
        return { ...c, rows };
      });

      const bars = [...comp.slice(-8), ...comp.slice(0, 12)].map((r) => ({
        name: r.skill_name,
        val: r.delta_pp,
      }));
      return { smCards: cards, divergingBars: bars };
    }

    // LinkedIn 2023 waves fallback
    const sigYoy = [...(data.skill_yoy || [])]
      .filter((r) => (r.total_mentions || r.mentions_2023 + r.mentions_2024) >= 20)
      .sort((a, b) => b.yoy_growth_pct - a.yoy_growth_pct);

    const rising = sigYoy.slice(0, 3).map((r) => ({
      name: r.skill_name,
      tag: `Rising (+${r.yoy_growth_pct.toFixed(1)}%)`,
      color: PALETTE.teal,
      rising: true,
    }));
    const cooling = sigYoy
      .slice(-3)
      .reverse()
      .map((r) => ({
        name: r.skill_name,
        tag: `Cooling (${r.yoy_growth_pct.toFixed(1)}%)`,
        color: PALETTE.coral,
        rising: false,
      }));

    const cards = [...rising, ...cooling].map((c) => {
      const sub = (data.skill_trends || [])
        .filter((t) => t.skill_name === c.name && t.year_month !== '2023-06' && t.year_month !== '2023-09')
        .sort((a, b) => a.year_month.localeCompare(b.year_month));
      const lastHist = [...sub].reverse().find((x) => x.record_type === 'Historical')?.year_month;
      const rows = sub.map((t) => ({
        x: t.year_month,
        hist: t.record_type === 'Historical' ? t.demand_share_pct : null,
        fcst: t.record_type === 'Forecast' || t.year_month === lastHist ? t.demand_share_pct : null,
      }));
      return { ...c, rows };
    });

    const bars = [...sigYoy.slice(-7), ...sigYoy.slice(0, 12)].map((r) => ({
      name: r.skill_name,
      val: r.yoy_growth_pct,
    }));
    return { smCards: cards, divergingBars: bars };
  }, [viewMode, data.historical_skill_growth, data.historical_skill_forecast, data.skill_yoy, data.skill_trends]);

  const totalSo = (data.kpis?.historical_survey_total_respondents || 424980).toLocaleString();

  return (
    <div>
      <div className="slicer-row">
        <div className="slicer-item">
          <label htmlFor="hist-view-mode">Trend Lens & Time Horizon:</label>
          <select id="hist-view-mode" value={viewMode} onChange={(e) => setViewMode(e.target.value)}>
            <option value="history">6-Year Developer History (Stack Overflow 2020–2025 + 2026–2027 Forecast)</option>
            <option value="linkedin">LinkedIn 2023 Posting Waves (Jun–Nov 2023 + 6-Month Forecast)</option>
          </select>
        </div>
        {viewMode === 'history' && (
          <div>
            <span className="field-label">Trajectory Preset Stack:</span>
            <div className="seg-tabs" role="tablist" aria-label="Skill trajectory stacks">
              {stackTabs.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={stackPreset === t.id}
                  className={`seg-tab-btn ${stackPreset === t.id ? 'active' : ''}`}
                  onClick={() => setStackPreset(t.id)}
                >
                  {stackPreset === t.id && (
                    <motion.span layoutId="stackTab" className="seg-tab-pill" transition={{ type: 'spring', stiffness: 380, damping: 30 }} />
                  )}
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {viewMode === 'history' && (
        <EditorialPanel
          title="6-Year Skill Adoption Trajectory (2020–2025) & 2026–2027 Ridge Forecast"
          subtitle={`${totalSo} Stack Overflow Respondents`}
        >
          <div className="chart-box" style={{ height: 370 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={heroChartData} margin={{ top: 14, right: 24, left: 6, bottom: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis dataKey="year" tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
                <YAxis tickFormatter={(v) => `${v}%`} tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
                <Tooltip content={<EditorialTooltip valueFormatter={(v) => `${Number(v).toFixed(2)}%`} />} />
                <Legend />
                {heroSkills.map((sk, idx) => (
                  <Line
                    key={sk}
                    type="monotone"
                    dataKey={sk}
                    stroke={SERIES_COLORS[idx % SERIES_COLORS.length]}
                    strokeWidth={2.8}
                    dot={{ r: 4.5 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>
      )}

      <EditorialPanel
        title={
          viewMode === 'history'
            ? 'Small-Multiple Adoption %: Top 3 5-Year Rising vs. Top 3 Cooling Skills'
            : 'Small-Multiple Demand Share %: Top 3 Rising vs. Top 3 Cooling Skills'
        }
        subtitle={viewMode === 'history' ? 'Observed 2020–2025 + Forecast' : 'Actual 2023 Waves + 6-Mo Forecast'}
      >
        <div className="grid-3" style={{ marginBottom: 0 }}>
          {smCards.map((card, i) => (
            <div key={card.name + i} className="small-mult-box">
              <div className="small-mult-title">
                <span>{card.name}</span>
                <span className="mono" style={{ color: card.rising ? PALETTE.teal : PALETTE.coralDeep }}>
                  {card.tag}
                </span>
              </div>
              <div style={{ width: '100%', height: 188 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={card.rows} margin={{ top: 8, right: 10, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                    <XAxis dataKey="x" tick={{ fill: PALETTE.axisTick, fontSize: 10 }} />
                    <YAxis tickFormatter={(v) => `${v}%`} tick={{ fill: PALETTE.axisTick, fontSize: 10 }} />
                    <Tooltip content={<EditorialTooltip valueFormatter={(v) => `${Number(v).toFixed(2)}%`} />} />
                    <Line type="monotone" dataKey="hist" name="Observed %" stroke={card.color} strokeWidth={2.6} dot={{ r: 3.5 }} />
                    <Line
                      type="monotone"
                      dataKey="fcst"
                      name="Ridge Forecast %"
                      stroke={PALETTE.blue}
                      strokeWidth={2}
                      strokeDasharray="4 4"
                      dot={{ r: 3 }}
                      connectNulls
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          ))}
        </div>
      </EditorialPanel>

      <EditorialPanel
        title={
          viewMode === 'history'
            ? '5-Year Developer Adoption Shift (2020 -> 2025, Percentage Points)'
            : 'Normalized Share Shift: Wave 2 (Oct–Nov 2023) vs. Wave 1 (Jun–Sep 2023)'
        }
        subtitle={viewMode === 'history' ? 'Skills with >= 1.0% 2020 Baseline' : 'Skills with >= 20 Postings'}
      >
        <div className="chart-box" style={{ height: 450 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={divergingBars} layout="vertical" margin={{ top: 10, right: 24, left: 12, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
              <XAxis
                type="number"
                tickFormatter={(v) => (viewMode === 'history' ? `${v} pp` : `${v}%`)}
                tick={{ fill: PALETTE.axisTick, fontSize: 12 }}
              />
              <YAxis type="category" dataKey="name" width={186} tick={{ fill: PALETTE.axisTick, fontSize: 11.5 }} />
              <Tooltip
                content={
                  <EditorialTooltip
                    valueFormatter={(v) =>
                      `${v >= 0 ? '+' : ''}${Number(v).toFixed(2)} ${viewMode === 'history' ? 'pp' : '%'}`
                    }
                  />
                }
              />
              <Bar dataKey="val" name={viewMode === 'history' ? 'Delta (pp)' : 'Share Shift %'} radius={[4, 4, 4, 4]}>
                {divergingBars.map((b, idx) => (
                  <Cell key={idx} fill={b.val >= 0 ? PALETTE.blue : PALETTE.coral} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </EditorialPanel>
    </div>
  );
}

export function RelationshipsPage({ data }) {
  const k = data.kpis || {};
  const mat = data.cooccurrence_matrix || { skills: [], z: [] };
  const influencers = useMemo(
    () => [...(data.key_influencers || [])].slice(0, 15).reverse(),
    [data.key_influencers]
  );
  const topPairs = useMemo(
    () =>
      [...(data.cooccurrence || [])]
        .slice(0, 15)
        .reverse()
        .map((p) => ({
          pair: `${p.skill_name_a} + ${p.skill_name_b}`,
          count: p.co_posting_count,
        })),
    [data.cooccurrence]
  );

  return (
    <div>
      <div className="grid-2">
        <EditorialPanel title="2D Skill Co-Occurrence Matrix" subtitle="Top 14 Technical Skills">
          <EditorialHeatmap
            rowLabels={mat.skills || []}
            colLabels={mat.skills || []}
            values={mat.z || []}
            warm={false}
            formatVal={(v) => (v === 0 ? '—' : Number(v).toLocaleString())}
          />
        </EditorialPanel>

        <EditorialPanel
          title="Salary Key Influencers"
          subtitle={
            k.rf_salary_cv_r2 !== undefined
              ? `5-Fold CV R² = ${k.rf_salary_cv_r2} • MAE = $${Math.round(k.rf_salary_cv_mae_usd || 0).toLocaleString()}`
              : '5-Fold CV Random Forest'
          }
        >
          <div className="chart-box" style={{ height: 460 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={influencers} layout="vertical" margin={{ top: 10, right: 24, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
                <YAxis type="category" dataKey="factor_name" width={192} tick={{ fill: PALETTE.axisTick, fontSize: 11.5 }} />
                <Tooltip
                  content={
                    <EditorialTooltip
                      valueFormatter={(v) => `${Number(v).toFixed(2)}% importance`}
                    />
                  }
                />
                <Bar dataKey="importance_pct" name="Importance %" fill={PALETTE.coral} radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>
      </div>

      <EditorialPanel title="Top 15 Co-Occurring Skill Pairs in Job Postings" subtitle="Employer Co-Request Frequency">
        <div className="chart-box" style={{ height: 370 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={topPairs} layout="vertical" margin={{ top: 8, right: 24, left: 12, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
              <XAxis type="number" tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
              <YAxis type="category" dataKey="pair" width={226} tick={{ fill: PALETTE.axisTick, fontSize: 11.5 }} />
              <Tooltip content={<EditorialTooltip valueFormatter={(v) => `${Number(v).toLocaleString()} postings`} />} />
              <Bar dataKey="count" name="Co-Postings" fill={PALETTE.blue} radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </EditorialPanel>
    </div>
  );
}

export function SalaryInsightsPage({ data }) {
  const [roleFilter, setRoleFilter] = useState('All AI & Tech Roles');
  const [splitMode, setSplitMode] = useState('work_mode');

  const hSal = data.historical_salary_trends || [];
  const roleOptions = useMemo(() => {
    const names = new Set(hSal.filter((r) => r.segment_type === 'role').map((r) => r.segment_value));
    return ['All AI & Tech Roles', ...Array.from(names).sort()];
  }, [hSal]);

  const series = useMemo(() => {
    return (
      roleFilter === 'All AI & Tech Roles'
        ? hSal.filter((r) => r.segment_type === 'overall')
        : hSal.filter((r) => r.segment_type === 'role' && r.segment_value === roleFilter)
    )
      .map((r) => ({
        year: r.year_num,
        median: Math.round(r.median_salary_usd),
        p25: Math.round(r.p25_salary_usd),
        p75: Math.round(r.p75_salary_usd),
        count: r.record_count,
      }))
      .sort((a, b) => a.year - b.year);
  }, [hSal, roleFilter]);

  const totalHistRecs = useMemo(() => series.reduce((a, b) => a + (b.count || 0), 0), [series]);

  const splitChart = useMemo(() => {
    const segOrder =
      splitMode === 'seniority'
        ? ['Entry Level / Junior', 'Mid-Senior Level', 'Director / Lead', 'Executive']
        : ['Remote', 'Hybrid', 'On-Site'];
    const years = [2020, 2021, 2022, 2023, 2024, 2025];
    const rows = years.map((yr) => {
      const obj = { year: yr };
      segOrder.forEach((seg) => {
        const hit = hSal.find((r) => r.segment_type === splitMode && r.segment_value === seg && r.year_num === yr);
        if (hit) obj[seg] = Math.round(hit.median_salary_usd);
      });
      return obj;
    });
    return { rows, segOrder };
  }, [hSal, splitMode]);

  const topPayingSkills = useMemo(
    () =>
      (data.skills || [])
        .filter((s) => s.market_median_salary_usd && s.market_posting_count >= 15)
        .sort((a, b) => b.market_median_salary_usd - a.market_median_salary_usd)
        .slice(0, 18)
        .map((s) => ({ name: s.skill_name, sal: Math.round(s.market_median_salary_usd) }))
        .reverse(),
    [data.skills]
  );

  const matrix = useMemo(() => {
    const rs = data.role_seniority_salary || [];
    const roles = [...new Set(rs.map((r) => r.role_title_norm))].slice(0, 14);
    const levels = ['Entry Level / Junior', 'Associate', 'Mid-Senior Level', 'Director / Lead'];
    const z = roles.map((rName) =>
      levels.map((lName) => {
        const hit = rs.find((x) => x.role_title_norm === rName && x.level_name === lName);
        return hit ? Math.round(hit.salary_annual_usd) : null;
      })
    );
    return { roles, levels, z };
  }, [data.role_seniority_salary]);

  const roleDist = useMemo(() => [...(data.role_salary_distributions || [])].reverse(), [data.role_salary_distributions]);
  const countryDist = useMemo(() => [...(data.country_salary_distributions || [])].reverse(), [data.country_salary_distributions]);

  return (
    <div>
      <div className="slicer-row">
        <div className="slicer-item">
          <label htmlFor="sal-hist-role-filter">6-Year Salary Role Filter (2020–2025):</label>
          <select id="sal-hist-role-filter" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            {roleOptions.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
        <div className="slicer-item">
          <label htmlFor="sal-hist-split-mode">Breakdown Dimension (2020–2025):</label>
          <select id="sal-hist-split-mode" value={splitMode} onChange={(e) => setSplitMode(e.target.value)}>
            <option value="work_mode">Work Mode (Remote vs. Hybrid vs. On-Site)</option>
            <option value="seniority">Experience / Seniority Tier</option>
          </select>
        </div>
      </div>

      <div className="grid-2">
        <EditorialPanel
          title="6-Year Global Tech Salary Evolution (2020–2025)"
          subtitle={`${roleFilter} • ${totalHistRecs.toLocaleString()} Records`}
        >
          <div className="chart-box" style={{ height: 370 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={series} margin={{ top: 14, right: 20, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis dataKey="year" tick={{ fill: PALETTE.axisTick, fontSize: 11 }} />
                <YAxis yAxisId="left" tickFormatter={(v) => `$${Math.round(v / 1000)}k`} tick={{ fill: PALETTE.axisTick, fontSize: 11 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fill: PALETTE.blueMid, fontSize: 11 }} />
                <Tooltip
                  content={
                    <EditorialTooltip
                      valueFormatter={(v, name) =>
                        String(name).includes('Records') ? Number(v).toLocaleString() : `$${Number(v).toLocaleString()}`
                      }
                    />
                  }
                />
                <Legend />
                <Bar yAxisId="right" dataKey="count" name="Records Reported" fill="rgba(169, 223, 191, 0.20)" radius={[5, 5, 0, 0]} />
                <Line yAxisId="left" type="monotone" dataKey="p75" name="75th Pct ($)" stroke={PALETTE.teal} strokeWidth={2} strokeDasharray="4 4" />
                <Line yAxisId="left" type="monotone" dataKey="median" name="Median ($)" stroke={PALETTE.coral} strokeWidth={3.2} dot={{ r: 5, fill: PALETTE.coralDeep }} />
                <Line yAxisId="left" type="monotone" dataKey="p25" name="25th Pct ($)" stroke={PALETTE.blueMid} strokeWidth={2} strokeDasharray="4 4" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>

        <EditorialPanel
          title={
            splitMode === 'work_mode'
              ? 'Remote vs. Hybrid vs. On-Site Compensation (2020–2025)'
              : 'Salary Progression by Seniority Tier (2020–2025)'
          }
          subtitle="ai-jobs.net Median Annual USD"
        >
          <div className="chart-box" style={{ height: 370 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={splitChart.rows} margin={{ top: 14, right: 20, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis dataKey="year" tick={{ fill: PALETTE.axisTick, fontSize: 11 }} />
                <YAxis tickFormatter={(v) => `$${Math.round(v / 1000)}k`} tick={{ fill: PALETTE.axisTick, fontSize: 11 }} />
                <Tooltip content={<EditorialTooltip valueFormatter={(v) => `$${Number(v).toLocaleString()}`} />} />
                <Legend />
                {splitChart.segOrder.map((seg, i) => (
                  <Line
                    key={seg}
                    type="monotone"
                    dataKey={seg}
                    stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                    strokeWidth={2.8}
                    dot={{ r: 4.5 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>
      </div>

      <div className="grid-2">
        <EditorialPanel title="Top Paying ESCO Skills" subtitle="LinkedIn Disclosed Median USD (>=15 postings)">
          <div className="chart-box" style={{ height: 430 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topPayingSkills} layout="vertical" margin={{ top: 8, right: 24, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis type="number" tickFormatter={(v) => `$${Math.round(v / 1000)}k`} tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
                <YAxis type="category" dataKey="name" width={182} tick={{ fill: PALETTE.axisTick, fontSize: 11.5 }} />
                <Tooltip content={<EditorialTooltip valueFormatter={(v) => `$${Number(v).toLocaleString()}`} />} />
                <Bar dataKey="sal" name="Median Salary USD" fill={PALETTE.coral} radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>

        <EditorialPanel title="Median Salary Heatmap by Role & Seniority" subtitle="Disclosed USD Compensation">
          <EditorialHeatmap
            rowLabels={matrix.roles}
            colLabels={['Entry', 'Associate', 'Mid-Sr', 'Director']}
            values={matrix.z}
            warm={true}
            formatVal={(v) => `$${Math.round(v / 1000)}k`}
          />
        </EditorialPanel>
      </div>

      <div className="grid-2">
        <EditorialPanel title="Role Salary Percentiles (25th / Median / 75th)" subtitle="LinkedIn Market">
          <div className="chart-box" style={{ height: 420 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={roleDist} layout="vertical" margin={{ top: 8, right: 20, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis type="number" tickFormatter={(v) => `$${Math.round(v / 1000)}k`} tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
                <YAxis type="category" dataKey="role_name" width={186} tick={{ fill: PALETTE.axisTick, fontSize: 11.5 }} />
                <Tooltip content={<EditorialTooltip valueFormatter={(v) => `$${Number(v).toLocaleString()}`} />} />
                <Legend />
                <Bar dataKey="q25" name="25th Pct" fill="#6F7FB2" />
                <Bar dataKey="median" name="Median" fill={PALETTE.blue} />
                <Bar dataKey="q75" name="75th Pct" fill={PALETTE.coral} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>

        <EditorialPanel title="Global Developer Compensation by Country" subtitle="Stack Overflow 2024 (65.4k Cohort)">
          <div className="chart-box" style={{ height: 420 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={countryDist} layout="vertical" margin={{ top: 8, right: 20, left: 10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis type="number" tickFormatter={(v) => `$${Math.round(v / 1000)}k`} tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
                <YAxis type="category" dataKey="country_name" width={132} tick={{ fill: PALETTE.axisTick, fontSize: 11.5 }} />
                <Tooltip content={<EditorialTooltip valueFormatter={(v) => `$${Number(v).toLocaleString()}`} />} />
                <Legend />
                <Bar dataKey="q25" name="25th Pct" fill="#6F7FB2" />
                <Bar dataKey="median" name="Median USD" fill={PALETTE.blue} />
                <Bar dataKey="q75" name="75th Pct" fill={PALETTE.coral} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>
      </div>
    </div>
  );
}

export function SurveyMarketPage({ data }) {
  const topSvm = useMemo(
    () =>
      (data.skills || [])
        .filter((s) => s.survey_usage_pct > 0 || s.market_demand_pct > 1.0)
        .slice(0, 18)
        .reverse(),
    [data.skills]
  );

  const quadrantData = useMemo(
    () =>
      (data.skills || [])
        .filter((s) => s.market_demand_pct > 0.8 || s.survey_usage_pct > 1.5)
        .map((s) => ({
          name: s.skill_name,
          supply: Number(s.survey_usage_pct || 0),
          demand: Number(s.market_demand_pct || 0),
        })),
    [data.skills]
  );

  return (
    <div className="grid-2">
      <EditorialPanel title="Stack Overflow Usage % vs. LinkedIn Demand %" subtitle="Top 18 Tech Skills">
        <div className="chart-box" style={{ height: 470 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={topSvm} layout="vertical" margin={{ top: 8, right: 20, left: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
              <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
              <YAxis type="category" dataKey="skill_name" width={172} tick={{ fill: PALETTE.axisTick, fontSize: 11.5 }} />
              <Tooltip content={<EditorialTooltip valueFormatter={(v) => `${Number(v).toFixed(2)}%`} />} />
              <Legend />
              <Bar dataKey="market_demand_pct" name="LinkedIn Employer Request %" fill={PALETTE.coral} />
              <Bar dataKey="survey_usage_pct" name="Stack Overflow 2024 Usage %" fill={PALETTE.blue} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </EditorialPanel>

      <EditorialPanel title="Developer Supply % vs. Employer Demand % Quadrant" subtitle="Supply-Demand Positioning">
        <div className="chart-box" style={{ height: 470 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 16, right: 24, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
              <XAxis
                type="number"
                dataKey="supply"
                name="SO Supply %"
                tickFormatter={(v) => `${v}%`}
                tick={{ fill: PALETTE.axisTick, fontSize: 11 }}
              />
              <YAxis
                type="number"
                dataKey="demand"
                name="LinkedIn Demand %"
                tickFormatter={(v) => `${v}%`}
                tick={{ fill: PALETTE.axisTick, fontSize: 11 }}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload;
                  return (
                    <div style={{ background: '#0D112C', color: '#E3F2E5', border: '1px solid #DFB459', borderRadius: 10, padding: '8px 11px', fontSize: '0.78rem' }}>
                      <div style={{ fontWeight: 700, color: '#F6E2A8' }}>{p.name}</div>
                      <div>Supply: <b>{p.supply.toFixed(2)}%</b> • Demand: <b>{p.demand.toFixed(2)}%</b></div>
                    </div>
                  );
                }}
              />
              <Scatter data={quadrantData} fill={PALETTE.coral} stroke={PALETTE.blue} strokeWidth={1.2} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </EditorialPanel>
    </div>
  );
}

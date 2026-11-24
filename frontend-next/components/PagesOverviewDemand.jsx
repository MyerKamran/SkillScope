'use client';

import React, { useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  BarChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ScatterChart,
  Scatter,
  ZAxis,
  Cell,
  Treemap,
} from 'recharts';
import { Briefcase, DollarSign, Layers, Globe2, AlertTriangle } from 'lucide-react';
import { KpiCard, EditorialPanel, EditorialTooltip, PALETTE } from './MotionPrimitives';

export function MarketOverviewPage({ data, motionPaused }) {
  const k = data.kpis || {};
  const mp = (data.monthly_postings || []).map((r) => ({
    ...r,
    median_salary_clean: Math.round(r.median_salary || k.median_annual_salary_usd || 83200),
  }));

  const geoScatter = useMemo(() => {
    return (data.map_locations || [])
      .filter((l) => l.city !== 'Remote / National')
      .map((l) => ({
        ...l,
        lon: Number(l.longitude),
        lat: Number(l.latitude),
        sal: Math.round(l.median_salary || 85000),
      }));
  }, [data.map_locations]);

  const topCities = useMemo(() => {
    return geoScatter
      .slice(0, 15)
      .map((c) => ({
        label: `${c.city}, ${c.region}`,
        postings: c.postings,
        sal: c.sal,
      }))
      .reverse();
  }, [geoScatter]);

  const topRoles = useMemo(() => {
    return (data.roles || [])
      .filter((r) => r.role_key !== 17)
      .slice(0, 15)
      .map((r) => ({
        name: r.role_title_norm,
        postings: r.postings,
      }))
      .reverse();
  }, [data.roles]);

  return (
    <div>
      <div className="kpi-grid">
        <KpiCard
          index={0}
          icon={Briefcase}
          label="Deduplicated Postings"
          value={k.total_postings || 0}
          sub={k.date_range || '2023 Window'}
          motionPaused={motionPaused}
        />
        <KpiCard
          index={1}
          icon={DollarSign}
          label="Median Annual Salary"
          value={Math.round(k.median_annual_salary_usd || 0)}
          prefix="$"
          sub={`${(k.salary_coverage_pct || 40.1).toFixed(1)}% Disclosed (NULL Kept)`}
          motionPaused={motionPaused}
        />
        <KpiCard
          index={2}
          icon={Layers}
          label="ESCO-Aligned Skills"
          value={k.distinct_skills_in_demand || 86}
          sub={`Top Tech: ${k.top_skill_name || 'SQL'} (${(k.top_skill_share_pct || 0).toFixed(1)}%)`}
          motionPaused={motionPaused}
        />
        <KpiCard
          index={3}
          icon={Globe2}
          label="Remote Share"
          value={k.remote_share_pct || 0}
          suffix="%"
          decimals={1}
          sub="Remote-Allowed Postings"
          motionPaused={motionPaused}
        />
        <KpiCard
          index={4}
          icon={AlertTriangle}
          label="Entry-Level Paradox"
          value={k.entry_level_3plus_years_paradox_pct || 0}
          suffix="%"
          decimals={1}
          sub={`${(k.entry_level_3plus_years_paradox_count || 0).toLocaleString()} / ${(k.entry_level_total_count || 0).toLocaleString()} Entry Jobs`}
          motionPaused={motionPaused}
        />
      </div>

      <div className="grid-2">
        <EditorialPanel title="Posting Volume & Median Salary by Month" subtitle={k.date_range || 'Authentic 2023 Window'}>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={mp} margin={{ top: 16, right: 20, left: 10, bottom: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis dataKey="year_month" tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
                <YAxis yAxisId="left" tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tickFormatter={(v) => `$${Math.round(v / 1000)}k`}
                  tick={{ fill: PALETTE.coralDeep, fontSize: 12 }}
                />
                <Tooltip
                  content={
                    <EditorialTooltip
                      valueFormatter={(v, name) =>
                        String(name).includes('Salary') ? `$${Number(v).toLocaleString()}` : Number(v).toLocaleString()
                      }
                    />
                  }
                />
                <Legend />
                <Bar yAxisId="left" dataKey="postings" name="Monthly Postings" fill={PALETTE.blue} radius={[6, 6, 0, 0]} />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="median_salary_clean"
                  name="Median Salary ($USD)"
                  stroke={PALETTE.coral}
                  strokeWidth={3}
                  dot={{ r: 5, fill: PALETTE.coralDeep }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>

        <EditorialPanel title="GeoNames Spatial Distribution Map" subtitle="90.8% Matched • R-Tree Index">
          <div className="chart-box">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 16, right: 20, left: 6, bottom: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis
                  type="number"
                  dataKey="lon"
                  name="Longitude"
                  domain={[-130, 145]}
                  tick={{ fill: PALETTE.axisTick, fontSize: 11 }}
                />
                <YAxis
                  type="number"
                  dataKey="lat"
                  name="Latitude"
                  domain={[-40, 65]}
                  tick={{ fill: PALETTE.axisTick, fontSize: 11 }}
                />
                <ZAxis type="number" dataKey="postings" range={[55, 520]} name="Postings" />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3', stroke: PALETTE.coral }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const p = payload[0].payload;
                    return (
                      <div style={{ background: '#0D112C', color: '#E3F2E5', border: '1px solid #DFB459', borderRadius: 10, padding: '8px 11px', fontSize: '0.76rem' }}>
                        <div style={{ fontWeight: 700, color: '#F6E2A8' }}>{p.city}, {p.region} ({p.country_name})</div>
                        <div>Postings: <b>{p.postings.toLocaleString()}</b> • Median: <b>${p.sal.toLocaleString()}</b></div>
                        <div className="mono" style={{ opacity: 0.85 }}>({p.lat.toFixed(2)}, {p.lon.toFixed(2)})</div>
                      </div>
                    );
                  }}
                />
                <Scatter data={geoScatter} name="Hiring Hubs">
                  {geoScatter.map((entry, idx) => (
                    <Cell
                      key={idx}
                      fill={entry.sal >= 100000 ? PALETTE.coral : entry.sal >= 80000 ? PALETTE.blueMid : PALETTE.teal}
                      fillOpacity={0.82}
                      stroke={PALETTE.blue}
                      strokeWidth={1}
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>
      </div>

      <div className="grid-2">
        <EditorialPanel title="Top 15 Hiring Cities & Median Salary" subtitle="GeoNames Verified Locations">
          <div className="chart-box" style={{ height: 390 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topCities} layout="vertical" margin={{ top: 8, right: 24, left: 10, bottom: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis type="number" tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
                <YAxis type="category" dataKey="label" width={150} tick={{ fill: PALETTE.axisTick, fontSize: 11.5 }} />
                <Tooltip
                  content={
                    <EditorialTooltip
                      valueFormatter={(v) => `${Number(v).toLocaleString()} postings`}
                    />
                  }
                />
                <Bar dataKey="postings" name="Postings" fill={PALETTE.blueMid} radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>

        <EditorialPanel title="Top Career Roles Classified" subtitle="29 Career Tracks">
          <div className="chart-box" style={{ height: 390 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topRoles} layout="vertical" margin={{ top: 8, right: 24, left: 10, bottom: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis type="number" tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
                <YAxis type="category" dataKey="name" width={182} tick={{ fill: PALETTE.axisTick, fontSize: 11.5 }} />
                <Tooltip content={<EditorialTooltip valueFormatter={(v) => `${Number(v).toLocaleString()} postings`} />} />
                <Bar dataKey="postings" name="Classified Postings" fill={PALETTE.coral} radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>
      </div>
    </div>
  );
}

const TREEMAP_SHADES = [
  '#22205A',
  '#2B2A6E',
  '#1D424F',
  '#1E524A',
  '#296154',
  '#5E481E',
  '#755923',
  '#36337A',
];

function EditorialTreemapCell(props) {
  const { depth, x, y, width, height, index, name, value } = props;
  if (depth === 0 || width <= 3 || height <= 3) return null;

  if (depth === 1) {
    return (
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill="none"
        stroke="rgba(172, 225, 175, 0.24)"
        strokeWidth={1.5}
        rx={4}
      />
    );
  }

  const fill = TREEMAP_SHADES[index % TREEMAP_SHADES.length];
  const fontSize = width > 110 ? 13 : 11.5;
  const maxChars = Math.max(4, Math.floor((width - 14) / (fontSize * 0.58)));
  const labelText =
    name && name.length > maxChars ? `${name.slice(0, maxChars - 1)}…` : name;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={fill}
        stroke="#12113a"
        strokeWidth={2}
        rx={5}
      />
      {width > 44 && height > 22 && (
        <text
          x={x + 8}
          y={y + 20}
          fill="#F4FBF5"
          stroke="none"
          strokeWidth={0}
          fontFamily="var(--font-sans), Inter, system-ui, sans-serif"
          fontSize={fontSize}
          fontWeight={600}
        >
          {labelText}
        </text>
      )}
      {width > 44 && height > 40 && value > 0 && (
        <text
          x={x + 8}
          y={y + 37}
          fill="#F7E3A8"
          stroke="none"
          strokeWidth={0}
          fontFamily="var(--font-mono), monospace"
          fontSize={11}
          fontWeight={500}
        >
          {Number(value).toLocaleString()}
        </text>
      )}
    </g>
  );
}

export function SkillDemandPage({ data }) {
  const [roleKey, setRoleKey] = useState(0);
  const [catFilter, setCatFilter] = useState('ALL');

  const namedRoles = useMemo(
    () => [...(data.roles || [])].filter((r) => r.role_key !== 17).sort((a, b) => a.role_key - b.role_key),
    [data.roles]
  );

  const skillRows = useMemo(() => {
    let rows = [];
    if (roleKey === 0) {
      rows = (data.skills || []).map((s) => ({
        name: s.skill_name,
        pct: Number(s.market_demand_pct || 0),
        count: Number(s.market_posting_count || 0),
        cat: s.category_name || 'General',
      }));
    } else {
      rows = (data.role_profiles || [])
        .filter((p) => p.role_key === roleKey)
        .map((p) => {
          const skMeta = (data.skills || []).find((s) => s.skill_key === p.skill_key) || {};
          return {
            name: p.skill_name,
            pct: Number(p.demand_pct || 0),
            count: Number(p.posting_count || 0),
            cat: skMeta.category_name || 'General',
          };
        });
    }
    if (catFilter !== 'ALL') {
      rows = rows.filter((r) => r.cat === catFilter);
    }
    return rows.sort((a, b) => b.pct - a.pct);
  }, [data.skills, data.role_profiles, roleKey, catFilter]);

  const top20 = useMemo(() => skillRows.slice(0, 20).reverse(), [skillRows]);

  const treemapData = useMemo(() => {
    const groups = {};
    skillRows
      .filter((s) => s.count > 0)
      .forEach((s) => {
        if (!groups[s.cat]) groups[s.cat] = [];
        groups[s.cat].push({ name: s.name, size: s.count });
      });
    return Object.entries(groups).map(([cat, children]) => ({
      name: cat,
      children,
    }));
  }, [skillRows]);

  return (
    <div>
      <div className="slicer-row">
        <div className="slicer-item">
          <label htmlFor="demand-role-slicer">Filter by Target Role (28 Named Roles):</label>
          <select
            id="demand-role-slicer"
            value={roleKey}
            onChange={(e) => setRoleKey(parseInt(e.target.value, 10))}
          >
            <option value={0}>All Classified Career Roles</option>
            {namedRoles.map((r) => (
              <option key={r.role_key} value={r.role_key}>
                {r.role_title_norm} ({r.postings.toLocaleString()})
              </option>
            ))}
          </select>
        </div>
        <div className="slicer-item">
          <label htmlFor="demand-cat-slicer">Filter by ESCO Skill Category (21 Categories):</label>
          <select
            id="demand-cat-slicer"
            value={catFilter}
            onChange={(e) => setCatFilter(e.target.value)}
          >
            <option value="ALL">All 21 ESCO Skill Categories</option>
            {(data.categories || []).map((c) => (
              <option key={c.category_key} value={c.category_name}>
                {c.category_name} ({c.parent_category})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid-2">
        <EditorialPanel title="Top 20 Most Demanded Skills" subtitle="Employer Request Share %">
          <div className="chart-box" style={{ height: 470 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={top20} layout="vertical" margin={{ top: 8, right: 24, left: 10, bottom: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={PALETTE.gridStroke} />
                <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fill: PALETTE.axisTick, fontSize: 12 }} />
                <YAxis type="category" dataKey="name" width={172} tick={{ fill: PALETTE.axisTick, fontSize: 11.5 }} />
                <Tooltip
                  content={
                    <EditorialTooltip
                      valueFormatter={(v) => `${Number(v).toFixed(1)}%`}
                    />
                  }
                />
                <Bar dataKey="pct" name="Share %" fill={PALETTE.blue} radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>

        <EditorialPanel title="Hierarchical ESCO Category Treemap" subtitle="Proportional Posting Volume">
          <div className="chart-box" style={{ height: 470 }}>
            <ResponsiveContainer width="100%" height="100%">
              <Treemap
                data={treemapData}
                dataKey="size"
                stroke="none"
                content={<EditorialTreemapCell />}
              >
                <Tooltip content={<EditorialTooltip valueFormatter={(v) => `${Number(v).toLocaleString()} postings`} />} />
              </Treemap>
            </ResponsiveContainer>
          </div>
        </EditorialPanel>
      </div>
    </div>
  );
}

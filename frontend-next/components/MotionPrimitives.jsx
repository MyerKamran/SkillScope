'use client';

import React, { useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

export const PALETTE = {
  bg: '#12113a',
  bgWarm: '#1c1a4a',
  panel: '#1a1846',
  border: 'rgba(172, 225, 175, 0.16)',
  blue: '#ace1af',
  blueMid: '#87ceaa',
  coral: '#e2b44a',
  coralDeep: '#f6e2a8',
  teal: '#67d5c4',
  ochre: '#e8b062',
  plum: '#a7aef7',
  slate: '#a6beb4',
  gridStroke: 'rgba(172, 225, 175, 0.12)',
  axisTick: '#D5E8DA',
};

export const SERIES_COLORS = [
  '#ace1af', // Celadon primary
  '#e2b44a', // Gold secondary
  '#67d5c4', // Seafoam Celadon
  '#f6e2a8', // Pale Gold Highlight
  '#a7aef7', // Periwinkle Indigo Accent
  '#e8b062', // Warm Amber Gold
];

export function AnimatedCounter({ value, prefix = '', suffix = '', decimals = 0, motionPaused = false }) {
  const prefersReduced = useReducedMotion();
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const target = Number(value || 0);
    if (prefersReduced || motionPaused) {
      setDisplay(target);
      return;
    }
    let rafId = null;
    const duration = 680;
    const startTime = performance.now();

    const step = (now) => {
      const t = Math.min(1, (now - startTime) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(target * eased);
      if (t < 1) {
        rafId = requestAnimationFrame(step);
      }
    };
    rafId = requestAnimationFrame(step);
    return () => {
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [value, prefersReduced, motionPaused]);

  const formatted = display.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return (
    <>
      {prefix}
      {formatted}
      {suffix}
    </>
  );
}

function handlePointerGlow(e) {
  const rect = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty('--mx', `${e.clientX - rect.left}px`);
  e.currentTarget.style.setProperty('--my', `${e.clientY - rect.top}px`);
}

export function KpiCard({ label, value, prefix = '', suffix = '', decimals = 0, sub, index = 0, icon: Icon = null, motionPaused = false }) {
  return (
    <motion.div
      className="kpi-card"
      onPointerMove={handlePointerGlow}
      initial={{ opacity: 0, y: 14, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.48, delay: Math.min(0.28, index * 0.055), ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -4, transition: { type: 'spring', stiffness: 260, damping: 24 } }}
    >
      <div className="kpi-label">
        <span>{label}</span>
        {Icon && <Icon size={14} style={{ color: PALETTE.coral }} aria-hidden="true" />}
      </div>
      <div className="kpi-val">
        {typeof value === 'number' ? (
          <AnimatedCounter
            value={value}
            prefix={prefix}
            suffix={suffix}
            decimals={decimals}
            motionPaused={motionPaused}
          />
        ) : (
          value
        )}
      </div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </motion.div>
  );
}

export function EditorialPanel({ title, subtitle, children, className = '', style = {}, rightSlot = null }) {
  return (
    <motion.div
      className={`panel ${className}`}
      style={style}
      onPointerMove={handlePointerGlow}
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.06 }}
      transition={{ duration: 0.44, ease: [0.22, 1, 0.36, 1] }}
    >
      {title && (
        <h3>
          <span>{title}</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
            {subtitle && <span className="panel-sub">{subtitle}</span>}
            {rightSlot}
          </span>
        </h3>
      )}
      {children}
    </motion.div>
  );
}

export function EditorialTooltip({ active, payload, label, valueFormatter }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div
      style={{
        background: '#12113a',
        color: '#e3f2e5',
        border: '1px solid #e2b44a',
        borderRadius: 12,
        padding: '10px 13px',
        fontSize: '0.78rem',
        boxShadow: '0 14px 32px -8px rgba(4, 6, 20, 0.72)',
      }}
    >
      {label !== undefined && label !== null && (
        <div style={{ fontWeight: 600, marginBottom: 4, color: '#f6e2a8' }}>{String(label)}</div>
      )}
      {payload.map((entry, i) => {
        const val = valueFormatter ? valueFormatter(entry.value, entry.name) : entry.value;
        return (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 14, lineHeight: 1.55 }}>
            <span style={{ color: '#a6beb4' }}>{entry.name}:</span>
            <span className="mono" style={{ fontWeight: 600, color: '#e3f2e5' }}>
              {val}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function EditorialHeatmap({ rowLabels, colLabels, values, warm = false, formatVal = (v) => v }) {
  const [hovered, setHovered] = useState(null);
  const flat = values.flat().filter((v) => v !== null && v !== undefined && Number.isFinite(Number(v)));
  const maxV = flat.length ? Math.max(...flat) : 1;
  const minV = flat.length ? Math.min(...flat) : 0;

  const getCellStyle = (val) => {
    if (val === null || val === undefined || !Number.isFinite(Number(val))) {
      return { background: 'rgba(11, 14, 38, 0.65)', color: '#7D928B' };
    }
    const norm = maxV === minV ? 0.5 : (Number(val) - minV) / (maxV - minV);
    if (warm) {
      // Deep Indigo -> Soft Celadon -> Brushed Gold
      if (norm < 0.45) {
        const alpha = 0.14 + norm * 0.65;
        return { background: `rgba(169, 223, 191, ${alpha.toFixed(2)})`, color: '#E3F2E5' };
      }
      const alpha = 0.45 + (norm - 0.45) * 0.95;
      return {
        background: `rgba(223, 180, 89, ${Math.min(0.95, alpha).toFixed(2)})`,
        color: norm > 0.62 ? '#0D112C' : '#E3F2E5',
      };
    }
    const alpha = 0.12 + norm * 0.8;
    return {
      background: `rgba(169, 223, 191, ${alpha.toFixed(2)})`,
      color: norm > 0.58 ? '#0D112C' : '#E3F2E5',
    };
  };

  return (
    <div className="heatmap-wrap">
      <div style={{ minHeight: 24, marginBottom: 6, fontSize: '0.77rem', color: PALETTE.blueMid, fontWeight: 600 }}>
        {hovered
          ? `${hovered.r} × ${hovered.c}: ${hovered.v !== null && hovered.v !== undefined ? formatVal(hovered.v) : 'No sample'}`
          : 'Hover any cell to inspect exact values'}
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `165px repeat(${colLabels.length}, minmax(44px, 1fr))`,
          gap: 3,
          alignItems: 'center',
        }}
      >
        <div />
        {colLabels.map((c, ci) => (
          <div
            key={ci}
            style={{
              fontSize: '0.78rem',
              fontWeight: 600,
              color: '#E3F2E5',
              textAlign: 'center',
              padding: '4px 2px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={c}
          >
            {c.length > 13 ? c.slice(0, 12) + '…' : c}
          </div>
        ))}
        {rowLabels.map((r, ri) => (
          <React.Fragment key={ri}>
            <div
              style={{
                fontSize: '0.78rem',
                fontWeight: 600,
                color: '#E3F2E5',
                paddingRight: 10,
                textAlign: 'right',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
              title={r}
            >
              {r}
            </div>
            {colLabels.map((c, ci) => {
              const v = values[ri]?.[ci];
              const cellStyle = getCellStyle(v);
              return (
                <div
                  key={`${ri}-${ci}`}
                  className="heatmap-cell"
                  style={cellStyle}
                  onMouseEnter={() => setHovered({ r, c, v })}
                  onMouseLeave={() => setHovered(null)}
                >
                  {v !== null && v !== undefined ? formatVal(v) : '—'}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

export function AnimatedMatchGauge({ score = 0 }) {
  const clamped = Math.max(0, Math.min(100, Number(score || 0)));
  const radius = 84;
  const arcLen = Math.PI * radius; // semicircle
  const targetOffset = arcLen * (1 - clamped / 100);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '10px 0 4px' }}>
      <svg viewBox="0 0 220 130" style={{ width: '100%', maxWidth: 245, overflow: 'visible' }} aria-label={`Role match score ${clamped.toFixed(1)}%`}>
        <defs>
          <linearGradient id="editorialGaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ace1af" />
            <stop offset="100%" stopColor="#e2b44a" />
          </linearGradient>
        </defs>
        <path
          d="M 26 110 A 84 84 0 0 1 194 110"
          fill="none"
          stroke="rgba(172, 225, 175, 0.16)"
          strokeWidth="16"
          strokeLinecap="round"
        />
        <motion.path
          d="M 26 110 A 84 84 0 0 1 194 110"
          fill="none"
          stroke="url(#editorialGaugeGrad)"
          strokeWidth="16"
          strokeLinecap="round"
          strokeDasharray={arcLen}
          initial={{ strokeDashoffset: arcLen }}
          animate={{ strokeDashoffset: targetOffset }}
          transition={{ duration: 0.85, ease: [0.22, 1, 0.36, 1] }}
        />
        <text
          x="110"
          y="96"
          textAnchor="middle"
          style={{
            fontFamily: 'var(--font-display), Georgia, serif',
            fontSize: '30px',
            fontWeight: 500,
            fill: '#e3f2e5',
          }}
        >
          {clamped.toFixed(1)}%
        </text>
        <text
          x="110"
          y="116"
          textAnchor="middle"
          style={{
            fontFamily: 'var(--font-sans), sans-serif',
            fontSize: '10.5px',
            fontWeight: 600,
            fill: '#e2b44a',
            letterSpacing: '0.1em',
          }}
        >
          ROLE READINESS
        </text>
      </svg>
    </div>
  );
}

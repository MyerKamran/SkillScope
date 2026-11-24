'use client';

import React, { useRef } from 'react';
import { motion, useScroll, useSpring, useTransform, useReducedMotion } from 'framer-motion';

const PILLARS = [
  {
    num: '01',
    title: 'Mamdani Fuzzy Readiness',
    body: 'Evaluates your exact skillset against 29 calibrated roles in real time, ranking missing skills by demand lift and salary premium.',
  },
  {
    num: '02',
    title: 'ESCO Multi-Label NLP',
    body: 'Extracts 86 canonical competencies from unstructured job descriptions with context-aware disambiguation at 96.0% benchmark F1.',
  },
  {
    num: '03',
    title: 'Six-Year Warehouse Horizon',
    body: 'Unifies 32,394 US postings with 424,980 Stack Overflow cohorts and 151,439 global salaries across 5 MySQL data marts.',
  },
];

export function HomeLanding({ data, onNavigate }) {
  const prefersReduced = useReducedMotion();
  const motionOff = Boolean(prefersReduced);

  const heroRef = useRef(null);
  const trippleRef = useRef(null);
  const galleryRef = useRef(null);
  const bannerRef = useRef(null);

  // 1. Hero parallax (translucent image layer glides while live constellation canvas shines behind)
  const { scrollYProgress: heroProgress } = useScroll({
    target: heroRef,
    offset: ['start start', 'end start'],
  });
  const heroBgY = useTransform(heroProgress, [0, 1], [0, 96]);
  const heroCopyY = useTransform(heroProgress, [0, 1], [0, -32]);
  const heroCardY = useTransform(heroProgress, [0, 1], [0, 22]);

  // 2. Three-column counter-scrolling pillars (left/right move up, center moves down)
  const { scrollYProgress: trippleRaw } = useScroll({
    target: trippleRef,
    offset: ['start end', 'end start'],
  });
  const trippleProgress = useSpring(trippleRaw, { stiffness: 110, damping: 24, mass: 0.45 });
  const pillarY0 = useTransform(trippleProgress, [0, 1], [44, -44]);
  const pillarY1 = useTransform(trippleProgress, [0, 1], [-30, 36]);
  const pillarY2 = useTransform(trippleProgress, [0, 1], [54, -34]);
  const pillarMotion = [pillarY0, pillarY1, pillarY2];

  // 3. Staggered 2-column gallery opposing vertical drift (left goes up, right goes down)
  const { scrollYProgress: galleryRaw } = useScroll({
    target: galleryRef,
    offset: ['start end', 'end start'],
  });
  const galleryProgress = useSpring(galleryRaw, { stiffness: 105, damping: 24, mass: 0.45 });
  const leftColY = useTransform(galleryProgress, [0, 1], [42, -46]);
  const rightColY = useTransform(galleryProgress, [0, 1], [-34, 48]);

  // 4. Closing banner parallax
  const { scrollYProgress: bannerRaw } = useScroll({
    target: bannerRef,
    offset: ['start end', 'end start'],
  });
  const bannerBgY = useTransform(bannerRaw, [0, 1], [-28, 32]);

  const kpis = data?.kpis || {};
  const nlp = data?.nlp_eval || {};
  const recon = data?.etl_reconciliation || {};

  const leftGallery = [
    {
      id: 'coach',
      img: '/images/card-coach.png',
      eyebrow: 'Interactive Simulator',
      stat: `${data?.roles?.length || 29} Roles`,
      title: 'Skill-Gap Coach',
      desc: 'Test current skills against any target role and persist live Mamdani recommendations to MySQL.',
    },
    {
      id: 'market',
      img: '/images/card-market.png',
      eyebrow: '2020–2025 Explorer',
      stat: `$${Math.round(kpis.median_annual_salary_usd ?? 83200).toLocaleString()} Median`,
      title: 'Market & Salaries',
      desc: 'Compare 6-year Stack Overflow adoption trajectories, global pay percentiles, and 2026 forecasts.',
    },
  ];

  const rightGallery = [
    {
      id: 'analyzer',
      img: '/images/card-nlp.png',
      eyebrow: 'ESCO v1.1 Taxonomy',
      stat: `${((nlp.f1_score ?? 0.9598) * 100).toFixed(1)}% Audit F1`,
      title: 'JD Analyzer',
      desc: 'Paste raw job text to extract disambiguated technical skills and send them straight into coaching.',
    },
    {
      id: 'warehouse',
      img: '/images/card-warehouse.png',
      eyebrow: 'Medallion Governance',
      stat: `${recon.checks_passed ?? 50}/${recon.checks_total ?? 50} Checks`,
      title: 'Warehouse & Lineage',
      desc: 'Verify Bronze-to-Gold parity, 5 conformed star-schema marts, and live MySQL EXPLAIN ANALYZE timings.',
    },
  ];

  return (
    <div className="ns-home">
      {/* 1. ATMOSPHERIC HERO — TRANSLUCENT LAYER OVER LIVE CONSTELLATION CANVAS */}
      <section className="ns-hero" ref={heroRef}>
        <motion.div
          className="ns-hero-bg-wrap"
          aria-hidden="true"
          style={{ y: motionOff ? 0 : heroBgY }}
        >
          <img src="/images/indigo-hero.png" alt="" className="ns-hero-bg-img" />
          <div className="ns-hero-scrim" />
        </motion.div>

        <div className="ns-inner ns-hero-grid">
          <motion.div style={{ y: motionOff ? 0 : heroCopyY }}>
            <div className="ns-eyebrow">Inside Labour Intelligence · 2020–2025</div>
            <h1 className="ns-hero-title">
              Career intelligence
              <br />
              <span className="ns-gold-accent">that moves with the market.</span>
            </h1>
            <p className="ns-hero-sub">
              An open architectural workspace combining Mamdani fuzzy readiness scoring, ESCO NLP
              extraction, and six years of verified salary &amp; developer survey history.
            </p>
            <div className="ns-cta-row">
              <button
                type="button"
                className="ns-btn-gold"
                onClick={() => onNavigate('coach')}
              >
                <span>Open Skill-Gap Coach</span>
                <span aria-hidden="true">→</span>
              </button>
              <button
                type="button"
                className="ns-btn-celadon-outline"
                onClick={() => onNavigate('analyzer')}
              >
                <span>Analyze a JD</span>
              </button>
            </div>
          </motion.div>

          <motion.aside
            className="ns-hero-feature"
            style={{ y: motionOff ? 0 : heroCardY }}
            aria-label="Live Warehouse Metrics"
          >
            <div className="ns-feature-top">
              <span className="ns-feature-label">Live MySQL 8.0 Corpus</span>
              <span className="badge badge-primary">5 Data Marts</span>
            </div>
            <div className="ns-feature-stats">
              <div>
                <div className="ns-feature-val">
                  {(kpis.total_postings ?? 32394).toLocaleString()}
                </div>
                <div className="ns-feature-desc">Curated Job Postings</div>
              </div>
              <div>
                <div className="ns-feature-val">
                  {(kpis.historical_survey_total_respondents ?? 424980).toLocaleString()}
                </div>
                <div className="ns-feature-desc">Developer Surveys (6 Yrs)</div>
              </div>
              <div>
                <div className="ns-feature-val">
                  {(kpis.historical_salary_total_records ?? 151439).toLocaleString()}
                </div>
                <div className="ns-feature-desc">Global Salary Records</div>
              </div>
              <div>
                <div className="ns-feature-val">
                  {((nlp.precision ?? 0.9848) * 100).toFixed(1)}%
                </div>
                <div className="ns-feature-desc">ESCO NLP Precision</div>
              </div>
            </div>
            <button
              type="button"
              className="ns-feature-link"
              onClick={() => onNavigate('market')}
            >
              <span>Explore 2020–2025 Market Dynamics</span>
              <span aria-hidden="true">→</span>
            </button>
          </motion.aside>
        </div>
      </section>

      {/* 2. COUNTER-SCROLLING 3-COLUMN PILLARS */}
      <section className="ns-tripple-section" ref={trippleRef}>
        <div className="ns-inner">
          <div className="ns-section-header">
            <div>
              <div className="ns-eyebrow">Built Alongside Power BI</div>
              <h2 className="ns-section-title">
                Live inference and NLP, designed cleanly around open space.
              </h2>
            </div>
            <p className="ns-section-note">
              Historical OLAP slicing lives inside our companion Power BI dashboards. This studio
              runs real-time fuzzy logic, text parsing, and write-back.
            </p>
          </div>

          <div className="ns-tripple-grid">
            {PILLARS.map((pillar, idx) => (
              <motion.article
                key={pillar.num}
                className="ns-pillar-card"
                style={{ y: motionOff ? 0 : pillarMotion[idx] }}
              >
                <div className="ns-pillar-num">{pillar.num}</div>
                <div>
                  <h3 className="ns-pillar-title">{pillar.title}</h3>
                  <p className="ns-pillar-body">{pillar.body}</p>
                </div>
              </motion.article>
            ))}
          </div>
        </div>
      </section>

      {/* 3. STAGGERED 2-COLUMN OPPOSING-SCROLL GALLERY */}
      <section className="ns-gallery-section" ref={galleryRef}>
        <div className="ns-inner">
          <div className="ns-section-header">
            <div>
              <div className="ns-eyebrow">Four Open Workspaces</div>
              <h2 className="ns-section-title">Select a capability to explore live data.</h2>
            </div>
            <p className="ns-section-note">
              Each module reads directly from verified Silver &amp; Gold lakehouse layers served on
              demand.
            </p>
          </div>

          <div className="ns-gallery-grid">
            <motion.div
              className="ns-gallery-col"
              style={{ y: motionOff ? 0 : leftColY }}
            >
              {leftGallery.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="ns-project-card"
                  onClick={() => onNavigate(item.id)}
                >
                  <div className="ns-project-media">
                    <img src={item.img} alt={item.title} className="ns-project-img" />
                    <div className="ns-card-circle" aria-hidden="true">
                      →
                    </div>
                  </div>
                  <div className="ns-project-info">
                    <div className="ns-project-meta">
                      <span>{item.eyebrow}</span>
                      <span className="mono">{item.stat}</span>
                    </div>
                    <h3 className="ns-project-title">{item.title}</h3>
                    <p className="ns-project-desc">{item.desc}</p>
                  </div>
                </button>
              ))}
            </motion.div>

            <motion.div
              className="ns-gallery-col offset-right"
              style={{ y: motionOff ? 0 : rightColY }}
            >
              {rightGallery.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="ns-project-card"
                  onClick={() => onNavigate(item.id)}
                >
                  <div className="ns-project-media">
                    <img src={item.img} alt={item.title} className="ns-project-img" />
                    <div className="ns-card-circle" aria-hidden="true">
                      →
                    </div>
                  </div>
                  <div className="ns-project-info">
                    <div className="ns-project-meta">
                      <span>{item.eyebrow}</span>
                      <span className="mono">{item.stat}</span>
                    </div>
                    <h3 className="ns-project-title">{item.title}</h3>
                    <p className="ns-project-desc">{item.desc}</p>
                  </div>
                </button>
              ))}
            </motion.div>
          </div>
        </div>
      </section>

      {/* 4. FULL-BLEED CLOSING BANNER */}
      <section className="ns-banner" ref={bannerRef}>
        <motion.div
          className="ns-banner-media"
          aria-hidden="true"
          style={{ y: motionOff ? 0 : bannerBgY }}
        >
          <img src="/images/indigo-banner.png" alt="" className="ns-banner-img" />
          <div className="ns-banner-scrim" />
        </motion.div>

        <div className="ns-inner ns-banner-inner">
          <div className="ns-eyebrow">Ready When You Are</div>
          <h2 className="ns-banner-title">See where your skills stand today.</h2>
          <p className="ns-banner-sub">
            Benchmark against 32,394 employer requisitions or inspect our star-schema DWBI lineage
            in seconds.
          </p>
          <div className="ns-cta-row center">
            <button
              type="button"
              className="ns-btn-gold"
              onClick={() => onNavigate('coach')}
            >
              <span>Launch Readiness Coach</span>
              <span aria-hidden="true">→</span>
            </button>
            <button
              type="button"
              className="ns-btn-celadon-outline"
              onClick={() => onNavigate('warehouse')}
            >
              <span>Inspect DWBI Schemas</span>
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

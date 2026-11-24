'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';

const LETTERS = 'killscope'.split('');

/**
 * Intro sequence ported from "Skillscope Loading Screen.html":
 * the S glyph draws itself, "killscope" slides open, the gold dot lands on the i,
 * the gold rule extends and the tagline fades in over a radar-sweep constellation.
 * Fades out automatically once the sequence completes (or on "Skip intro").
 */
export function LoadingScreen({ onFinish }) {
  const restRef = useRef(null);
  const canvasRef = useRef(null);
  const doneRef = useRef(false);
  const [playing, setPlaying] = useState(false);
  const [leaving, setLeaving] = useState(false);

  const leave = useCallback(() => {
    if (doneRef.current) return;
    doneRef.current = true;
    setLeaving(true);
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.setTimeout(() => onFinish?.(), reduce ? 200 : 850);
  }, [onFinish]);

  // Start the sequence once fonts are ready, then hold briefly before revealing the site.
  useEffect(() => {
    const html = document.documentElement;
    html.classList.add('is-loading');
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let holdTimer = 0;
    let cancelled = false;

    const start = () => {
      if (cancelled) return;
      const rest = restRef.current;
      if (rest) rest.style.setProperty('--w', `${rest.scrollWidth}px`);
      setPlaying(true);
      holdTimer = window.setTimeout(leave, reduce ? 1400 : 5600);
    };

    const fontsReady = document.fonts?.ready ?? Promise.resolve();
    Promise.race([fontsReady, new Promise((r) => setTimeout(r, 1800))]).then(start);

    return () => {
      cancelled = true;
      window.clearTimeout(holdTimer);
      html.classList.remove('is-loading');
    };
  }, [leave]);

  // Radar-sweep constellation canvas.
  useEffect(() => {
    const c = canvasRef.current;
    const x = c?.getContext('2d');
    if (!c || !x) return undefined;
    const TAU = Math.PI * 2;
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let W = 0;
    let H = 0;
    let P = [];
    let a = 0;
    let last = 0;
    let raf = 0;

    function size() {
      const D = Math.min(window.devicePixelRatio || 1, 2);
      W = window.innerWidth;
      H = window.innerHeight;
      c.width = W * D;
      c.height = H * D;
      x.setTransform(D, 0, 0, D, 0, 0);
      const n = Math.min(90, Math.round((W * H) / 17000));
      P = [];
      for (let i = 0; i < n; i += 1) {
        P.push({
          x: Math.random() * W,
          y: Math.random() * H,
          vx: (Math.random() - 0.5) * 0.22,
          vy: (Math.random() - 0.5) * 0.22,
          r: Math.random() * 1.2 + 0.8,
          g: Math.random() < 0.12,
          l: 0,
        });
      }
    }

    function frame(t) {
      raf = window.requestAnimationFrame(frame);
      try {
        const dt = Math.min(40, t - last || 16);
        last = t;
        if (!still) a = (a + dt * 0.00045) % TAU;
        x.clearRect(0, 0, W, H);
        const cx = W / 2;
        const cy = H * 0.48;
        const R = Math.max(10, Math.min(W, H) * 0.6);
        x.lineWidth = 1;
        x.strokeStyle = 'rgba(172,225,175,.06)';
        for (let i = 1; i <= 4; i += 1) {
          x.beginPath();
          x.arc(cx, cy, Math.max(1, (R * i) / 4), 0, TAU);
          x.stroke();
        }
        if (x.createConicGradient) {
          const g = x.createConicGradient(a - 0.9, cx, cy);
          g.addColorStop(0, 'rgba(172,225,175,0)');
          g.addColorStop(0.1432, 'rgba(172,225,175,.10)');
          g.addColorStop(0.1434, 'rgba(172,225,175,0)');
          g.addColorStop(1, 'rgba(172,225,175,0)');
          x.fillStyle = g;
          x.beginPath();
          x.arc(cx, cy, R, 0, TAU);
          x.fill();
        }
        x.strokeStyle = 'rgba(172,225,175,.2)';
        x.beginPath();
        x.moveTo(cx, cy);
        x.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R);
        x.stroke();

        for (let i = 0; i < P.length; i += 1) {
          const p = P[i];
          if (!still) {
            p.x += (p.vx * dt) / 16;
            p.y += (p.vy * dt) / 16;
          }
          if (p.x < -10) p.x = W + 10;
          else if (p.x > W + 10) p.x = -10;
          if (p.y < -10) p.y = H + 10;
          else if (p.y > H + 10) p.y = -10;
          const d = (a - Math.atan2(p.y - cy, p.x - cx) + TAU * 2) % TAU;
          if (d < 0.06) p.l = 1;
          p.l *= 0.97;
        }
        for (let i = 0; i < P.length; i += 1) {
          const p = P[i];
          for (let j = i + 1; j < P.length; j += 1) {
            const q = P[j];
            const ex = p.x - q.x;
            const ey = p.y - q.y;
            const ed = Math.sqrt(ex * ex + ey * ey);
            if (ed < 130) {
              x.strokeStyle = `rgba(172,225,175,${(1 - ed / 130) * 0.14 + Math.max(p.l, q.l) * 0.12})`;
              x.beginPath();
              x.moveTo(p.x, p.y);
              x.lineTo(q.x, q.y);
              x.stroke();
            }
          }
        }
        for (let i = 0; i < P.length; i += 1) {
          const p = P[i];
          const col = p.g ? '226,180,74' : '172,225,175';
          x.shadowBlur = p.l > 0.05 ? 14 * p.l : 0;
          x.shadowColor = `rgba(${col},.9)`;
          x.fillStyle = `rgba(${col},${0.35 + 0.55 * p.l})`;
          x.beginPath();
          x.arc(p.x, p.y, Math.max(0.5, p.r + p.l * 1.2), 0, TAU);
          x.fill();
        }
        x.shadowBlur = 0;
      } catch {
        // Guard against transient 0-size viewport frames
      }
      if (still) window.cancelAnimationFrame(raf);
    }

    size();
    window.addEventListener('resize', size);
    raf = window.requestAnimationFrame(frame);
    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener('resize', size);
    };
  }, []);

  const className = ['ss-loader', playing ? 'play' : '', leaving ? 'leaving' : '']
    .filter(Boolean)
    .join(' ');

  return (
    <div className={className}>
      <canvas ref={canvasRef} className="ssl-canvas" aria-hidden="true" />
      <div className="ssl-bloom" aria-hidden="true" />
      <div className="ssl-stage" role="status" aria-label="Loading SkillScope">
        <div className="ssl-word" aria-hidden="true">
          <svg className="ssl-s" viewBox="0 0 100 100">
            <path
              className="p1"
              pathLength="1"
              stroke="#ace1af"
              strokeWidth="9"
              d="M86 32V28Q86 14 72 14H30Q14 14 14 30V36Q14 50 30 50H70Q86 50 86 64V70Q86 86 70 86H28Q14 86 14 72V68"
            />
            <path className="p2" pathLength="1" stroke="#ace1af" strokeWidth="5" d="M72 42V38Q72 28 62 28H36Q28 28 28 36" />
            <path className="p2" pathLength="1" stroke="#ace1af" strokeWidth="5" d="M28 58V62Q28 72 38 72H64Q72 72 72 64" />
          </svg>
          <div className="ssl-rest" ref={restRef}>
            {LETTERS.map((ch, i) => (
              <span key={i} className={ch === 'i' ? 'ssl-i' : undefined} style={{ '--i': i }}>
                {ch === 'i' ? 'ı' : ch}
              </span>
            ))}
          </div>
        </div>
        <div className="ssl-line" aria-hidden="true" />
        <div className="ssl-tag">See your skills clearly</div>
      </div>
      <button type="button" className="ssl-skip" onClick={leave}>
        Skip intro
      </button>
    </div>
  );
}

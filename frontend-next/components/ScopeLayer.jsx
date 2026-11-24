'use client';

import React, { useEffect, useRef } from 'react';

// Elements that make the scope "lock on" (ring tightens and turns celadon).
const INTERACTIVE =
  'a[href], button, select, summary, label, [role="tab"], [role="button"], .skill-pill, .ns-project-card';
// Text fields swap the reticle for a slim gold caret so typing stays precise.
const TEXTUAL =
  'input:not([type="checkbox"]):not([type="radio"]):not([type="range"]):not([type="button"]):not([type="submit"]), textarea, [contenteditable="true"]';

/**
 * Site-wide animated constellation background + custom scope reticle cursor.
 * Hardened so:
 * - Click radar pings clamp age >= 0 and radius >= 0.5 (never throws IndexSizeError on ctx.arc).
 * - requestAnimationFrame reschedules defensively inside try/finally so the loop never halts.
 * - Pointer tracking works smoothly even across clicks, unmounted targets, <select>, or reduced-motion.
 */
export function ScopeLayer() {
  const canvasRef = useRef(null);
  const ringRef = useRef(null);
  const dotRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ring = ringRef.current;
    const dot = dotRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return undefined;

    const root = document.documentElement;
    const TAU = Math.PI * 2;
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const fine = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

    let W = 0;
    let H = 0;
    let particles = [];
    let last = 0;
    let raf = 0;
    let disposed = false;
    let downTimer = 0;
    const m = { x: -999, y: -999, sx: -999, sy: -999, inside: false };
    const pings = [];

    if (fine) root.classList.add('has-scope-cursor');

    function size() {
      const D = Math.min(window.devicePixelRatio || 1, 2);
      W = window.innerWidth;
      H = window.innerHeight;
      canvas.width = W * D;
      canvas.height = H * D;
      ctx.setTransform(D, 0, 0, D, 0, 0);
      const n = Math.min(90, Math.round((W * H) / 17000));
      particles = [];
      for (let i = 0; i < n; i += 1) {
        particles.push({
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

    function updateHoverState(targetEl) {
      const el =
        targetEl instanceof Element
          ? targetEl
          : m.x >= 0 && m.y >= 0
          ? document.elementFromPoint(m.x, m.y)
          : null;
      const isText = Boolean(el?.closest?.(TEXTUAL));
      const isHover = !isText && Boolean(el?.closest?.(INTERACTIVE));
      ring?.classList.toggle('is-text', isText);
      dot?.classList.toggle('is-text', isText);
      ring?.classList.toggle('is-hover', isHover);
      dot?.classList.toggle('is-hover', isHover);
    }

    function placeCursor() {
      if (!fine || !ring || !dot) return;
      ring.style.transform = `translate3d(${m.sx.toFixed(2)}px, ${m.sy.toFixed(2)}px, 0)`;
      dot.style.transform = `translate3d(${m.x.toFixed(2)}px, ${m.y.toFixed(2)}px, 0)`;
    }

    function clearDown() {
      window.clearTimeout(downTimer);
      ring?.classList.remove('is-down');
    }

    function draw(frameTs) {
      const now = performance.now();
      const dt = Math.min(40, Math.max(1, now - (last || now) || 16));
      last = now;

      const wander = !fine;
      if (wander) {
        const wt = frameTs || now;
        m.x = W / 2 + Math.sin(wt * 0.00023) * W * 0.32 + Math.sin(wt * 0.00071) * W * 0.08;
        m.y = H / 2 + Math.sin(wt * 0.00031 + 1) * H * 0.28 + Math.cos(wt * 0.0009) * H * 0.06;
        if (m.sx < -900) {
          m.sx = m.x;
          m.sy = m.y;
        }
      }

      const tracking = wander || m.inside;
      const follow = fine ? 0.26 : still ? 1 : 0.14;
      if (m.x > -900) {
        if (m.sx < -900) {
          m.sx = m.x;
          m.sy = m.y;
        } else {
          m.sx += (m.x - m.sx) * follow;
          m.sy += (m.y - m.sy) * follow;
        }
      }

      ctx.clearRect(0, 0, W, H);
      ctx.lineWidth = 1;

      // Radar pings from clicks: strictly clamp age in [0, 1] and radius >= 0.5
      for (let k = pings.length - 1; k >= 0; k -= 1) {
        const pg = pings[k];
        const age = Math.max(0, (now - pg.t) / 900);
        if (age >= 1) {
          pings.splice(k, 1);
          continue;
        }
        const outerR = Math.max(0.5, (1 - Math.pow(1 - age, 3)) * 220);
        pg.r = outerR;
        ctx.strokeStyle = `rgba(226,180,74,${(1 - age) * 0.45})`;
        ctx.beginPath();
        ctx.arc(pg.x, pg.y, outerR, 0, TAU);
        ctx.stroke();

        const innerR = Math.max(0.5, outerR * 0.62);
        ctx.strokeStyle = `rgba(172,225,175,${(1 - age) * 0.18})`;
        ctx.beginPath();
        ctx.arc(pg.x, pg.y, innerR, 0, TAU);
        ctx.stroke();
      }

      for (let i = 0; i < particles.length; i += 1) {
        const p = particles[i];
        if (!still) {
          p.x += (p.vx * dt) / 16;
          p.y += (p.vy * dt) / 16;
        }
        if (p.x < -10) p.x = W + 10;
        else if (p.x > W + 10) p.x = -10;
        if (p.y < -10) p.y = H + 10;
        else if (p.y > H + 10) p.y = -10;

        if (tracking && !still) {
          const dx = m.sx - p.x;
          const dy = m.sy - p.y;
          const dm = Math.sqrt(dx * dx + dy * dy);
          if (dm < 150 && dm > 1) {
            p.x += (dx / dm) * 0.18;
            p.y += (dy / dm) * 0.18;
          }
        }
        for (let k = 0; k < pings.length; k += 1) {
          const pg = pings[k];
          const d = Math.hypot(p.x - pg.x, p.y - pg.y);
          if (Math.abs(d - pg.r) < 10) p.l = 1;
        }
        p.l *= 0.97;
      }

      for (let i = 0; i < particles.length; i += 1) {
        const p = particles[i];
        for (let j = i + 1; j < particles.length; j += 1) {
          const q = particles[j];
          const ex = p.x - q.x;
          const ey = p.y - q.y;
          const ed = Math.sqrt(ex * ex + ey * ey);
          if (ed < 130) {
            ctx.strokeStyle = `rgba(172,225,175,${(1 - ed / 130) * 0.14 + Math.max(p.l, q.l) * 0.12})`;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.stroke();
          }
        }
        if (tracking) {
          const cm = Math.sqrt((m.sx - p.x) * (m.sx - p.x) + (m.sy - p.y) * (m.sy - p.y));
          if (cm < 150) {
            ctx.strokeStyle = `rgba(226,180,74,${(1 - cm / 150) * 0.28})`;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(m.sx, m.sy);
            ctx.stroke();
          }
        }
      }

      for (let i = 0; i < particles.length; i += 1) {
        const p = particles[i];
        const col = p.g ? '226,180,74' : '172,225,175';
        ctx.shadowBlur = p.l > 0.05 ? 14 * p.l : 0;
        ctx.shadowColor = `rgba(${col},.9)`;
        ctx.fillStyle = `rgba(${col},${0.35 + 0.55 * p.l})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(0.5, p.r + p.l * 1.2), 0, TAU);
        ctx.fill();
      }
      ctx.shadowBlur = 0;

      if (wander) {
        ctx.strokeStyle = 'rgba(226,180,74,.35)';
        ctx.beginPath();
        ctx.arc(m.sx, m.sy, 34, 0, TAU);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(m.sx - 44, m.sy);
        ctx.lineTo(m.sx - 26, m.sy);
        ctx.moveTo(m.sx + 26, m.sy);
        ctx.lineTo(m.sx + 44, m.sy);
        ctx.moveTo(m.sx, m.sy - 44);
        ctx.lineTo(m.sx, m.sy - 26);
        ctx.moveTo(m.sx, m.sy + 26);
        ctx.lineTo(m.sx, m.sy + 44);
        ctx.stroke();
      }

      placeCursor();
    }

    function loop(frameTs) {
      if (disposed) return;
      raf = window.requestAnimationFrame(loop);
      try {
        draw(frameTs);
      } catch {
        // Keep loop alive cleanly even if a transient viewport frame occurs
      }
    }

    const syncPointerPos = (e) => {
      if (e.pointerType === 'touch') return;
      m.x = e.clientX;
      m.y = e.clientY;
      if (!m.inside) {
        m.inside = true;
        if (m.sx < -900) {
          m.sx = m.x;
          m.sy = m.y;
        }
        root.classList.add('scope-visible');
      }
      // Immediate zero-latency update for center dot
      if (fine && dot) {
        dot.style.transform = `translate3d(${m.x.toFixed(2)}px, ${m.y.toFixed(2)}px, 0)`;
      }
    };

    const onMove = (e) => {
      syncPointerPos(e);
      updateHoverState(e.target);
    };

    const onLeave = () => {
      m.inside = false;
      clearDown();
      root.classList.remove('scope-visible');
    };

    const onOver = (e) => {
      updateHoverState(e.target);
    };

    const onDown = (e) => {
      syncPointerPos(e);
      updateHoverState(e.target);
      if (e.pointerType !== 'touch') {
        ring?.classList.add('is-down');
        window.clearTimeout(downTimer);
        downTimer = window.setTimeout(clearDown, 240);
      }
      if (!still) {
        pings.push({ x: e.clientX, y: e.clientY, t: performance.now(), r: 0.5 });
        if (pings.length > 4) pings.shift();
      }
    };

    const onUp = () => {
      clearDown();
      window.requestAnimationFrame(() => updateHoverState(null));
    };

    size();
    window.addEventListener('resize', size);
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('mousemove', onMove, { passive: true });
    window.addEventListener('pointerdown', onDown, { passive: true });
    window.addEventListener('pointerup', onUp, { passive: true });
    window.addEventListener('mouseup', onUp, { passive: true });
    window.addEventListener('pointercancel', clearDown, { passive: true });
    window.addEventListener('dragend', clearDown, { passive: true });
    window.addEventListener('blur', onLeave);
    root.addEventListener('mouseleave', onLeave);
    document.addEventListener('pointerover', onOver, { passive: true });

    raf = window.requestAnimationFrame(loop);

    return () => {
      disposed = true;
      window.cancelAnimationFrame(raf);
      window.clearTimeout(downTimer);
      window.removeEventListener('resize', size);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('pointerdown', onDown);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('mouseup', onUp);
      window.removeEventListener('pointercancel', clearDown);
      window.removeEventListener('dragend', clearDown);
      window.removeEventListener('blur', onLeave);
      root.removeEventListener('mouseleave', onLeave);
      document.removeEventListener('pointerover', onOver);
      root.classList.remove('has-scope-cursor', 'scope-visible');
    };
  }, []);

  return (
    <>
      <canvas ref={canvasRef} className="scope-canvas" aria-hidden="true" />
      <div ref={ringRef} className="scope-ring" aria-hidden="true">
        <svg viewBox="-40 -40 80 80">
          <circle r="26" />
          <path d="M-38 0H-20M20 0H38M0 -38V-20M0 20V38" />
        </svg>
      </div>
      <div ref={dotRef} className="scope-dot" aria-hidden="true" />
    </>
  );
}

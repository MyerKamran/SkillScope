'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const EASE = [0.22, 1, 0.36, 1];

function BrandGlyph() {
  return (
    <svg className="brand-glyph" viewBox="0 0 100 100" aria-hidden="true">
      <path
        strokeWidth="10"
        d="M86 32V28Q86 14 72 14H30Q14 14 14 30V36Q14 50 30 50H70Q86 50 86 64V70Q86 86 70 86H28Q14 86 14 72V68"
      />
      <path strokeWidth="6" d="M72 42V38Q72 28 62 28H36Q28 28 28 36" />
      <path strokeWidth="6" d="M28 58V62Q28 72 38 72H64Q72 72 72 64" />
    </svg>
  );
}

function BrandWord() {
  return (
    <>
      <BrandGlyph />
      <span>killscope</span>
      <span className="brand-period">.</span>
    </>
  );
}

/**
 * NSIDE-inspired header: a solid celadon brand block (wordmark + menu toggle) flush with the
 * top edge on the left, tracked uppercase text links on the right, and a full-screen menu.
 */
export function SiteHeader({ items, activeTab, onNavigate }) {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const toggleRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Modal behaviour for the full-screen menu: inert page, focus management, Esc to close.
  useEffect(() => {
    if (!menuOpen) return undefined;
    const html = document.documentElement;
    const background = Array.from(document.querySelectorAll('[data-inert-when-menu]'));
    html.classList.add('menu-open');
    background.forEach((el) => {
      el.inert = true;
    });
    const focusTimer = window.requestAnimationFrame(() => closeRef.current?.focus());
    const onKey = (e) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => {
      window.cancelAnimationFrame(focusTimer);
      html.classList.remove('menu-open');
      background.forEach((el) => {
        el.inert = false;
      });
      document.removeEventListener('keydown', onKey);
      toggleRef.current?.focus({ preventScroll: true });
    };
  }, [menuOpen]);

  const go = (id) => {
    setMenuOpen(false);
    onNavigate(id);
  };

  return (
    <>
      <header className={`site-header${scrolled ? ' scrolled' : ''}`} data-inert-when-menu="">
        <div className="site-header-inner">
          <div className="brand-block">
            <button type="button" className="brand-mark" onClick={() => go('home')} aria-label="SkillScope home">
              <BrandWord />
            </button>
            <button
              ref={toggleRef}
              type="button"
              className="menu-toggle"
              aria-label="Open menu"
              aria-expanded={menuOpen}
              aria-controls="site-menu"
              onClick={() => setMenuOpen(true)}
            >
              <span className="menu-lines" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
            </button>
          </div>

          <nav className="site-nav" aria-label="Primary">
            {items.map((item) => {
              const active = item.id === activeTab;
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`site-nav-link${active ? ' active' : ''}`}
                  aria-current={active ? 'page' : undefined}
                  onClick={() => go(item.id)}
                >
                  {item.short}
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      <AnimatePresence>
        {menuOpen && (
          <motion.div
            id="site-menu"
            className="site-menu"
            role="dialog"
            aria-modal="true"
            aria-label="Site menu"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4, ease: EASE }}
          >
            <div className="site-menu-inner">
              <div className="site-menu-top">
                <div className="brand-block">
                  <span className="brand-mark" aria-hidden="true">
                    <BrandWord />
                  </span>
                  <button
                    ref={closeRef}
                    type="button"
                    className="menu-toggle is-open"
                    aria-label="Close menu"
                    onClick={() => setMenuOpen(false)}
                  >
                    <span className="menu-lines" aria-hidden="true">
                      <i />
                      <i />
                      <i />
                    </span>
                  </button>
                </div>
              </div>

              <ul className="site-menu-list">
                {items.map((item, idx) => {
                  const active = item.id === activeTab;
                  return (
                    <motion.li
                      key={item.id}
                      initial={{ opacity: 0, y: 28 }}
                      animate={{ opacity: 1, y: 0, transition: { delay: 0.08 + idx * 0.06, duration: 0.55, ease: EASE } }}
                      exit={{ opacity: 0, y: 10, transition: { duration: 0.2, ease: EASE } }}
                    >
                      <button
                        type="button"
                        className={`site-menu-link${active ? ' active' : ''}`}
                        aria-current={active ? 'page' : undefined}
                        onClick={() => go(item.id)}
                      >
                        <span className="site-menu-num">{String(idx + 1).padStart(2, '0')}</span>
                        <span className="site-menu-label">{item.label}</span>
                        <span className="site-menu-sub">{item.subtitle}</span>
                      </button>
                    </motion.li>
                  );
                })}
              </ul>

              <div className="site-menu-foot">
                <span>FAST-NUCES Karachi · BDS-5B</span>
                <span>Python Lakehouse · MySQL 8.0 · Next.js</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

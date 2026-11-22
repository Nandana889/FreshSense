import { useState } from 'react';
import { Leaf, Menu, X } from 'lucide-react';

const NAV_LINKS = [
  { href: '#home', label: 'Home' },
  { href: '#about', label: 'About' },
  { href: '#how-it-works', label: 'How It Works' },
];

export default function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="navbar">
      <nav className="navbar__inner container" aria-label="Main">
        <a className="brand" href="#home" onClick={() => setIsMenuOpen(false)}>
          <span className="brand__mark" aria-hidden="true">
            <Leaf size={20} strokeWidth={2.2} />
          </span>
          <span className="brand__name">FreshSense</span>
        </a>

        <button
          type="button"
          className="navbar__toggle"
          aria-label={isMenuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={isMenuOpen}
          aria-controls="nav-links"
          onClick={() => setIsMenuOpen((open) => !open)}
        >
          {isMenuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>

        <ul id="nav-links" className={`navbar__links${isMenuOpen ? ' is-open' : ''}`}>
          {NAV_LINKS.map(({ href, label }) => (
            <li key={href}>
              <a href={href} onClick={() => setIsMenuOpen(false)}>
                {label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}

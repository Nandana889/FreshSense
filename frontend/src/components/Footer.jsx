import { Leaf } from 'lucide-react';

const FOOTER_TAGS = [
  'Explainable AI',
  'Standard Vision Transformer',
  'Vegetable Freshness Classification',
];

// The team behind the project. Kept in the footer rather than the About
// section so the credit is on every screen without interrupting the
// explanation of how the model works.
const TEAM = ['Nandana K', 'Keerthana E', 'Rajeswari B'];

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer__inner">
        <p className="footer__name">
          <Leaf size={18} aria-hidden="true" />
          FreshSense
        </p>
        <ul className="footer__tags">
          {FOOTER_TAGS.map((tag) => (
            <li key={tag}>{tag}</li>
          ))}
        </ul>
      </div>

      <div className="container footer__credits">
        <h2 className="footer__credits-label">Built by</h2>
        <ul className="footer__team">
          {TEAM.map((member) => (
            <li key={member}>{member}</li>
          ))}
        </ul>
      </div>
    </footer>
  );
}

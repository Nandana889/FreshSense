import { Leaf } from 'lucide-react';

const FOOTER_TAGS = [
  'Explainable AI',
  'Standard Vision Transformer',
  'Vegetable Freshness Classification',
];

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
    </footer>
  );
}

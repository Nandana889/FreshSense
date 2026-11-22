import { ArrowDown } from 'lucide-react';
import PatchGrid from './PatchGrid.jsx';

export default function Hero() {
  return (
    <section id="home" className="hero">
      <div className="container hero__grid">
        <div className="hero__copy">
          <p className="eyebrow">Vegetable Freshness Classification</p>
          <h1>Know Your Vegetable Freshness</h1>
          <p className="hero__subtitle">
            AI-Powered Freshness Detection with Explainable Artificial Intelligence
          </p>
          <p className="hero__text">
            Upload a vegetable image and let our Vision Transformer model classify its freshness
            while Grad-CAM visualizations explain the regions that influenced the prediction.
          </p>
          <a className="button button--primary button--large" href="#analyze">
            Analyze Vegetable
            <ArrowDown size={18} aria-hidden="true" />
          </a>
        </div>

        <figure className="hero__figure">
          <PatchGrid />
          <figcaption>
            A Vision Transformer reads a 224 × 224 image as a 14 × 14 grid of patches.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

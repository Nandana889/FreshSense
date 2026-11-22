import { Brain, ClipboardCheck, Flame, ImageUp, SlidersHorizontal } from 'lucide-react';

const STEPS = [
  { Icon: ImageUp, title: 'Image Upload', text: 'User uploads a vegetable image.' },
  { Icon: SlidersHorizontal, title: 'Image Processing', text: 'The image is resized and normalized.' },
  {
    Icon: Brain,
    title: 'Freshness Classification',
    text: 'Standard ViT predicts one of three freshness classes.',
  },
  { Icon: Flame, title: 'Visual Explanation', text: 'Grad-CAM generates a heatmap and overlay.' },
  {
    Icon: ClipboardCheck,
    title: 'Shopkeeper Decision',
    text: 'An agent turns the grade into a selling window and a sell-or-discard action.',
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="section section--tinted">
      <div className="container">
        <header className="section-header">
          <p className="eyebrow">Workflow</p>
          <h2>How It Works</h2>
        </header>

        <ol className="steps">
          {STEPS.map(({ Icon, title, text }, index) => (
            <li key={title} className="step">
              <span className="step__icon" aria-hidden="true">
                <Icon size={24} />
              </span>
              <p className="step__number">Step {index + 1}</p>
              <h3>{title}</h3>
              <p>{text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

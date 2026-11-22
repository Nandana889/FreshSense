import { formatClassName, getClassStyle } from '../utils/freshnessClasses.js';

const CLASS_NAMES = ['Fresh', 'Mildly_Spoiled', 'Spoiled'];

export default function About() {
  return (
    <section id="about" className="section">
      <div className="container about">
        <div>
          <p className="eyebrow">About the project</p>
          <h2>Classification you can inspect</h2>
          <p className="section-lead">
            This project uses a Vision Transformer (ViT) for three-class vegetable freshness
            classification and Gradient-weighted Class Activation Mapping (Grad-CAM) to provide
            visual explanations of model predictions.
          </p>
        </div>

        <div className="card about__classes">
          <h3>Freshness classes</h3>
          <ul>
            {CLASS_NAMES.map((name) => {
              const { tone, Icon } = getClassStyle(name);
              return (
                <li key={name} className={`class-chip class-chip--${tone}`}>
                  <Icon size={20} aria-hidden="true" />
                  {formatClassName(name)}
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </section>
  );
}

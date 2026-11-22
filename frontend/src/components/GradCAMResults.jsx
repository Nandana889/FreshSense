import { formatClassName } from '../utils/freshnessClasses.js';

const toImageSrc = (base64Data) => `data:image/png;base64,${base64Data}`;

export default function GradCAMResults({ result }) {
  const predictedClass = formatClassName(result.predicted_class);

  const panels = [
    {
      title: 'Original Image',
      text: 'The image as the model received it, resized to 224 × 224 pixels.',
      image: result.original_image,
    },
    {
      title: 'Grad-CAM Heatmap',
      text: `Regions that contributed to the "${predictedClass}" prediction. Warmer colours mark stronger influence.`,
      image: result.heatmap,
    },
    {
      title: 'Grad-CAM Overlay',
      text: 'The heatmap blended over the image, showing where those regions fall on the vegetable.',
      image: result.gradcam_overlay,
    },
  ];

  return (
    <section id="explanation" className="section">
      <div className="container">
        <header className="section-header">
          <p className="eyebrow">Visual explanation</p>
          <h2>Explainable AI – Understanding the Prediction</h2>
          <p className="section-lead">
            Grad-CAM highlights image regions that contributed to the model&apos;s prediction. The
            heatmap helps users understand where the model focused when making its classification.
          </p>
        </header>

        <div className="xai-grid">
          {panels.map(({ title, text, image }) => (
            <figure key={title} className="card xai-panel">
              <img
                src={toImageSrc(image)}
                alt={`${title} for the image predicted as ${predictedClass}`}
              />
              <figcaption>
                <h3>{title}</h3>
                <p>{text}</p>
              </figcaption>
            </figure>
          ))}
        </div>

        <div className="xai-footer">
          <div className="heat-legend">
            <span>Lower influence</span>
            <span className="heat-legend__scale" aria-hidden="true" />
            <span>Higher influence</span>
          </div>
          <p>
            Highlighted regions show where the model focused. They do not prove that spoilage is
            present in those areas.
          </p>
        </div>
      </div>
    </section>
  );
}

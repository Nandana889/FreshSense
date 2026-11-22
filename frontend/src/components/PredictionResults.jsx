import { ArrowDown, ChartColumn, Loader2, RotateCcw } from 'lucide-react';
import { formatClassName, getClassStyle } from '../utils/freshnessClasses.js';

function ProbabilityBar({ className, probability, isPredicted }) {
  const { tone } = getClassStyle(className);
  const label = formatClassName(className);

  return (
    <li className={`probability probability--${tone}`}>
      <div className="probability__row">
        <span className="probability__label">
          {label}
          {isPredicted && <span className="probability__tag">Predicted</span>}
        </span>
        <span className="probability__value">{probability.toFixed(2)}%</span>
      </div>
      <div
        className="probability__track"
        role="progressbar"
        aria-label={`${label} probability`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={probability}
      >
        <div className="probability__fill" style={{ width: `${probability}%` }} />
      </div>
    </li>
  );
}

function ResultSummary({ result, onAnalyzeAnother }) {
  const { predicted_class: predictedClass, confidence, class_probabilities: probabilities } = result;
  const { tone, Icon } = getClassStyle(predictedClass);

  return (
    <div className="results">
      <div className={`verdict verdict--${tone}`}>
        <span className="verdict__icon" aria-hidden="true">
          <Icon size={30} />
        </span>
        <div className="verdict__copy">
          <p className="verdict__label">Predicted class</p>
          <p className="verdict__class">{formatClassName(predictedClass)}</p>
        </div>
        <div className="verdict__confidence">
          <p className="verdict__label">Confidence</p>
          <p className="verdict__value">{confidence.toFixed(2)}%</p>
        </div>
      </div>

      <h4 className="results__heading">Class probabilities</h4>
      <ul className="probabilities">
        {Object.entries(probabilities).map(([className, probability]) => (
          <ProbabilityBar
            key={className}
            className={className}
            probability={probability}
            isPredicted={className === predictedClass}
          />
        ))}
      </ul>

      <p className="results__note">
        Confidence is the model&apos;s own probability for this class. It is not a food-safety
        assessment.
      </p>

      <div className="results__actions">
        <a className="button button--secondary" href="#explanation">
          View explanation
          <ArrowDown size={16} aria-hidden="true" />
        </a>
        <button type="button" className="button button--ghost" onClick={onAnalyzeAnother}>
          <RotateCcw size={16} aria-hidden="true" />
          Analyze another image
        </button>
      </div>
    </div>
  );
}

export default function PredictionResults({ isAnalyzing, result, onAnalyzeAnother }) {
  return (
    <article className="card prediction">
      <header className="card__header">
        <h3>Prediction results</h3>
      </header>

      {/* aria-live announces each state change to screen readers. */}
      <div aria-live="polite" className="prediction__body">
        {isAnalyzing && (
          <div className="placeholder">
            <Loader2 className="spin placeholder__icon" size={32} aria-hidden="true" />
            <p className="placeholder__title">Analyzing your image</p>
            <p>Running the Vision Transformer and generating Grad-CAM. This can take a moment.</p>
          </div>
        )}

        {!isAnalyzing && result && (
          <ResultSummary result={result} onAnalyzeAnother={onAnalyzeAnother} />
        )}

        {!isAnalyzing && !result && (
          <div className="placeholder">
            <ChartColumn className="placeholder__icon" size={32} aria-hidden="true" />
            <p className="placeholder__title">No analysis yet</p>
            <p>The predicted class and all three probabilities will appear here.</p>
          </div>
        )}
      </div>
    </article>
  );
}

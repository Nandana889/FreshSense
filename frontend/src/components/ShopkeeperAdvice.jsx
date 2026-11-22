import { useState } from 'react';
import {
  BadgeCheck,
  CalendarClock,
  CircleHelp,
  Crosshair,
  Eye,
  Hand,
  Loader2,
  MessageCircleQuestion,
  Scissors,
  SendHorizontal,
  ShoppingBasket,
  Sparkles,
  Trash2,
  TriangleAlert,
} from 'lucide-react';

/**
 * Presentation settings per action code returned by POST /advise.
 * `tone` reuses the same palette as the freshness verdict, so a discard
 * decision looks the same whether it came from the grade or from the advisor.
 */
const ACTIONS = {
  sell_normally: { tone: 'fresh', Icon: BadgeCheck },
  prioritise_sale: { tone: 'mild', Icon: ShoppingBasket },
  trim_and_discount: { tone: 'mild', Icon: Scissors },
  discard: { tone: 'spoiled', Icon: Trash2 },
  needs_human_check: { tone: 'mild', Icon: Hand },
  check_then_trim_or_discard: { tone: 'mild', Icon: Scissors },
  needs_vegetable_type: { tone: 'unknown', Icon: CircleHelp },
};

const UNKNOWN_ACTION = { tone: 'unknown', Icon: CircleHelp };

const STORAGE_LABELS = {
  ambient: 'Open shelf',
  refrigerated: 'Chiller',
};

const VEGETABLE_LABELS = {
  bellpepper: 'Bell pepper',
  carrot: 'Carrot',
  cucumber: 'Cucumber',
  potato: 'Potato',
  tomato: 'Tomato',
};

const labelFor = (value) => VEGETABLE_LABELS[value] ?? value;

function formatSellBy(isoDate) {
  if (!isoDate) return null;
  // Parsed as UTC to avoid the date shifting a day in negative timezones.
  const parsed = new Date(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(parsed.valueOf())) return isoDate;
  return parsed.toLocaleDateString(undefined, {
    timeZone: 'UTC',
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });
}

function AdviceControls({ options, vegetable, storage, onVegetableChange, onStorageChange, busy }) {
  return (
    <div className="advice__controls">
      <label className="field">
        <span className="field__label">Vegetable</span>
        <select
          className="field__input"
          value={vegetable}
          disabled={busy}
          onChange={(event) => onVegetableChange(event.target.value)}
        >
          <option value="">Select…</option>
          {options.vegetables.map((name) => (
            <option key={name} value={name}>
              {labelFor(name)}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="field" disabled={busy}>
        <legend className="field__label">Storage</legend>
        <div className="segmented">
          {options.storage_conditions.map((condition) => (
            <label
              key={condition}
              className={`segmented__option${
                storage === condition ? ' segmented__option--active' : ''
              }`}
            >
              <input
                type="radio"
                name="storage"
                value={condition}
                checked={storage === condition}
                onChange={() => onStorageChange(condition)}
              />
              {STORAGE_LABELS[condition] ?? condition}
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  );
}

function AdviceBody({ advice }) {
  const { tone, Icon } = ACTIONS[advice.action] ?? UNKNOWN_ACTION;
  const sellBy = formatSellBy(advice.sell_by_date);
  const hasWindow = advice.sell_within_days > 0;

  return (
    <div className="advice__body">
      <div className={`decision decision--${tone}`}>
        <span className="decision__icon" aria-hidden="true">
          <Icon size={30} />
        </span>
        <div className="decision__copy">
          <p className="decision__label">{advice.action_label}</p>
          <p className="decision__headline">{advice.headline}</p>
        </div>
        {hasWindow && (
          <div className="decision__window">
            <p className="decision__label">
              <CalendarClock size={14} aria-hidden="true" /> Sell by
            </p>
            <p className="decision__value">{sellBy ?? `${advice.sell_within_days} days`}</p>
          </div>
        )}
      </div>

      <p className="advice__message">{advice.shopkeeper_message}</p>

      {advice.cautions?.length > 0 && (
        <ul className="advice__cautions">
          {advice.cautions.map((caution) => (
            <li key={caution}>
              <TriangleAlert size={16} aria-hidden="true" />
              <span>{caution}</span>
            </li>
          ))}
        </ul>
      )}

      {advice.where_to_look && (
        <p className="advice__look">
          <Crosshair size={16} aria-hidden="true" />
          <span>
            <strong>Where to look: </strong>
            {advice.where_to_look}
          </span>
        </p>
      )}

      {advice.inspection_note && (
        <p className="advice__inspection">
          <Eye size={16} aria-hidden="true" />
          <span>{advice.inspection_note}</span>
        </p>
      )}

      <details className="advice__details">
        <summary>Why this advice</summary>
        <p>{advice.reasoning}</p>

        {advice.references?.length > 0 && (
          <>
            <h5>Sources</h5>
            <ul className="advice__references">
              {advice.references.map((reference) => (
                <li key={reference.claim}>
                  <span className="advice__claim">{reference.claim}</span>
                  <span className="advice__source">{reference.source}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </details>
    </div>
  );
}

const SUGGESTED_QUESTIONS = [
  'What happens if I leave it out another day?',
  'Should I move the rest of the crate to the chiller?',
  'Can I sell it at a discount instead?',
];

function FollowupThread({ thread, isAsking, error, onAsk }) {
  const [draft, setDraft] = useState('');

  function submit(event) {
    event.preventDefault();
    const question = draft.trim();
    if (!question || isAsking) return;
    setDraft('');
    onAsk(question);
  }

  return (
    <section className="followup">
      <h4 className="followup__heading">
        <MessageCircleQuestion size={17} aria-hidden="true" />
        Ask about this item
      </h4>

      {thread.length === 0 && !isAsking && (
        <ul className="followup__suggestions">
          {SUGGESTED_QUESTIONS.map((question) => (
            <li key={question}>
              <button type="button" className="chip" onClick={() => onAsk(question)}>
                {question}
              </button>
            </li>
          ))}
        </ul>
      )}

      {thread.length > 0 && (
        <ol className="followup__thread">
          {thread.map((turn, index) => (
            <li
              // Turns are append-only, so the index is a stable identity here.
              key={`${turn.role}-${index}`}
              className={`bubble bubble--${turn.role}`}
            >
              {turn.content}
            </li>
          ))}
        </ol>
      )}

      <div aria-live="polite">
        {isAsking && (
          <p className="followup__thinking">
            <Loader2 className="spin" size={16} aria-hidden="true" />
            Thinking…
          </p>
        )}
        {error && (
          <p className="advice__error" role="alert">
            <TriangleAlert size={16} aria-hidden="true" /> {error}
          </p>
        )}
      </div>

      <form className="followup__form" onSubmit={submit}>
        <label className="sr-only" htmlFor="followup-input">
          Your question about this item
        </label>
        <input
          id="followup-input"
          className="field__input followup__input"
          type="text"
          placeholder="e.g. can I still sell these tomorrow?"
          value={draft}
          maxLength={2000}
          disabled={isAsking}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button
          type="submit"
          className="button button--primary"
          disabled={isAsking || !draft.trim()}
        >
          <SendHorizontal size={16} aria-hidden="true" />
          Ask
        </button>
      </form>
    </section>
  );
}

export default function ShopkeeperAdvice({
  advice,
  options,
  vegetable,
  storage,
  isAdvising,
  error,
  followupAvailable,
  followupThread,
  isAsking,
  followupError,
  onAsk,
  onVegetableChange,
  onStorageChange,
}) {
  const usedAgent = advice?.engine === 'claude-agent';

  return (
    <section id="advice" className="section">
      <div className="container">
        <header className="section-header">
          <p className="eyebrow">Decision</p>
          <h2>What to do with this stock</h2>
          <p className="section-lead">
            The grade above says how spoiled the item looks. This step turns it into an action, using
            published storage and food-safety guidance.
          </p>
        </header>

        <article className="card advice">
          <header className="card__header">
            <h3>Shopkeeper advice</h3>
            <span className={`badge badge--${usedAgent ? 'agent' : 'rules'}`}>
              {usedAgent ? (
                <>
                  <Sparkles size={13} aria-hidden="true" /> AI agent
                </>
              ) : (
                'Rule-based'
              )}
            </span>
          </header>

          {options && (
            <AdviceControls
              options={options}
              vegetable={vegetable}
              storage={storage}
              onVegetableChange={onVegetableChange}
              onStorageChange={onStorageChange}
              busy={isAdvising}
            />
          )}

          <div aria-live="polite">
            {isAdvising && (
              <div className="placeholder">
                <Loader2 className="spin placeholder__icon" size={32} aria-hidden="true" />
                <p className="placeholder__title">Working out the decision</p>
                <p>Checking storage data and food-safety rules for this vegetable.</p>
              </div>
            )}

            {!isAdvising && error && (
              <p className="advice__error" role="alert">
                <TriangleAlert size={16} aria-hidden="true" /> {error}
              </p>
            )}

            {!isAdvising && !error && advice && <AdviceBody advice={advice} />}
          </div>

          {!isAdvising && !error && advice && followupAvailable && (
            <FollowupThread
              thread={followupThread}
              isAsking={isAsking}
              error={followupError}
              onAsk={onAsk}
            />
          )}

          <p className="advice__disclaimer">
            Selling windows are estimates for typical shop conditions, not a food-safety
            certification. Use your own judgement and local regulations for the final call.
          </p>
        </article>
      </div>
    </section>
  );
}

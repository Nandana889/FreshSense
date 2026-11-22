/**
 * Client for the FastAPI backend.
 *
 * Defaults to 127.0.0.1:8000, which is where the setup instructions start the
 * server. Override it when the backend runs elsewhere by setting
 * VITE_API_BASE_URL (in frontend/.env, or on the command line) -- useful when
 * port 8000 is already taken:
 *
 *   VITE_API_BASE_URL=http://127.0.0.1:8001 npm run dev
 *
 * Whichever port the API is on, the backend's CORS policy still requires the
 * page itself to be served from http://localhost:5173.
 */
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

// Grad-CAM on a CPU can be slow, but a request should not hang forever.
const PREDICT_TIMEOUT_MS = 120_000;
const HEALTH_TIMEOUT_MS = 5_000;
// The advisor may run a multi-step agent loop, so it needs more than a health
// check but far less than a Grad-CAM pass.
const ADVICE_TIMEOUT_MS = 90_000;

const REQUIRED_FIELDS = [
  'predicted_class',
  'confidence',
  'class_probabilities',
  'original_image',
  'heatmap',
  'gradcam_overlay',
];

/** FastAPI sends `detail` as a string, or as a list for validation errors. */
function readErrorDetail(body) {
  const detail = body?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join('; ');
  return '';
}

function describeHttpError(status, detail) {
  if (status >= 500) {
    return `The backend could not process this image.${detail ? ` Details: ${detail}` : ''}`;
  }
  return detail || `The request was rejected (HTTP ${status}).`;
}

/**
 * Sends an image to POST /predict and returns the backend's JSON response.
 * Rejects with an AbortError if `signal` is aborted; every other failure is
 * an Error whose message is safe to show to the user.
 */
export async function predictFreshness(file, signal) {
  // The field name must be exactly `file`. Content-Type is deliberately not
  // set here: the browser has to add the multipart boundary itself.
  const formData = new FormData();
  formData.append('file', file);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/predict`, {
      method: 'POST',
      body: formData,
      signal: AbortSignal.any([signal, AbortSignal.timeout(PREDICT_TIMEOUT_MS)]),
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    if (error.name === 'TimeoutError') {
      throw new Error('The analysis took too long and was stopped. Please try again.');
    }
    throw new Error(
      `Could not connect to the backend at ${API_BASE_URL}. Make sure the FastAPI server is running, then try again.`,
    );
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(describeHttpError(response.status, readErrorDetail(body)));
  }

  const isComplete = REQUIRED_FIELDS.every((field) => body?.[field] != null);
  if (!isComplete) {
    throw new Error('The backend returned an incomplete response. Please try again.');
  }

  return body;
}

/**
 * Asks POST /advise what the shopkeeper should do with this item.
 *
 * `vegetable` may be null: the backend then replies with an action of
 * `needs_vegetable_type` rather than guessing, because the sell-or-discard
 * rule depends on whether the produce is dense or high-moisture.
 */
export async function fetchAdvice({ result, vegetable, storage }, signal) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/advise`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        freshness_class: result.predicted_class,
        confidence: result.confidence,
        class_probabilities: result.class_probabilities,
        vegetable: vegetable || null,
        storage,
        // Sending the pair lets the agent name the part of the item to check.
        // The backend ignores them unless the agent is configured.
        original_image: result.original_image,
        gradcam_overlay: result.gradcam_overlay,
      }),
      signal: AbortSignal.any([signal, AbortSignal.timeout(ADVICE_TIMEOUT_MS)]),
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    if (error.name === 'TimeoutError') {
      throw new Error('Getting advice took too long and was stopped. Please try again.');
    }
    throw new Error(
      `Could not reach the advisor at ${API_BASE_URL}. Make sure the FastAPI server is running.`,
    );
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(describeHttpError(response.status, readErrorDetail(body)));
  }

  if (!body?.action) {
    throw new Error('The advisor returned an incomplete response. Please try again.');
  }

  return body;
}

/**
 * Asks POST /advise/followup a question about advice already given.
 *
 * Unlike the advice itself this has no offline fallback, so a 503 here means
 * the backend has no API key configured. That message is shown as-is.
 */
export async function askFollowup({ question, result, advice, vegetable, storage, history }) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/advise/followup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        freshness_class: result.predicted_class,
        confidence: result.confidence,
        class_probabilities: result.class_probabilities,
        decision: advice,
        vegetable: vegetable || null,
        storage,
        history,
      }),
      signal: AbortSignal.timeout(ADVICE_TIMEOUT_MS),
    });
  } catch (error) {
    if (error.name === 'TimeoutError') {
      throw new Error('That question took too long to answer. Please try again.');
    }
    throw new Error(`Could not reach the advisor at ${API_BASE_URL}.`);
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(readErrorDetail(body) || `The question was rejected (HTTP ${response.status}).`);
  }

  if (!body?.answer) {
    throw new Error('The advisor returned an empty answer.');
  }

  return body.answer;
}

/** Returns the GET /vegetables options, or null if the backend is unreachable. */
export async function fetchVegetableOptions() {
  try {
    const response = await fetch(`${API_BASE_URL}/vegetables`, {
      signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
    });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

/** Returns the GET /health payload, or null if the backend cannot be reached. */
export async function fetchHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
    });
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}

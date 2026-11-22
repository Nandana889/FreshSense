import { useEffect, useRef, useState } from 'react';
import Navbar from './components/Navbar.jsx';
import Hero from './components/Hero.jsx';
import ImageUpload from './components/ImageUpload.jsx';
import PredictionResults from './components/PredictionResults.jsx';
import GradCAMResults from './components/GradCAMResults.jsx';
import ShopkeeperAdvice from './components/ShopkeeperAdvice.jsx';
import HowItWorks from './components/HowItWorks.jsx';
import About from './components/About.jsx';
import Footer from './components/Footer.jsx';
import {
  askFollowup,
  fetchAdvice,
  fetchHealth,
  fetchVegetableOptions,
  predictFreshness,
} from './services/api.js';
import { validateImage } from './utils/validateImage.js';

export default function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Advice is a second, cheaper request against the same classification, so
  // changing the vegetable or the storage condition re-asks the advisor
  // without re-running the Vision Transformer.
  const [advice, setAdvice] = useState(null);
  const [adviceError, setAdviceError] = useState('');
  const [isAdvising, setIsAdvising] = useState(false);
  const [adviceOptions, setAdviceOptions] = useState(null);
  const [vegetable, setVegetable] = useState('');
  const [storage, setStorage] = useState('ambient');

  // Follow-up questions need the language model, so the box only appears when
  // the backend reports a configured API key.
  const [followupAvailable, setFollowupAvailable] = useState(false);
  const [followupThread, setFollowupThread] = useState([]);
  const [followupError, setFollowupError] = useState('');
  const [isAsking, setIsAsking] = useState(false);

  // Holds the in-flight request. A ref (rather than state) means a second
  // click is blocked immediately, before React has re-rendered the button.
  const activeRequest = useRef(null);
  const activeAdviceRequest = useRef(null);
  const resultsRef = useRef(null);

  async function handleFileSelect(candidate) {
    const validationError = await validateImage(candidate);
    if (validationError) {
      // A rejected file leaves the current selection as it was.
      setError(validationError);
      return;
    }
    setFile(candidate);
    setResult(null); // Results always belong to the image on screen.
    setError('');
    clearAdvice();
  }

  function clearAdvice() {
    activeAdviceRequest.current?.abort();
    activeAdviceRequest.current = null;
    setIsAdvising(false);
    setAdvice(null);
    setAdviceError('');
    // A question thread belongs to one item, so it never outlives the advice.
    setFollowupThread([]);
    setFollowupError('');
    setIsAsking(false);
  }

  async function handleAsk(question) {
    if (isAsking || !advice || !result) return;

    setFollowupThread((thread) => [...thread, { role: 'user', content: question }]);
    setFollowupError('');
    setIsAsking(true);

    try {
      // `followupThread` is the history as it was before this question, which
      // is exactly what the backend needs.
      const answer = await askFollowup({
        question,
        result,
        advice,
        vegetable,
        storage,
        history: followupThread,
      });
      setFollowupThread((thread) => [...thread, { role: 'assistant', content: answer }]);
    } catch (requestError) {
      setFollowupError(requestError.message);
    } finally {
      setIsAsking(false);
    }
  }

  async function handleAnalyze() {
    if (activeRequest.current) return;

    if (!file) {
      setError('Please select an image before starting the analysis.');
      return;
    }

    const controller = new AbortController();
    activeRequest.current = controller;
    setIsAnalyzing(true);
    setResult(null);
    setError('');

    try {
      setResult(await predictFreshness(file, controller.signal));
    } catch (requestError) {
      // An abort means the user cancelled, which is not an error to report.
      if (requestError.name !== 'AbortError') setError(requestError.message);
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null;
        setIsAnalyzing(false);
      }
    }
  }

  function handleReset() {
    activeRequest.current?.abort();
    activeRequest.current = null;
    setIsAnalyzing(false);
    setFile(null);
    setResult(null);
    setError('');
    clearAdvice();
  }

  function handleAnalyzeAnother() {
    handleReset();
    document.getElementById('analyze')?.scrollIntoView();
  }

  // On narrow screens the results sit below the upload card, so bring them
  // into view. On wide screens they are already visible and nothing moves.
  useEffect(() => {
    if (result) resultsRef.current?.scrollIntoView({ block: 'nearest' });
  }, [result]);

  // The selector options come from the backend so the two never disagree
  // about which vegetables the model was trained on. The health check tells us
  // whether the agent has credentials, which decides if questions are offered.
  useEffect(() => {
    let cancelled = false;

    fetchVegetableOptions().then((options) => {
      if (!cancelled && options) setAdviceOptions(options);
    });

    fetchHealth().then((health) => {
      if (!cancelled) setFollowupAvailable(Boolean(health?.advisor?.followup_available));
    });

    return () => {
      cancelled = true;
    };
  }, []);

  // Ask for advice whenever there is a result, and again whenever the
  // shopkeeper corrects the vegetable or the storage condition.
  useEffect(() => {
    if (!result) return undefined;

    const controller = new AbortController();
    activeAdviceRequest.current?.abort();
    activeAdviceRequest.current = controller;

    setIsAdvising(true);
    setAdviceError('');

    fetchAdvice({ result, vegetable, storage }, controller.signal)
      .then((payload) => {
        if (!controller.signal.aborted) setAdvice(payload);
      })
      .catch((requestError) => {
        if (requestError.name === 'AbortError') return;
        setAdvice(null);
        setAdviceError(requestError.message);
      })
      .finally(() => {
        if (activeAdviceRequest.current === controller) {
          activeAdviceRequest.current = null;
          setIsAdvising(false);
        }
      });

    return () => controller.abort();
  }, [result, vegetable, storage]);

  return (
    <>
      <Navbar />
      <main>
        <Hero />

        <section id="analyze" className="section section--tinted">
          <div className="container">
            <header className="section-header">
              <p className="eyebrow">Analysis</p>
              <h2>Analyze a vegetable image</h2>
              <p className="section-lead">
                Upload one image. The prediction and its visual explanation come directly from the
                trained model.
              </p>
            </header>

            <div className="workspace">
              <ImageUpload
                file={file}
                isAnalyzing={isAnalyzing}
                error={error}
                onFileSelect={handleFileSelect}
                onAnalyze={handleAnalyze}
                onReset={handleReset}
              />
              <div ref={resultsRef} className="workspace__results">
                <PredictionResults
                  isAnalyzing={isAnalyzing}
                  result={result}
                  onAnalyzeAnother={handleAnalyzeAnother}
                />
              </div>
            </div>
          </div>
        </section>

        {result && (
          <ShopkeeperAdvice
            advice={advice}
            options={adviceOptions}
            vegetable={vegetable}
            storage={storage}
            isAdvising={isAdvising}
            error={adviceError}
            followupAvailable={followupAvailable}
            followupThread={followupThread}
            isAsking={isAsking}
            followupError={followupError}
            onAsk={handleAsk}
            onVegetableChange={setVegetable}
            onStorageChange={setStorage}
          />
        )}

        {result && <GradCAMResults result={result} />}

        <HowItWorks />
        <About />
      </main>
      <Footer />
    </>
  );
}

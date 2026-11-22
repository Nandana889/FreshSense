import { useEffect, useRef, useState } from 'react';
import { CircleAlert, ImageUp, Loader2, ScanSearch, X } from 'lucide-react';
import ApiStatus from './ApiStatus.jsx';
import {
  ACCEPTED_FILE_TYPES,
  MAX_FILE_SIZE_MB,
  formatFileSize,
} from '../utils/validateImage.js';

export default function ImageUpload({
  file,
  isAnalyzing,
  error,
  onFileSelect,
  onAnalyze,
  onReset,
}) {
  const inputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);

  // Object URLs hold the file in memory, so each one is released when replaced.
  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Without this, an image dropped just outside the card makes the browser
  // leave the app and open the image instead.
  useEffect(() => {
    const preventNavigation = (event) => event.preventDefault();
    window.addEventListener('dragover', preventNavigation);
    window.addEventListener('drop', preventNavigation);
    return () => {
      window.removeEventListener('dragover', preventNavigation);
      window.removeEventListener('drop', preventNavigation);
    };
  }, []);

  function handleInputChange(event) {
    const [chosen] = event.target.files;
    if (chosen) onFileSelect(chosen);
    event.target.value = ''; // Lets the same file be chosen again after a reset.
  }

  function handleDrop(event) {
    event.preventDefault();
    setIsDragging(false);
    if (isAnalyzing) return;
    const [dropped] = event.dataTransfer.files;
    if (dropped) onFileSelect(dropped);
  }

  function handleDragOver(event) {
    event.preventDefault();
    if (!isAnalyzing) setIsDragging(true);
  }

  function handleDragLeave(event) {
    // Moving onto a child element also fires dragleave, so ignore those.
    if (!event.currentTarget.contains(event.relatedTarget)) setIsDragging(false);
  }

  return (
    <article className="card upload">
      <header className="card__header">
        <h3>Upload image</h3>
        <ApiStatus />
      </header>

      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept={ACCEPTED_FILE_TYPES}
        onChange={handleInputChange}
        disabled={isAnalyzing}
        tabIndex={-1}
        aria-hidden="true"
      />

      <div
        className={`dropzone${isDragging ? ' is-dragging' : ''}${file ? ' has-file' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {previewUrl ? (
          <img className="dropzone__preview" src={previewUrl} alt={`Preview of ${file?.name}`} />
        ) : (
          <div className="dropzone__prompt">
            <span className="dropzone__icon" aria-hidden="true">
              <ImageUp size={26} />
            </span>
            <p className="dropzone__title">Drag and drop an image here</p>
            <button
              type="button"
              className="button button--secondary"
              onClick={() => inputRef.current?.click()}
            >
              Browse files
            </button>
            <p className="dropzone__hint">JPG, JPEG, PNG or WEBP, up to {MAX_FILE_SIZE_MB} MB</p>
          </div>
        )}
      </div>

      {file && (
        <div className="file-row">
          <div className="file-row__details">
            <span className="file-row__name" title={file.name}>
              {file.name}
            </span>
            <span className="file-row__size">{formatFileSize(file.size)}</span>
          </div>
          <button
            type="button"
            className="button button--ghost"
            onClick={() => inputRef.current?.click()}
            disabled={isAnalyzing}
          >
            Change
          </button>
          <button type="button" className="button button--ghost" onClick={onReset}>
            <X size={16} aria-hidden="true" />
            {isAnalyzing ? 'Cancel' : 'Remove'}
          </button>
        </div>
      )}

      {error && (
        <div className="alert" role="alert">
          <CircleAlert size={18} aria-hidden="true" />
          <p>{error}</p>
        </div>
      )}

      <button
        type="button"
        className="button button--primary button--block"
        onClick={onAnalyze}
        disabled={isAnalyzing}
      >
        {isAnalyzing ? (
          <>
            <Loader2 className="spin" size={18} aria-hidden="true" />
            Analyzing…
          </>
        ) : (
          <>
            <ScanSearch size={18} aria-hidden="true" />
            Analyze Freshness
          </>
        )}
      </button>
    </article>
  );
}

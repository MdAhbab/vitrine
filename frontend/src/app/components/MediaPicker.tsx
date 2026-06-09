import { useRef, useState } from 'react';
import { ImagePlus, Link2, Loader2, X } from 'lucide-react';
import { api, mediaUrl } from '../lib/api';

type Props = {
  value: string;
  onChange: (url: string) => void;
  bucket?: 'listings' | 'avatars' | 'documents';
  label?: string;
  accept?: string;
  className?: string;
};

export function MediaPicker({
  value, onChange, bucket = 'listings', label = 'Image', accept = 'image/*',
  className = '',
}: Props) {
  const [mode, setMode] = useState<'url' | 'upload'>('url');
  const [urlInput, setUrlInput] = useState(value.startsWith('http') ? value : '');
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const applyUrl = () => {
    const v = urlInput.trim();
    if (v) onChange(v);
  };

  const onFile = async (file: File | null) => {
    if (!file) return;
    setUploading(true);
    try {
      const res = await api.uploadFile(file, bucket);
      onChange(res.url);
      setUrlInput('');
      setMode('url');
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const src = value ? mediaUrl(value) : '';

  return (
    <div className={`space-y-2 ${className}`}>
      {label && (
        <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">{label}</div>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setMode('url')}
          className={`hairline rounded-lg px-3 h-8 text-xs inline-flex items-center gap-1.5 ${mode === 'url' ? 'border-accent' : ''}`}
        >
          <Link2 size={12} /> URL
        </button>
        <button
          type="button"
          onClick={() => setMode('upload')}
          className={`hairline rounded-lg px-3 h-8 text-xs inline-flex items-center gap-1.5 ${mode === 'upload' ? 'border-accent' : ''}`}
        >
          <ImagePlus size={12} /> Upload
        </button>
      </div>

      {mode === 'url' ? (
        <div className="flex gap-2">
          <input
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="https://… or /files/…"
            className="flex-1 hairline rounded-lg bg-surface-2 px-3 h-10 text-sm focus:border-accent outline-none"
          />
          <button type="button" onClick={applyUrl} className="hairline rounded-lg px-3 h-10 text-sm hover:border-accent">
            Use
          </button>
        </div>
      ) : (
        <label className="hairline rounded-xl border-dashed p-6 grid place-items-center cursor-pointer hover:border-accent transition-colors">
          {uploading ? <Loader2 size={20} className="animate-spin text-accent" /> : <ImagePlus size={20} className="text-text-muted" />}
          <span className="text-xs text-text-muted mt-2">{uploading ? 'Uploading…' : 'Click to choose file'}</span>
          <input
            ref={fileRef}
            type="file"
            accept={accept}
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0] ?? null)}
          />
        </label>
      )}

      {src && (
        <div className="relative inline-block">
          <img src={src} alt="" className="w-24 h-24 rounded-lg object-cover hairline" />
          <button
            type="button"
            onClick={() => onChange('')}
            className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-surface hairline grid place-items-center hover:border-danger"
            aria-label="Remove"
          >
            <X size={12} />
          </button>
        </div>
      )}
    </div>
  );
}

type MultiProps = {
  values: string[];
  onChange: (urls: string[]) => void;
  bucket?: 'listings' | 'avatars' | 'documents';
  label?: string;
  max?: number;
};

export function MediaPickerMulti({
  values, onChange, bucket = 'listings', label = 'Screenshots', max = 6,
}: MultiProps) {
  const add = (url: string) => {
    if (!url || values.includes(url) || values.length >= max) return;
    onChange([...values, url]);
  };

  return (
    <div className="space-y-3">
      <MediaPicker value="" onChange={add} bucket={bucket} label={label} />
      {values.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {values.map((v, i) => (
            <div key={`${v}-${i}`} className="relative">
              <img src={mediaUrl(v)} alt="" className="w-20 h-16 rounded-lg object-cover hairline" />
              <button
                type="button"
                onClick={() => onChange(values.filter((_, j) => j !== i))}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-surface hairline grid place-items-center text-[10px]"
                aria-label="Remove"
              >
                <X size={10} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

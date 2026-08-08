import React, { useState } from 'react'
import { mediaUrl } from '../lib/api'

const ERROR_IMG_SRC =
  'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODgiIGhlaWdodD0iODgiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgc3Ryb2tlPSIjMDAwIiBzdHJva2UtbGluZWpvaW49InJvdW5kIiBvcGFjaXR5PSIuMyIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIzLjciPjxyZWN0IHg9IjE2IiB5PSIxNiIgd2lkdGg9IjU2IiBoZWlnaHQ9IjU2IiByeD0iNiIvPjxwYXRoIGQ9Im0xNiA1OCAxNi0xOCAzMiAzMiIvPjxjaXJjbGUgY3g9IjUzIiBjeT0iMzUiIHI9IjciLz48L3N2Zz4KCg=='

export function ImageWithFallback(props: React.ImgHTMLAttributes<HTMLImageElement>) {
  // Remember *which* src failed rather than a bare boolean: this component is
  // reused across product navigations and thumbnail switches, and a sticky
  // `didError` would keep showing the placeholder for a perfectly good image.
  const [erroredSrc, setErroredSrc] = useState<string | null>(null)

  const { src, alt, style, className, ...rest } = props

  // Uploaded media arrives from the API as a relative `/files/…` path, which in
  // dev resolves against the Vite origin (:5173) instead of the API (:8000) and
  // 404s. Resolving here fixes every consumer at once; absolute http(s):/data:
  // URLs pass through mediaUrl untouched.
  const resolved = typeof src === 'string' && src ? mediaUrl(src) : undefined

  return !resolved || erroredSrc === resolved ? (
    <div
      // Themed surface token, not a fixed light gray — the broken-image state
      // was the one visual state guaranteed to look wrong in dark mode.
      className={`inline-block bg-surface-2 text-center align-middle ${className ?? ''}`}
      style={style}
    >
      <div className="flex items-center justify-center w-full h-full">
        <img src={ERROR_IMG_SRC} alt={alt ?? 'Error loading image'} {...rest} data-original-url={resolved ?? ''} />
      </div>
    </div>
  ) : (
    <img
      src={resolved}
      alt={alt}
      className={className}
      style={style}
      {...rest}
      onError={() => setErroredSrc(resolved)}
    />
  )
}

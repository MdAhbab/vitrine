import { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = { children: ReactNode; fallback?: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Uncaught render error:', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return this.props.fallback ?? (
        <div className="min-h-[40vh] grid place-items-center px-6 text-center">
          <div>
            <h1 className="font-serif text-2xl">Something went wrong</h1>
            <p className="text-text-muted text-sm mt-2 max-w-md">
              An unexpected error occurred. Try refreshing the page.
            </p>
            <button
              onClick={() => { this.setState({ error: null }); window.location.reload(); }}
              className="mt-6 text-accent hover:underline text-sm"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

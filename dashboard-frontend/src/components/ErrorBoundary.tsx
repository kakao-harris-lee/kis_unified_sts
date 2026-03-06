import { Component, ErrorInfo, ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error to console for debugging
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    this.setState({
      error,
      errorInfo,
    });
  }

  handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return (
        <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
          <div className="max-w-2xl w-full bg-gray-800 rounded-lg p-6 border border-red-900/50">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">
                <svg
                  className="w-8 h-8 text-red-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-xl font-semibold text-red-400 mb-2">
                  Something went wrong
                </h2>
                <p className="text-sm text-gray-300 mb-4">
                  An unexpected error occurred in the application. Please try
                  refreshing the page or contact support if the problem persists.
                </p>

                {this.state.error && (
                  <div className="mb-4">
                    <h3 className="text-sm font-medium text-gray-400 mb-2">
                      Error Details:
                    </h3>
                    <div className="bg-gray-900 rounded p-3 text-xs text-red-300 font-mono overflow-auto">
                      <div className="mb-2">
                        <strong>Message:</strong> {this.state.error.message}
                      </div>
                      {this.state.error.stack && (
                        <div className="text-gray-500 whitespace-pre-wrap">
                          {this.state.error.stack}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                <div className="flex gap-3">
                  <button
                    onClick={this.handleReset}
                    className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded transition-colors"
                  >
                    Try Again
                  </button>
                  <button
                    onClick={() => window.location.reload()}
                    className="px-4 py-2 text-sm font-medium text-gray-300 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                  >
                    Reload Page
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

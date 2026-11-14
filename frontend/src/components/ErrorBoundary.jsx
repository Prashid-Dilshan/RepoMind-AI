import { Component } from 'react';

export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('RepoMind crashed:', error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="fatal" role="alert">
        <h1 className="fatal-title">Something broke</h1>
        <p className="fatal-text">
          The page hit an unexpected error. Your indexed repositories are safe. Reload to continue.
        </p>
        <button type="button" className="btn-solid" onClick={() => window.location.reload()}>
          Reload the page
        </button>
      </div>
    );
  }
}

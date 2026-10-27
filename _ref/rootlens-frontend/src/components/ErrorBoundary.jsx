import { Component } from 'react';

// A crash inside one panel (for example a message the page cannot draw) must not blank the whole dashboard:
// show a small notice with a retry instead, and log the error for debugging.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('RootLens panel error:', error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div role="alert" className="rounded-2xl bg-warn/15 p-4 text-sm text-warn">
        <p className="font-semibold">{this.props.what ?? 'This panel'} could not be shown.</p>
        <p className="mt-1 text-xs opacity-80">{String(this.state.error?.message ?? this.state.error)}</p>
        <button type="button" onClick={() => this.setState({ error: null })} className="mt-2 rounded-full bg-warn/20 px-3 py-1 text-xs font-semibold hover:bg-warn/30">Try again</button>
      </div>
    );
  }
}

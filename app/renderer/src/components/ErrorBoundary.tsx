import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  area: string;
}

interface State {
  error: Error | null;
  stack: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, stack: "" };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[NEWXAU · ${this.props.area}]`, error, info.componentStack);
    this.setState({ stack: info.componentStack ?? "" });
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children;
    return (
      <section className="error-card" role="alert">
        <span className="eyebrow danger">View interrupted</span>
        <h2>{this.props.area} could not be rendered</h2>
        <p>The desktop shell and backend are still running. Retry this view or reload the window.</p>
        <pre>{this.state.error.message}{this.state.stack}</pre>
        <div className="button-row">
          <button className="button primary" type="button" onClick={() => this.setState({ error: null, stack: "" })}>
            Try again
          </button>
          <button className="button" type="button" onClick={() => window.location.reload()}>
            Reload window
          </button>
        </div>
      </section>
    );
  }
}

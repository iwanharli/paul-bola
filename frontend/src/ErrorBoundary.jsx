import { Component } from "react";
import { Link } from "react-router-dom";

/**
 * Catches render errors in the routed page so one broken page shows a
 * recoverable fallback instead of blanking the entire app. Keyed by route in
 * App.jsx so navigating away resets it.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // surface it in the console for debugging; the UI stays usable
    console.error("Page render error:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="state error-fallback">
          <div>
            <h2>Halaman ini bermasalah</h2>
            <p>
              Terjadi error saat menampilkan halaman ini. Bagian lain aplikasi
              tetap bisa dipakai.
            </p>
            <div className="error-actions">
              <button type="button" onClick={() => this.setState({ error: null })}>
                Coba lagi
              </button>
              <Link to="/">Kembali ke dashboard</Link>
            </div>
            <pre className="error-detail">{String(this.state.error?.message || this.state.error)}</pre>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

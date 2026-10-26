import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("ErrorBoundary caught an unhandled component error:", error, errorInfo);
  }

  private handleReset = (): void => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          data-testid="error-boundary-fallback"
          style={{
            padding: "40px 24px",
            margin: "20px 0",
            backgroundColor: "#1e293b",
            border: "1px solid #ef4444",
            borderRadius: "12px",
            textAlign: "center",
            color: "#f8fafc",
          }}
        >
          <div style={{ fontSize: "2rem", marginBottom: "12px" }}>⚠️</div>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#fca5a5", marginBottom: "8px" }}>
            Sahifada kutilmagan xatolik yuz berdi
          </h2>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8", maxWidth: "480px", margin: "0 auto 20px" }}>
            Ushbu bo'limni render qilishda texnik muammo yuz berdi. Boshqa bo'limlarga o'tishingiz yoki sahifani qayta yuklashingiz mumkin.
          </p>
          <div style={{ display: "flex", gap: "12px", justifyContent: "center" }}>
            <button
              onClick={this.handleReset}
              style={{
                padding: "8px 18px",
                backgroundColor: "#3b82f6",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontWeight: 600,
                fontSize: "0.875rem",
                cursor: "pointer",
              }}
            >
              Qayta urinish
            </button>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: "8px 18px",
                backgroundColor: "#334155",
                color: "#f8fafc",
                border: "none",
                borderRadius: "6px",
                fontSize: "0.875rem",
                cursor: "pointer",
              }}
            >
              Sahifani yangilash
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

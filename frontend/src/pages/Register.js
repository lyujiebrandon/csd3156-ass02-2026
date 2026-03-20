import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { signUp, confirmSignUp } from "../services/auth";

export default function Register() {
  const [step, setStep] = useState("register"); // "register" | "confirm"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleRegister(e) {
    e.preventDefault();
    setError("");
    if (password !== confirmPassword) {
      return setError("Passwords do not match");
    }
    setLoading(true);
    try {
      await signUp(email, password);
      setStep("confirm");
    } catch (err) {
      setError(err.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await confirmSignUp(email, code);
      navigate("/login");
    } catch (err) {
      setError(err.message || "Confirmation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">DocuMind</h1>

        {step === "register" ? (
          <>
            <p className="auth-subtitle">Create your account</p>
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={handleRegister} className="form">
              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                />
              </div>
              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min. 8 characters"
                  required
                />
              </div>
              <div className="form-group">
                <label>Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat password"
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
                {loading ? "Creating account..." : "Create Account"}
              </button>
            </form>
          </>
        ) : (
          <>
            <p className="auth-subtitle">Enter the confirmation code sent to <strong>{email}</strong></p>
            {error && <div className="alert alert-error">{error}</div>}
            <form onSubmit={handleConfirm} className="form">
              <div className="form-group">
                <label>Confirmation Code</label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="123456"
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
                {loading ? "Verifying..." : "Confirm Account"}
              </button>
            </form>
          </>
        )}

        <p className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}

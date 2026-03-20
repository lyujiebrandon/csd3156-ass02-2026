import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <Link to="/">DocuMind</Link>
      </div>
      {user && (
        <div className="navbar-links">
          <Link to="/dashboard">Dashboard</Link>
          <Link to="/upload">Upload</Link>
          <Link to="/search">Search</Link>
          <span className="navbar-email">{user.email}</span>
          <button className="btn btn-outline" onClick={handleLogout}>
            Sign Out
          </button>
        </div>
      )}
    </nav>
  );
}

import { Link, NavLink, Route, Routes } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import ReviewPage from "./pages/ReviewPage";
import OpsPage from "./pages/OpsPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">S</span>
          <span className="brand-name">SentinelAI</span>
        </Link>
        <nav className="nav">
          <NavLink to="/" end>
            Copilot
          </NavLink>
          <NavLink to="/review">Review Queue</NavLink>
          <NavLink to="/ops">Ops</NavLink>
        </nav>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/ops" element={<OpsPage />} />
        </Routes>
      </main>
    </div>
  );
}

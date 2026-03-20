import { createContext, useContext, useEffect, useState } from "react";
import { getCurrentUser, signOut } from "../services/auth";
import { connectWebSocket, disconnectWebSocket } from "../services/websocket";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCurrentUser().then((result) => {
      if (result) {
        setUser(result.session.getIdToken().payload);
        connectWebSocket();
      }
      setLoading(false);
    });
  }, []);

  function login(session) {
    setUser(session.getIdToken().payload);
    connectWebSocket();
  }

  function logout() {
    signOut();
    disconnectWebSocket();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

import { useCallback, useContext, useEffect, useRef, useState, createContext } from "react";
import { fetchMe, logoutAccount } from "../api.js";
import { clearSession, getToken, setSession, subscribeAuth } from "../auth.js";
import AuthDialog from "./AuthDialog.jsx";

const AuthContext = createContext(null);

const signedOut = {
  user: null,
  notice: "",
  openSignIn: () => {},
  signOut: async () => {},
};

export function useAuth() {
  return useContext(AuthContext) || signedOut;
}

export default function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const pending = useRef(null);

  useEffect(() => subscribeAuth((event) => {
    if (event.type !== "cleared") return;
    setUser(null);
    if (event.message) {
      setNotice(event.message);
      setDialogOpen(true);
    }
  }), []);

  useEffect(() => {
    if (!getToken()) return undefined;
    let active = true;
    fetchMe().then((result) => {
      if (active && result?.ok && result.data?.email) setUser(result.data);
    });
    return () => {
      active = false;
    };
  }, []);

  const closeSignIn = useCallback(() => {
    pending.current = null;
    setDialogOpen(false);
  }, []);

  const openSignIn = useCallback((after) => {
    pending.current = typeof after === "function" ? after : null;
    setDialogOpen(true);
  }, []);

  const completeSignIn = useCallback((session) => {
    setSession(session.token);
    setUser(session.user);
    setNotice("");
    setDialogOpen(false);
    const next = pending.current;
    pending.current = null;
    next?.(session.user);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logoutAccount();
    } finally {
      clearSession("");
      setUser(null);
      setNotice("");
      setDialogOpen(false);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, notice, openSignIn, signOut }}>
      <div inert={dialogOpen || undefined}>{children}</div>
      {notice && !dialogOpen && (
        <p role="status" className="sr-only">{notice}</p>
      )}
      <AuthDialog open={dialogOpen} notice={notice} onClose={closeSignIn} onAuthenticated={completeSignIn} />
    </AuthContext.Provider>
  );
}

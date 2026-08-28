import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext.jsx';
import { IconSparkle, IconShield, IconChart, IconGoogle } from '../components/Icons.jsx';

// Demo build: the account that "Continue with Google" falls back to.
const GOOGLE_DEFAULT = 'admin@gmail.com';

export default function Login() {
  const { login } = useApp();
  const navigate = useNavigate();
  const [email, setEmail] = useState('admin@gmail.com');
  // Shown so the form looks real; the server does not check it in this build.
  const [password, setPassword] = useState('demo1234');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const signIn = async (address) => {
    setError('');
    setBusy(true);
    try {
      const me = await login(address, password);
      // Owners land in the admin console; everyone else goes straight to Ask.
      navigate(me?.role === 'owner' ? '/admin' : '/app/ask', { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const submit = (e) => {
    e.preventDefault();
    signIn(email);
  };

  // Stands in for the OAuth round trip: uses whatever address is typed, and
  // falls back to the owner account when the field is empty.
  const withGoogle = () => signIn(email.trim() || GOOGLE_DEFAULT);

  return (
    <div className="login-page">
      <div className="login-left">
        <div className="login-box">
          <div className="brand">
            <div className="brand-mark">A</div>
            <div>
              <div className="brand-name">AskDB</div>
              <div className="brand-sub">Research preview</div>
            </div>
          </div>

          <h2>Sign in</h2>
          <p className="sub">Connect a database and ask questions in plain English.</p>

          <form className="login-form" onSubmit={submit}>
            {error && <div className="alert">{error}</div>}

            <div className="field">
              <label htmlFor="email">Work email</label>
              <input
                id="email"
                className="input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                required
              />
            </div>

            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                className="input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>

            <button className="btn btn-primary" type="submit" disabled={busy} style={{ marginTop: 4 }}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div className="login-or"><span>or</span></div>

          <button type="button" className="btn btn-google" onClick={withGoogle} disabled={busy}>
            <IconGoogle size={18} />
            Continue with Google
          </button>

        </div>
      </div>

      <div className="login-right">
        <h3>Ask your database anything, in the language you already use.</h3>
        <p>
          AskDB translates a plain English question into SQL, runs it against your
          connected database, and answers with a number, an explanation, a table and a chart.
        </p>

        <div className="col" style={{ gap: 18, marginTop: 8 }}>
          <div className="login-feature">
            <div className="ico"><IconSparkle size={16} /></div>
            <div>
              <h4>Natural language to SQL</h4>
              <p>Every answer shows the exact query that ran, so results can be checked.</p>
            </div>
          </div>
          <div className="login-feature">
            <div className="ico"><IconChart size={16} /></div>
            <div>
              <h4>Answers, not just rows</h4>
              <p>A short answer up front, then the description, table and chart behind it.</p>
            </div>
          </div>
          <div className="login-feature">
            <div className="ico"><IconShield size={16} /></div>
            <div>
              <h4>Owner-controlled access</h4>
              <p>Mask PII, hide sensitive measures and block tables from the admin panel.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

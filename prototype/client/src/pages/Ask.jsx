import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext.jsx';
import { api } from '../lib/api.js';
import AnswerCard from '../components/AnswerCard.jsx';
import { IconSend, IconCheck } from '../components/Icons.jsx';

// The local engine answers in ~20ms, which reads as "nothing happened" and
// hides the work. Hold the answer for a fixed beat and show progress.
// Wording stays in plain business language - no jargon on screen.
const THINKING_MS = 5000;
const STAGES = [
  'Reading your question',
  'Finding the right information',
  'Working through the numbers',
  'Double-checking the results',
  'Preparing your answer',
];
const STAGE_MS = THINKING_MS / STAGES.length;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function Thinking({ stage }) {
  return (
    <div className="answer thinking-card">
      <div className="thinking-stages">
        {STAGES.map((label, i) => {
          const state = i < stage ? 'done' : i === stage ? 'active' : 'todo';
          return (
            <div className={`stage stage-${state}`} key={label}>
              <span className="stage-icon">
                {state === 'done' ? <IconCheck /> : state === 'active' ? <span className="stage-spin" /> : <span className="stage-dot" />}
              </span>
              <span className="stage-label">{label}</span>
            </div>
          );
        })}
      </div>
      <div className="thinking-bar">
        <span style={{ animationDuration: `${THINKING_MS}ms` }} />
      </div>
    </div>
  );
}

export default function Ask() {
  const { connection, connectionId, toast } = useApp();
  const location = useLocation();
  const [question, setQuestion] = useState('');
  const [thread, setThread] = useState([]);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [suggestions, setSuggestions] = useState([]);
  const threadRef = useRef(null);
  const inputRef = useRef(null);
  const timersRef = useRef([]);

  // Never leave stage timers running behind an unmounted page.
  useEffect(() => () => timersRef.current.forEach(clearTimeout), []);

  useEffect(() => {
    if (!connectionId) return;
    api.suggestions(connectionId)
      .then((d) => setSuggestions(d.examples || []))
      .catch(() => setSuggestions([]));
  }, [connectionId]);

  // Clear the thread when the user switches database.
  useEffect(() => { setThread([]); }, [connectionId]);

  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [thread, busy]);

  // A question handed over from History or Overview.
  useEffect(() => {
    if (location.state?.question) {
      run(location.state.question);
      window.history.replaceState({}, '');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  async function run(text) {
    const q = String(text || '').trim();
    if (!q || busy) return;

    setThread((t) => [...t, { role: 'user', text: q }]);
    setQuestion('');
    setBusy(true);
    setStage(0);

    // Advance the visible stage on a timer while the request runs underneath.
    timersRef.current.forEach(clearTimeout);
    timersRef.current = STAGES.slice(0, -1).map((_, i) =>
      setTimeout(() => setStage(i + 1), (i + 1) * STAGE_MS)
    );

    try {
      // Whichever takes longer wins: a slow query is never cut short, and a
      // fast one still shows the full animation.
      const [result] = await Promise.all([api.ask(q, connectionId), sleep(THINKING_MS)]);
      setThread((t) => [...t, { role: 'answer', result, question: q }]);
    } catch (err) {
      toast(err.message, 'err');
      setThread((t) => [...t, {
        role: 'answer',
        question: q,
        result: {
          status: 'error',
          answer: { headline: 'Request failed', subline: 'The server could not answer', description: err.message, insights: [] },
          chart: { type: 'empty' }, rows: [], columns: [], steps: [], confidence: 0, executionMs: 0, followUps: [],
        },
      }]);
    } finally {
      timersRef.current.forEach(clearTimeout);
      timersRef.current = [];
      setBusy(false);
      setStage(0);
      inputRef.current?.focus();
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      run(question);
    }
  };

  const empty = thread.length === 0;

  // One composer, rendered in two places: centred on the empty screen, docked
  // to the bottom once there is a conversation to scroll through.
  const composer = (
    <div className="composer">
      <div className="composer-box">
        <textarea
          ref={inputRef}
          rows={1}
          value={question}
          placeholder={`Ask about ${connection?.name || 'your data'}…`}
          onChange={(e) => {
            setQuestion(e.target.value);
            e.target.style.height = 'auto';
            e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
          }}
          onKeyDown={onKeyDown}
          disabled={busy}
        />
        <button
          className="send-btn"
          onClick={() => run(question)}
          disabled={busy || !question.trim()}
          aria-label="Ask"
        >
          <IconSend />
        </button>
      </div>
    </div>
  );

  // Empty state: hero, search bar and suggestions as one centred block.
  if (empty) {
    return (
      <div className="ask-page">
        <div className="ask-center">
          <div className="ask-hero">
            <div className="mark">A</div>
            <h2>Ask {connection?.name || 'your database'} a question</h2>
            <p>
              Questions are translated to SQL and run against the live connection.
              Every answer shows the query behind it.
            </p>
          </div>
          {composer}
          <div className="suggestions">
            {suggestions.map((s) => (
              <button className="chip" key={s} onClick={() => run(s)}>{s}</button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="ask-page">
      <div className="thread" ref={threadRef}>
        <div className="thread-inner">
          {thread.map((item, i) =>
            item.role === 'user' ? (
              <div className="bubble-q" key={i}>{item.text}</div>
            ) : (
              <AnswerCard
                key={i}
                result={item.result}
                onFollowUp={run}
                onRerun={() => run(item.question)}
              />
            )
          )}

          {busy && <Thinking stage={stage} />}
        </div>
      </div>

      <div className="composer-wrap">{composer}</div>
    </div>
  );
}

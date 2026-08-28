import express from 'express';
import cors from 'cors';
import morgan from 'morgan';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import routes from './routes/index.js';
import { warmUp } from './engine/executor.js';
import { seedActivity } from './store.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 4000;

app.use(cors());
app.use(express.json({ limit: '1mb' }));
app.use(morgan('dev'));

app.get('/api/health', (_req, res) => {
  res.json({ ok: true, service: 'askdb-server', time: new Date().toISOString() });
});

app.use('/api', routes);

// In production the built client is served from the same origin.
const clientDist = path.join(__dirname, '..', '..', 'client', 'dist');
app.use(express.static(clientDist));
app.get(/^(?!\/api).*/, (_req, res) => {
  res.sendFile(path.join(clientDist, 'index.html'), (err) => {
    if (err) res.status(404).json({ error: 'Client build not found. Run npm run build.' });
  });
});

app.use((err, _req, res, _next) => {
  console.error(err);
  res.status(500).json({ error: err.message || 'Unexpected server error' });
});

seedActivity();
warmUp();

app.listen(PORT, () => {
  console.log(`\n  AskDB API listening on http://localhost:${PORT}`);
  console.log(`  Demo logins (no password checked): admin@gmail.com / vonara@gmail.com\n`);
});

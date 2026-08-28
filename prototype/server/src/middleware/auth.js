import crypto from 'node:crypto';
import { USERS } from '../store.js';

// ---------------------------------------------------------------------------
// Demo authentication: a signed, stateless token in the same shape as a JWT.
// It is deliberately simple - real deployments should use proper JWTs with
// rotation and short expiry.
// ---------------------------------------------------------------------------

const SECRET = process.env.ASKDB_SECRET || 'askdb-demo-secret';
const b64 = (obj) => Buffer.from(JSON.stringify(obj)).toString('base64url');
const sign = (payload) => crypto.createHmac('sha256', SECRET).update(payload).digest('base64url');

export function issueToken(user) {
  const payload = b64({ sub: user.id, email: user.email, role: user.role, iat: Date.now() });
  return `${payload}.${sign(payload)}`;
}

export function verifyToken(token) {
  if (!token || !token.includes('.')) return null;
  const [payload, signature] = token.split('.');
  if (sign(payload) !== signature) return null;
  try {
    const claims = JSON.parse(Buffer.from(payload, 'base64url').toString());
    return USERS.find((u) => u.id === claims.sub) || null;
  } catch {
    return null;
  }
}

export function requireAuth(req, res, next) {
  const header = req.headers.authorization || '';
  const user = verifyToken(header.replace(/^Bearer\s+/i, ''));
  if (!user) return res.status(401).json({ error: 'Not authenticated' });
  req.user = user;
  next();
}

// Owners may change settings; viewers may not.
export function requireOwner(req, res, next) {
  if (!req.user || req.user.role !== 'owner') {
    return res.status(403).json({ error: 'Only workspace owners can change this setting.' });
  }
  next();
}

export const publicUser = (user) => ({
  id: user.id,
  name: user.name,
  email: user.email,
  role: user.role,
  initials: user.initials,
  avatarUrl: user.avatarUrl,
  lastActive: user.lastActive,
});

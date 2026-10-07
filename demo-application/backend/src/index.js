const express = require('express');
const cors = require('cors');
const authorizationContext = require('./config/authorizationContext.json');
const demoUsers = require('./config/demoUsers.json');
const { getPolicyForRole } = require('./services/policyService');
const { resolvePolicyValues } = require('./utils/resolvePolicyValues');
const { createGenerationContract } = require('./services/generationContract');
const { generateSql } = require('./services/fakeSqlGenerator');
const { inspectSql, SqlInspectionError } = require('./security/sql/sqlInspector');
const { evaluateSqlSecurity } = require('./security/sql/securityEvaluator');

function createEffectivePolicy(context) {
  if (!context || typeof context !== 'object' || Array.isArray(context)) {
    throw new Error('A valid authorization context is required.');
  }
  if (!context.role) {
    throw new Error('Authorization context must contain a "role" field.');
  }

  return resolvePolicyValues(getPolicyForRole(context.role), context);
}

function validateVerificationRequest(body) {
  const { policy, user, sql, dialect = 'mysql' } = body || {};

  if (!policy || typeof policy !== 'object' || Array.isArray(policy)) {
    return { error: 'Policy must be a JSON object.' };
  }
  if (!Array.isArray(policy.allowedTables)) {
    return { error: 'Policy must include an allowedTables array.' };
  }
  if (!user || typeof user !== 'object' || Array.isArray(user)) {
    return { error: 'Authenticated user must be a JSON object.' };
  }
  if (!sql || typeof sql !== 'string' || !sql.trim()) {
    return { error: 'SQL must be a non-empty string.' };
  }
  if (typeof dialect !== 'string' || !dialect.trim()) {
    return { error: 'Dialect must be a non-empty string.' };
  }

  return {
    value: {
      policy,
      user,
      sql: sql.trim(),
      dialect: dialect.trim()
    }
  };
}

async function verifySql({ policy, user, sql, dialect = 'mysql' }) {
  const analysis = await inspectSql(sql, dialect);
  return evaluateSqlSecurity(analysis, policy, user);
}

function createApp() {
  const app = express();
  app.use(cors());
  app.use(express.json({ limit: '256kb' }));

  app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', service: 'policy-verification-backend' });
  });

  app.get('/api/users', (req, res) => {
    res.json(demoUsers);
  });

  app.get('/api/user-policy/:userId', (req, res) => {
    try {
      const user = demoUsers.find((item) => item.userId === req.params.userId)
        || authorizationContext;
      res.json({ user, effectivePolicy: createEffectivePolicy(user) });
    } catch (error) {
      res.status(400).json({
        code: 'POLICY_RESOLUTION_FAILED',
        message: error.message
      });
    }
  });

  app.post('/api/verify-sql', async (req, res) => {
    const validation = validateVerificationRequest(req.body);
    if (validation.error) {
      return res.status(400).json({
        code: 'INVALID_REQUEST',
        message: validation.error
      });
    }

    try {
      const result = await verifySql(validation.value);
      return res.json(result);
    } catch (error) {
      if (error instanceof SqlInspectionError) {
        return res.status(error.status).json({
          code: error.code,
          message: error.message
        });
      }

      console.error('SQL verification failed:', error);
      return res.status(500).json({
        code: 'VERIFICATION_FAILED',
        message: 'The backend could not complete SQL verification.'
      });
    }
  });

  // Compatibility endpoint for the original predefined-user demo.
  app.post('/api/check-sql', async (req, res) => {
    const user = demoUsers.find((item) => item.userId === req.body?.userId)
      || authorizationContext;
    const policy = createEffectivePolicy(user);
    const validation = validateVerificationRequest({
      policy,
      user,
      sql: req.body?.sql,
      dialect: req.body?.dialect
    });

    if (validation.error) {
      return res.status(400).json({ code: 'INVALID_REQUEST', message: validation.error });
    }

    try {
      return res.json(await verifySql(validation.value));
    } catch (error) {
      const status = error instanceof SqlInspectionError ? error.status : 500;
      return res.status(status).json({
        code: error.code || 'VERIFICATION_FAILED',
        message: error.message || 'The backend could not complete SQL verification.'
      });
    }
  });

  app.post('/api/query', async (req, res) => {
    try {
      const user = demoUsers.find((item) => item.userId === req.body?.userId)
        || authorizationContext;
      const policy = createEffectivePolicy(user);
      const question = req.body?.question || 'Show employee names';
      const contract = createGenerationContract(policy, question);

      if (contract.status === 'BLOCKED') {
        return res.status(403).json({
          stage: 'PRE_GENERATION',
          decision: 'FAIL',
          reason: contract.reason
        });
      }

      const sql = generateSql(question, contract);
      const securityCheck = await verifySql({ policy, user, sql });
      return res.json({ question, contract, sql, securityCheck });
    } catch (error) {
      const status = error instanceof SqlInspectionError ? error.status : 500;
      return res.status(status).json({
        code: error.code || 'QUERY_PIPELINE_FAILED',
        message: error.message || 'The query pipeline failed.'
      });
    }
  });

  return app;
}

const app = createApp();
let server = null;

if (require.main === module) {
  const port = Number(process.env.PORT) || 5000;
  server = app.listen(port, () => {
    console.log(`Policy verification backend running on http://localhost:${port}`);
  });
}

module.exports = {
  app,
  server,
  createApp,
  createEffectivePolicy,
  validateVerificationRequest,
  verifySql
};

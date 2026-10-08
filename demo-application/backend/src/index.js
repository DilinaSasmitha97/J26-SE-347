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
const {
  SecureQueryError,
  validateWithSecurityLayer,
  translateQuestion,
  executeAndMask,
  getSecurityRuntimeHealth
} = require('./services/secureQueryService');

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
  const validation = validateWithSecurityLayer(sql, policy);
  const validationCheck = {
    label: 'Navodya AST safety',
    passed: validation.safe,
    status: validation.safe ? 'PASS' : 'FAIL',
    reason: validation.safe ? null : 'SECURITY_LAYER_REJECTED',
    message: validation.safe
      ? `${validation.statementType} passed dangerous-query and schema-allowlist validation.`
      : validation.violations.map((item) => `${item.type}: ${item.detail}`).join('; ')
  };

  if (!validation.safe) {
    return {
      passed: false,
      decision: 'FAIL',
      message: 'Query was stopped by the security validation layer.',
      checks: [validationCheck],
      securityValidation: validation,
      context: {
        policyId: policy.policyId || 'Unnamed policy',
        userId: user.userId || user.sub || 'Unknown user',
        role: user.role || 'Unspecified',
        tables: [],
        columns: [],
        normalizedSql: ''
      }
    };
  }

  const analysis = await inspectSql(sql, dialect);
  const policyResult = evaluateSqlSecurity(analysis, policy, user);
  return {
    ...policyResult,
    checks: [validationCheck, ...policyResult.checks],
    securityValidation: validation,
    inspection: analysis
  };
}

function createApp() {
  const app = express();
  app.use(cors());
  app.use(express.json({ limit: '256kb' }));

  app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', service: 'policy-verification-backend' });
  });

  app.get('/api/security-health', async (req, res) => {
    const runtime = await getSecurityRuntimeHealth();
    res.json({
      status: runtime.database.status === 'ok' && runtime.ner.status === 'ok' ? 'ok' : 'degraded',
      service: 'integrated-security-pipeline',
      components: {
        navodyaValidation: { status: 'ok', mode: 'in-process' },
        database: runtime.database,
        ner: runtime.ner
      }
    });
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

  app.post('/api/generate-sql', async (req, res) => {
    const started = Date.now();
    const user = demoUsers.find((item) => item.userId === req.body?.userId);
    if (!user) {
      return res.status(400).json({
        code: 'UNKNOWN_USER',
        message: 'Choose a valid demo user. The backend does not trust client-supplied roles or policies.'
      });
    }

    const question = typeof req.body?.question === 'string' ? req.body.question.trim() : '';
    if (!question || question.length > 2000) {
      return res.status(400).json({
        code: 'INVALID_REQUEST',
        message: 'Provide a natural-language question of up to 2000 characters.'
      });
    }

    try {
      const effectivePolicy = createEffectivePolicy(user);
      const generation = await translateQuestion(question, effectivePolicy);
      return res.json({
        status: 'GENERATED',
        question,
        user,
        effectivePolicy,
        generation,
        sql: generation.sql,
        elapsedMs: Date.now() - started
      });
    } catch (error) {
      if (error instanceof SecureQueryError) {
        return res.status(error.status || 500).json({
          code: error.code,
          message: error.message,
          details: error.details || null
        });
      }
      console.error('SQL generation failed:', error);
      return res.status(500).json({
        code: 'SQL_GENERATION_FAILED',
        message: 'The backend could not generate SQL.'
      });
    }
  });

  app.post('/api/secure-query', async (req, res) => {
    const started = Date.now();
    const requestedUserId = req.body?.userId;
    const user = demoUsers.find((item) => item.userId === requestedUserId);

    if (!user) {
      return res.status(400).json({
        code: 'UNKNOWN_USER',
        message: 'Choose a valid demo user. The backend does not trust client-supplied roles or policies.'
      });
    }

    const suppliedSql = typeof req.body?.sql === 'string' ? req.body.sql.trim() : '';
    const question = typeof req.body?.question === 'string' ? req.body.question.trim() : '';
    if (!suppliedSql && !question) {
      return res.status(400).json({
        code: 'INVALID_REQUEST',
        message: 'Provide either a natural-language question or SQL to validate.'
      });
    }

    try {
      const effectivePolicy = createEffectivePolicy(user);
      const generation = suppliedSql ? null : await translateQuestion(question, effectivePolicy);
      const sql = suppliedSql || generation.sql;
      const decision = await verifySql({ policy: effectivePolicy, user, sql, dialect: 'mysql' });
      const baseResponse = {
        status: decision.passed ? 'APPROVED' : 'BLOCKED',
        source: suppliedSql ? 'provided_sql' : 'nl_to_sql',
        question: question || null,
        user,
        effectivePolicy,
        generation,
        sql,
        securityValidation: decision.securityValidation,
        inspection: decision.inspection || null,
        decision,
        tenantRewrite: { applied: false, reason: 'Skipped in this integration phase.' },
        elapsedMs: Date.now() - started
      };

      if (!decision.passed || req.body?.execute !== true) {
        return res.json(baseResponse);
      }

      try {
        const result = await executeAndMask(sql, effectivePolicy, user);
        return res.json({
          ...baseResponse,
          status: 'COMPLETED',
          result,
          elapsedMs: Date.now() - started
        });
      } catch (error) {
        if (!(error instanceof SecureQueryError)) throw error;
        return res.json({
          ...baseResponse,
          status: 'EXECUTION_FAILED',
          executionError: {
            code: error.code,
            message: error.message,
            details: error.details || null
          },
          elapsedMs: Date.now() - started
        });
      }
    } catch (error) {
      if (error instanceof SqlInspectionError || error instanceof SecureQueryError) {
        return res.status(error.status || 500).json({
          code: error.code,
          message: error.message,
          details: error.details || null
        });
      }
      console.error('Secure query pipeline failed:', error);
      return res.status(500).json({
        code: 'SECURE_QUERY_FAILED',
        message: 'The secure query pipeline could not complete.'
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

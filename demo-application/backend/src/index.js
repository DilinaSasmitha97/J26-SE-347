const express = require('express');
const cors = require('cors');
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
const presentationService = require('./services/presentationService');
const intentClassificationService = require('./services/intentClassificationService');
const { createResultStore } = require('./services/resultStore');

function createEffectivePolicy(context, policy) {
  if (!context || typeof context !== 'object' || Array.isArray(context)) {
    throw new Error('A valid authorization context is required.');
  }
  if (typeof context.role !== 'string' || !context.role.trim()) {
    throw new Error('Authorization context must contain a "role" field.');
  }

  if (!policy || typeof policy !== 'object' || Array.isArray(policy) || !Array.isArray(policy.allowedTables)) {
    throw new Error('Paste a policy JSON object containing an allowedTables array.');
  }
  return resolvePolicyValues(policy, context);
}

function validateContextRequest(body) {
  const { user, policy, rules } = body || {};
  if (!user || typeof user !== 'object' || Array.isArray(user)) return { error: 'Paste the authenticated user JSON object.' };
  if (typeof user.userId !== 'string' || !user.userId.trim()) return { error: 'Authenticated user must contain a non-empty userId.' };
  if (!policy || typeof policy !== 'object' || Array.isArray(policy)) return { error: 'Paste the user policy JSON object.' };
  if (!Array.isArray(policy.allowedTables) || policy.allowedTables.some((table) => typeof table !== 'string' || !table.trim())) return { error: 'Policy allowedTables must be an array of table names.' };
  for (const key of ['deniedColumns', 'allowedOperations']) {
    if (policy[key] !== undefined && (!Array.isArray(policy[key]) || policy[key].some((item) => typeof item !== 'string'))) return { error: `Policy ${key} must be an array of strings.` };
  }
  if (rules != null && (typeof rules !== 'object' || Array.isArray(rules))) return { error: 'NL-to-SQL rules must be a JSON object when provided.' };
  try {
    return { value: { user: structuredClone(user), effectivePolicy: createEffectivePolicy(user, policy), rules: rules || null } };
  } catch (error) {
    return { error: error.message };
  }
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
  const validation = validateWithSecurityLayer(sql);
  const validationCheck = {
    label: 'SQL safety (AST) check',
    passed: validation.safe,
    status: validation.safe ? 'PASS' : 'FAIL',
    reason: validation.safe ? null : 'SECURITY_LAYER_REJECTED',
    message: validation.safe
      ? `${validation.statementType} passed SQL safety validation.`
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
  const policyResult = evaluateSqlSecurity(analysis, policy, user, sql);
  return {
    ...policyResult,
    checks: [validationCheck, ...policyResult.checks],
    securityValidation: validation,
    inspection: analysis
  };
}

function createApp(dependencies = {}) {
  const app = express();
  const presenter = dependencies.presentationService || presentationService;
  const classifier = dependencies.intentClassificationService || intentClassificationService;
  const runMaskedQuery = dependencies.executeAndMask || executeAndMask;
  const verifyQuery = dependencies.verifySql || verifySql;
  const resultStore = dependencies.resultStore || createResultStore();
  app.use(cors());
  app.use(express.json({ limit: '256kb' }));

  app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', service: 'policy-verification-backend' });
  });

  app.get('/api/security-health', async (req, res) => {
    const [runtime, presentation] = await Promise.all([getSecurityRuntimeHealth(), presenter.presentationHealth()]);
    res.json({
      status: runtime.database.status === 'ok' && runtime.ner.status === 'ok' ? 'ok' : 'degraded',
      service: 'integrated-security-pipeline',
      components: {
        navodyaValidation: { status: 'ok', mode: 'in-process' },
        database: runtime.database,
        ner: runtime.ner,
        presentation
      }
    });
  });

  app.get('/api/presentation-health', async (req, res) => {
    res.json(await presenter.presentationHealth());
  });

  app.post('/api/simulate', async (req, res) => {
    const context = validateContextRequest(req.body);
    if (context.error) return res.status(400).json({ code: 'INVALID_REQUEST', message: context.error });
    const { user, effectivePolicy: policy } = context.value;
    const scenarioText = typeof req.body?.scenarioText === 'string' ? req.body.scenarioText.trim() : '';
    if (typeof req.body?.resultId !== 'string' || !scenarioText || scenarioText.length > 1000) {
      return res.status(400).json({ code: 'INVALID_REQUEST', message: 'Provide a resultId and a scenario of up to 1000 characters.' });
    }
    const entry = resultStore.get(req.body.resultId, user, policy);
    if (!entry) return res.status(404).json({ code: 'RESULT_UNAVAILABLE', message: 'This result expired or is unavailable for the current user and policy. Execute the query again.' });
    try {
      return res.json(await presenter.simulateResult(entry, scenarioText, user, policy));
    } catch (error) {
      return res.status(error.status || 502).json({ code: error.code || 'SIMULATION_FAILED', message: error.message });
    }
  });

  // Data presentation layer. Renders the masked result the gateway stored for
  // this user and policy, in the formats the intent classification recommended.
  app.post('/api/present-result', async (req, res) => {
    const context = validateContextRequest(req.body);
    if (context.error) return res.status(400).json({ code: 'INVALID_REQUEST', message: context.error });
    const { user, effectivePolicy: policy } = context.value;
    if (typeof req.body?.resultId !== 'string') {
      return res.status(400).json({ code: 'INVALID_REQUEST', message: 'Provide the resultId of an executed query.' });
    }
    const classification = req.body?.classification ?? null;
    if (classification !== null) {
      const problem = intentClassificationService.classificationChoiceProblem(classification);
      if (problem) return res.status(400).json({ code: 'INVALID_REQUEST', message: `Invalid classification: ${problem}.` });
    }
    const entry = resultStore.get(req.body.resultId, user, policy);
    if (!entry) return res.status(404).json({ code: 'RESULT_UNAVAILABLE', message: 'This result expired or is unavailable for the current user and policy. Execute the query again.' });
    try {
      return res.json(await presenter.renderResult(entry, classification && {
        intent: classification.intent, presentation_types: [...classification.presentation_types]
      }));
    } catch (error) {
      return res.status(error.status || 502).json({ code: error.code || 'PRESENTATION_FAILED', message: error.message });
    }
  });

  // Prediction layer. Forecast (prediction_needed) or anomaly detection
  // (ANOMALY_DETECTION) over the masked result stored for this user and policy.
  app.post('/api/predict-result', async (req, res) => {
    const context = validateContextRequest(req.body);
    if (context.error) return res.status(400).json({ code: 'INVALID_REQUEST', message: context.error });
    const { user, effectivePolicy: policy } = context.value;
    if (typeof req.body?.resultId !== 'string') {
      return res.status(400).json({ code: 'INVALID_REQUEST', message: 'Provide the resultId of an executed query.' });
    }
    const classification = req.body?.classification;
    const problem = intentClassificationService.classificationChoiceProblem(classification)
      || (typeof classification?.prediction_needed !== 'boolean' ? 'classification.prediction_needed must be a Boolean' : null);
    if (problem) return res.status(400).json({ code: 'INVALID_REQUEST', message: `Invalid classification: ${problem}.` });
    if (!classification.prediction_needed && classification.intent !== 'ANOMALY_DETECTION') {
      return res.status(400).json({ code: 'PREDICTION_NOT_REQUESTED', message: 'This question asks for neither a forecast nor anomaly detection.' });
    }
    const entry = resultStore.get(req.body.resultId, user, policy);
    if (!entry) return res.status(404).json({ code: 'RESULT_UNAVAILABLE', message: 'This result expired or is unavailable for the current user and policy. Execute the query again.' });
    try {
      return res.json(await presenter.predictResult(entry, {
        intent: classification.intent, prediction_needed: classification.prediction_needed
      }));
    } catch (error) {
      return res.status(error.status || 502).json({ code: error.code || 'PREDICTION_FAILED', message: error.message });
    }
  });

  app.get('/api/users', (req, res) => {
    res.json([]);
  });

  app.get('/api/user-policy/:userId', (req, res) => {
    res.status(400).json({ code: 'MANUAL_CONTEXT_REQUIRED', message: 'Paste the user and policy JSON in the application. Stored policy lookup is disabled.' });
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

  // Classification reads only the question. It needs no user, policy or rules,
  // and its result is never added to the SQL-generation request.
  app.post('/api/classify-intent', async (req, res) => {
    const request = intentClassificationService.validateClassificationRequest(req.body);
    if (request.error) return res.status(400).json({ code: 'INVALID_REQUEST', message: request.error });

    // Abort the upstream call when the browser cancels a superseded question.
    const disconnected = new AbortController();
    res.on('close', () => { if (!res.writableFinished) disconnected.abort(); });

    try {
      return res.json(await classifier.classifyIntent(request.value, { signal: disconnected.signal }));
    } catch (error) {
      if (disconnected.signal.aborted) return undefined;
      console.error('Intent classification failed:', error.code || '', error.message);
      return res.status(error.status || 502).json({
        code: error.code || 'CLASSIFICATION_FAILED',
        message: error.message || 'The question could not be classified.'
      });
    }
  });

  app.post('/api/generate-sql', async (req, res) => {
    const started = Date.now();
    const context = validateContextRequest(req.body);
    if (context.error) return res.status(400).json({ code: 'INVALID_REQUEST', message: context.error });
    const { user, effectivePolicy, rules } = context.value;

    const question = typeof req.body?.question === 'string' ? req.body.question.trim() : '';
    if (!question || question.length > 2000) {
      return res.status(400).json({
        code: 'INVALID_REQUEST',
        message: 'Provide a natural-language question of up to 2000 characters.'
      });
    }

    try {
      // Intent was classified in its own step (/api/classify-intent); generation
      // neither repeats it nor returns a result that could replace it.
      const generation = await translateQuestion(question, rules);
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
    const context = validateContextRequest(req.body);
    if (context.error) return res.status(400).json({ code: 'INVALID_REQUEST', message: context.error });
    const { user, effectivePolicy, rules } = context.value;

    const suppliedSql = typeof req.body?.sql === 'string' ? req.body.sql.trim() : '';
    const question = typeof req.body?.question === 'string' ? req.body.question.trim() : '';
    if ((!suppliedSql && !question) || question.length > 2000) {
      return res.status(400).json({
        code: 'INVALID_REQUEST',
        message: 'Provide SQL or a natural-language question of up to 2000 characters.'
      });
    }

    try {
      const understanding = suppliedSql ? {} : await presenter.analyzeQuestion(question, user, effectivePolicy);
      if (understanding.analysis?.response_intent?.is_data_request === false) {
        return res.status(400).json({ code: 'NOT_A_DATA_REQUEST', message: 'Ask a question about the data.', ...understanding });
      }
      const generation = suppliedSql ? null : await translateQuestion(question, rules);
      const sql = suppliedSql || generation.sql;
      const decision = await verifyQuery({ policy: effectivePolicy, user, sql, dialect: 'mysql' });
      const baseResponse = {
        status: decision.passed ? 'APPROVED' : 'BLOCKED',
        source: suppliedSql ? 'provided_sql' : 'nl_to_sql',
        question: question || null,
        user,
        effectivePolicy,
        generation,
        ...understanding,
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
        const result = await runMaskedQuery(sql, effectivePolicy, user);
        // Prediction is off by default; results are shown through /api/present-result.
        const predicting = presenter.predictionEnabled ? presenter.predictionEnabled() : true;
        const presentation = predicting
          ? await presenter.presentResult(question, result, user, effectivePolicy)
          : { presentation: null, presentationStatus: 'SKIPPED' };
        const resultId = question ? resultStore.save({ user, policy: effectivePolicy, question, result }) : null;
        return res.json({
          ...baseResponse,
          status: 'COMPLETED',
          result,
          resultId,
          ...presentation,
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

  // Compatibility endpoints also require explicit user and policy inputs.
  app.post('/api/check-sql', async (req, res) => {
    const context = validateContextRequest(req.body);
    if (context.error) return res.status(400).json({ code: 'INVALID_REQUEST', message: context.error });
    const { user, effectivePolicy: policy } = context.value;
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
    const context = validateContextRequest(req.body);
    if (context.error) return res.status(400).json({ code: 'INVALID_REQUEST', message: context.error });
    try {
      const { user, effectivePolicy: policy } = context.value;
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
  validateContextRequest,
  validateVerificationRequest,
  verifySql
};

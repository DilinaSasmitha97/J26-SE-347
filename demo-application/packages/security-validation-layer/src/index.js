'use strict';

const fs = require('fs');
const path = require('path');

function loadBundledConfig(name) {
  if (!/^[a-z0-9_-]+\.json$/i.test(name)) {
    throw new Error(`Invalid bundled config name: ${name}`);
  }
  return JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'config', name), 'utf8'));
}

module.exports = {
  ...require('./security-middleware'),
  ...require('./query-executor'),
  ...require('./controlled-write'),
  ...require('./pii-classifier'),
  ...require('./pii-ner'),
  ...require('./masking-policy'),
  ...require('./pii-fpe'),
  loadBundledConfig,
};

const {
    checkTenantSql,
} = require("./tenantSqlChecker");

const result = checkTenantSql(
    101,
    `
  SELECT *
  FROM customers
  WHERE tenant_id = 101
  `
);

console.log(result);
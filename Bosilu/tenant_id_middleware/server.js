const express = require("express");
const path = require("path");

const {
    checkTenantSql,
} = require("./tenantSqlChecker");

const app = express();

const PORT = 3000;

// Allow JSON requests
app.use(express.json());

// Serve frontend
app.use(express.static(
    path.join(__dirname, "public")
));

// API
app.post("/api/check", (req, res) => {
    try {
        const {
            tenantId,
            sqlQuery,
        } = req.body;

        if (!tenantId) {
            return res.status(400).json({
                pass: false,
                verdict: "FAIL",
                code: "TENANT_ID_REQUIRED",
                reason: "Tenant ID is required.",
            });
        }

        if (!sqlQuery) {
            return res.status(400).json({
                pass: false,
                verdict: "FAIL",
                code: "SQL_REQUIRED",
                reason: "SQL query is required.",
            });
        }

        const result = checkTenantSql(
            tenantId,
            sqlQuery
        );

        res.json(result);

    } catch (error) {

        console.error(error);

        res.status(500).json({
            pass: false,
            verdict: "FAIL",
            code: "SERVER_ERROR",
            reason: error.message,
        });
    }
});

app.listen(PORT, () => {
    console.log(
        `Server running at http://localhost:${PORT}`
    );
});
# Secure Multi-Tenant Natural Language Interface for Database Querying
## Policy-Model Prototype (Phase 1)

A lightweight Node.js + Express starter project demonstrating the foundational policy-grounding model for a secure multi-tenant Natural Language Interface to Database (NLIDB) system.

---

### 1. What This Project Does

In a multi-tenant natural language query system, users generate analytical database queries using natural language. To enforce tenant isolation and role-based access control (RBAC), security constraints must be applied before and during query execution.

This prototype validates the initial policy resolution stage:
1. Loads an **Authorization Context** representing the authenticated tenant and user.
2. Identifies the user's **Role** (e.g., `MANAGER`, `EMPLOYEE`).
3. Loads the matching **Security Policy** defining allowed tables, denied columns, and row-level rules.
4. Resolves dynamic context parameters (`valueFrom` placeholders like `tenantId`, `departmentId`, `userId`) into an **Effective Policy**.
5. Builds a **Generation Contract** binding user questions to allowed tables, restricted columns, and mandatory row filters.
6. Runs a **Fake NL-to-SQL Generator** to produce grounded SQL queries.
7. Executes **Post-Generation SQL Security Checking** evaluating queries for prohibited columns and missing tenant filters with `ALLOW / REWRITE / DENY` decisions.

```
Mock Authorization Context
         ↓
       Role
         ↓
 Load Matching Policy
         ↓
Resolve tenantId / departmentId
         ↓
  Effective Policy
         ↓
User Natural Language Question
         ↓
Pre-Generation Contract (Allowed Tables, Denied Columns, Required Filters)
         ↓
Fake SQL Generator
         ↓
Generated SQL Query
         ↓
Post-Generation Security Validator
   ├── ALLOW   → Query satisfies all tenant and column constraints
   ├── REWRITE → Automatically injects missing tenant/department filters
   └── DENY    → Prohibited columns (e.g., salary) or unauthorized tables detected
```

---

### 2. Project Structure

```
secure-policy-prototype/
├── package.json
├── src/
│   ├── index.js                     # Main Express backend & demo runner (port 5000)
│   ├── config/
│   │   ├── authorizationContext.json # Default mock authenticated user context
│   │   ├── demoUsers.json           # Predefined demo personas (Manager A/B, Employee A/B)
│   │   └── request.json             # Sample query request
│   ├── policies/
│   │   ├── managerPolicy.json       # Manager policy template
│   │   └── employeePolicy.json       # Employee policy template
│   ├── services/
│   │   ├── policyService.js         # Role-to-policy resolution service
│   │   ├── checkAccess.js           # Access check & filter collector
│   │   ├── generationContract.js    # Pre-generation policy contract builder
│   │   ├── fakeSqlGenerator.js      # Deterministic NL-to-SQL generator
│   │   └── postGenValidator.js      # Filter rewriting utility
│   ├── sqlSecurity/
│   │   ├── tenantChecker.js         # 1. Tenant isolation security check
│   │   ├── rowFilterChecker.js      # 2. Extra row-level filter check
│   │   ├── tableColumnChecker.js    # 3. Table authorization & blocked column check
│   │   └── sqlSecurityChecker.js    # Composite 3-tier security checker
│   └── utils/
│       └── resolvePolicyValues.js   # Dynamic context value resolution utility
├── frontend/
│   ├── package.json                 # Frontend dependencies (React + Vite)
│   ├── vite.config.js               # Vite config with backend proxy (port 3000 -> 5000)
│   ├── index.html                   # Entry HTML
│   └── src/
│       ├── components/
│       │   ├── UserSelector.jsx     # Initial fake login screen
│       │   ├── UserDetails.jsx      # Section 1: Active persona details & Switch User
│       │   ├── PolicyViewer.jsx     # Section 2: Human-readable effective policy & raw JSON
│       │   ├── SqlInput.jsx         # Section 3: SQL input & dynamic quick test buttons
│       │   └── SecurityResult.jsx   # Results UI: 3-tier PASS/FAIL badges & final ALLOW/DENY
│       ├── App.jsx                  # Main dashboard layout
│       ├── main.jsx                 # React root mount
│       └── index.css                # Visual theme styling
└── README.md
```

---

### 3. Installation

1. Install backend dependencies (in root):
```bash
npm install
```

2. Install frontend dependencies (in `frontend/`):
```bash
cd frontend && npm install && cd ..
```

---

### 4. Running the Demonstration

#### Option A: Run Full Web Demonstration (Backend + React Frontend)

**Terminal 1 — Start the Backend API Server (Port 5000):**
```bash
npm start
```
*(Runs CLI self-checks and starts HTTP API on `http://localhost:5000`)*

**Terminal 2 — Start the React Web Interface (Port 3000):**
```bash
npm run frontend
```
*(Opens Vite development server on `http://localhost:3000`)*

#### Option B: Standalone CLI Check
```bash
npm start
```

#### Optional: Run as Express Server
To expose the `/api/effective-policy` endpoint via Express:
```bash
PORT=3000 npm start
```

---

### 5. Architectural Roadmap & Future Integrations

This prototype is intentionally focused on the policy resolution stage. Subsequent phases will integrate:

1. **JWT / JWKS Validation**:
   - The current `src/config/authorizationContext.json` mock will be replaced by an authentication middleware that verifies incoming JSON Web Tokens (JWT) signed by an identity provider (IdP) via JSON Web Key Sets (JWKS).
   - Claims such as `tenant_id`, `sub` (user ID), `roles`, and departmental scopes will be dynamically extracted from token payloads into the authorization context.

2. **OPA / Rego Integration**:
   - The static JSON policies (`managerPolicy.json`, `employeePolicy.json`) will be connected to or replaced by Open Policy Agent (OPA) with policies authored in Rego.
   - OPA will act as a centralized Policy Decision Point (PDP), evaluating dynamic access rules across multiple services.

3. **Pre-Generation Policy Grounding**:
   - The resolved `effectivePolicy` (`allowedTables`, `deniedColumns`) will be injected into LLM prompt context to constrain natural language query interpretation, ensuring the model never generates queries referencing restricted tables or columns.

4. **SQLGlot AST Enforcement**:
   - Generated SQL queries will be parsed into Abstract Syntax Trees (AST) using SQLGlot.
   - The `rowRules` from the `effectivePolicy` (e.g., `tenant_id = 101` and `department_id = 1`) will be deterministically injected into the `WHERE` clauses to guarantee tenant isolation at the AST level, completely preventing prompt injection and data leakage.

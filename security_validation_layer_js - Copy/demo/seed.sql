-- Sample database for trying the Controlled Write Protocol.
--   mysql -u root -p < demo/seed.sql
-- Re-running it resets the data.

DROP DATABASE IF EXISTS svl_demo;
CREATE DATABASE svl_demo CHARACTER SET utf8mb4;
USE svl_demo;

CREATE TABLE customers (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  tenant_id INT          NOT NULL,
  name      VARCHAR(100) NOT NULL,
  email     VARCHAR(150) NOT NULL,
  phone     VARCHAR(20),
  city      VARCHAR(60),
  -- Deliberately left out of config/schema_allowlist.json: queries must never read it.
  password_hash VARCHAR(100)
) ENGINE = InnoDB;

CREATE TABLE orders (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  tenant_id   INT            NOT NULL,
  customer_id INT            NOT NULL,
  product     VARCHAR(100)   NOT NULL,
  amount      DECIMAL(10, 2) NOT NULL,
  status      VARCHAR(20)    NOT NULL DEFAULT 'pending',
  created_at  DATE           NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers (id)
) ENGINE = InnoDB;

-- MyISAM ignores ROLLBACK, so the protocol must refuse to "preview" writes here.
CREATE TABLE legacy_log (
  id      INT AUTO_INCREMENT PRIMARY KEY,
  message VARCHAR(200)
) ENGINE = MyISAM;

INSERT INTO customers (tenant_id, name, email, phone, city, password_hash) VALUES
  (1, 'Nimal Perera',      'nimal.perera@example.com',  '+94771234567', 'Colombo',    '$2b$12$demoHashNotARealPasswordAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'),
  (1, 'Kavindi Silva',     'kavindi.silva@example.com', '+94712345678', 'Kandy',      '$2b$12$demoHashNotARealPasswordBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB'),
  (1, 'Ruwan Jayasinghe',  'ruwan.j@example.com',       '+94761112233', 'Galle',      '$2b$12$demoHashNotARealPasswordCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC'),
  (2, 'Anjali Fernando',   'anjali.f@example.com',      '+94759876543', 'Negombo',    '$2b$12$demoHashNotARealPasswordDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD'),
  (2, 'Tharindu Bandara',  'tharindu.b@example.com',    '+94705554433', 'Kurunegala', '$2b$12$demoHashNotARealPasswordEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE');

INSERT INTO orders (tenant_id, customer_id, product, amount, status, created_at) VALUES
  (1, 1, 'Cloud Storage Plan',  120.00, 'paid',    '2026-06-03'),
  (1, 1, 'Analytics Add-on',     45.50, 'pending', '2026-07-11'),
  (1, 2, 'Cloud Storage Plan',  120.00, 'pending', '2026-07-19'),
  (1, 3, 'Support Package',     300.00, 'paid',    '2026-08-02'),
  (1, 2, 'Analytics Add-on',     45.50, 'pending', '2026-08-25'),
  (2, 4, 'Cloud Storage Plan',  120.00, 'paid',    '2026-06-14'),
  (2, 5, 'Support Package',     300.00, 'pending', '2026-08-30');

INSERT INTO legacy_log (message) VALUES ('created by seed.sql');

-- Schema of MySQL database `enterprise_hrms_alpha` (structure only), generated for the NL-to-SQL prompt.

CREATE TABLE `applications` (
  `application_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `job_opening_id` int unsigned NOT NULL,
  `candidate_id` int unsigned NOT NULL,
  `applied_date` date NOT NULL,
  `current_stage` enum('APPLIED','SCREENING','INTERVIEW','OFFER','HIRED','REJECTED','WITHDRAWN') NOT NULL,
  `last_stage_reached` enum('APPLIED','SCREENING','INTERVIEW','OFFER','HIRED') NOT NULL,
  `stage_updated_date` date NOT NULL,
  `expected_salary` decimal(14,2) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `rejection_reason` enum('SKILLS_MISMATCH','EXPERIENCE','SALARY','CULTURE_FIT','POSITION_FILLED','OTHER') DEFAULT NULL,
  PRIMARY KEY (`application_id`),
  UNIQUE KEY `uq_applications_tenant` (`tenant_id`,`application_id`),
  UNIQUE KEY `uq_applications_cand_open` (`tenant_id`,`job_opening_id`,`candidate_id`),
  KEY `ix_applications_date` (`tenant_id`,`applied_date`),
  KEY `fk_applications_candidate` (`tenant_id`,`candidate_id`),
  CONSTRAINT `fk_applications_candidate` FOREIGN KEY (`tenant_id`, `candidate_id`) REFERENCES `candidates` (`tenant_id`, `candidate_id`),
  CONSTRAINT `fk_applications_opening` FOREIGN KEY (`tenant_id`, `job_opening_id`) REFERENCES `job_openings` (`tenant_id`, `job_opening_id`)
);

CREATE TABLE `attendance_adjustments` (
  `adjustment_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `attendance_id` bigint unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `adjustment_type` enum('MISSED_PUNCH','TIME_CORRECTION','STATUS_CORRECTION') NOT NULL,
  `old_check_in_at` datetime DEFAULT NULL,
  `old_check_out_at` datetime DEFAULT NULL,
  `new_check_in_at` datetime DEFAULT NULL,
  `new_check_out_at` datetime DEFAULT NULL,
  `reason` varchar(200) NOT NULL,
  `requested_at` datetime NOT NULL,
  `approved_by_employee_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`adjustment_id`),
  KEY `ix_att_adj_attendance` (`tenant_id`,`attendance_id`),
  KEY `fk_att_adj_attendance` (`tenant_id`,`employee_id`,`attendance_id`),
  KEY `fk_att_adj_approver` (`tenant_id`,`approved_by_employee_id`),
  CONSTRAINT `fk_att_adj_approver` FOREIGN KEY (`tenant_id`, `approved_by_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_att_adj_attendance` FOREIGN KEY (`tenant_id`, `employee_id`, `attendance_id`) REFERENCES `attendance_records` (`tenant_id`, `employee_id`, `attendance_id`)
);

CREATE TABLE `attendance_records` (
  `attendance_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `attendance_date` date NOT NULL,
  `shift_id` int unsigned NOT NULL,
  `attendance_status` enum('PRESENT','LATE','REMOTE','HALF_DAY','ABSENT','ON_LEAVE') NOT NULL,
  `check_in_at` datetime DEFAULT NULL,
  `check_out_at` datetime DEFAULT NULL,
  `worked_minutes` smallint unsigned NOT NULL DEFAULT '0',
  `late_minutes` smallint unsigned NOT NULL DEFAULT '0',
  `overtime_minutes` smallint unsigned NOT NULL DEFAULT '0',
  `capture_source` enum('BIOMETRIC','MOBILE','WEB','MANUAL') DEFAULT NULL,
  `leave_request_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`attendance_id`),
  UNIQUE KEY `uq_attendance_emp_date` (`tenant_id`,`employee_id`,`attendance_date`),
  UNIQUE KEY `uq_attendance_tenant_emp_id` (`tenant_id`,`employee_id`,`attendance_id`) COMMENT 'composite target for attendance_adjustments',
  KEY `ix_attendance_date` (`tenant_id`,`attendance_date`),
  KEY `ix_attendance_status` (`tenant_id`,`attendance_status`,`attendance_date`),
  KEY `ix_attendance_checkin` (`tenant_id`,`check_in_at`) COMMENT 'supports duplicate-timestamp (buddy punching) detection',
  KEY `fk_attendance_shift` (`tenant_id`,`shift_id`),
  KEY `fk_attendance_leave` (`tenant_id`,`leave_request_id`),
  CONSTRAINT `fk_attendance_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_attendance_leave` FOREIGN KEY (`tenant_id`, `leave_request_id`) REFERENCES `leave_requests` (`tenant_id`, `leave_request_id`),
  CONSTRAINT `fk_attendance_shift` FOREIGN KEY (`tenant_id`, `shift_id`) REFERENCES `work_shifts` (`tenant_id`, `shift_id`),
  CONSTRAINT `ck_attendance_times` CHECK (((`check_out_at` is null) or (`check_in_at` is null) or (`check_out_at` >= `check_in_at`)))
);

CREATE TABLE `bonuses` (
  `bonus_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `bonus_type` enum('ANNUAL_PERFORMANCE','SPOT_AWARD','RETENTION','SIGN_ON','SALES_INCENTIVE') NOT NULL,
  `award_date` date NOT NULL,
  `payroll_period_id` int unsigned NOT NULL COMMENT 'period in which it is paid',
  `amount` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `performance_review_id` int unsigned DEFAULT NULL,
  `approved_by_employee_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`bonus_id`),
  KEY `ix_bonuses_employee` (`tenant_id`,`employee_id`),
  KEY `ix_bonuses_period` (`tenant_id`,`payroll_period_id`),
  KEY `fk_bonuses_approver` (`tenant_id`,`approved_by_employee_id`),
  KEY `fk_bonuses_review` (`tenant_id`,`performance_review_id`),
  CONSTRAINT `fk_bonuses_approver` FOREIGN KEY (`tenant_id`, `approved_by_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_bonuses_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_bonuses_period` FOREIGN KEY (`tenant_id`, `payroll_period_id`) REFERENCES `payroll_periods` (`tenant_id`, `payroll_period_id`),
  CONSTRAINT `fk_bonuses_review` FOREIGN KEY (`tenant_id`, `performance_review_id`) REFERENCES `performance_reviews` (`tenant_id`, `performance_review_id`),
  CONSTRAINT `ck_bonuses_amount` CHECK ((`amount` > 0))
);

CREATE TABLE `candidates` (
  `candidate_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `first_name` varchar(60) NOT NULL COMMENT 'sensitivity=INTERNAL',
  `last_name` varchar(60) NOT NULL COMMENT 'sensitivity=INTERNAL',
  `email` varchar(160) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=PARTIAL_EMAIL',
  `phone_number` varchar(30) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=PARTIAL_PHONE',
  `gender` enum('MALE','FEMALE','NON_BINARY','UNDISCLOSED') DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `country_code` char(2) NOT NULL,
  `highest_qualification_code` varchar(20) DEFAULT NULL,
  `years_experience` decimal(4,1) DEFAULT NULL,
  `candidate_source` enum('CAREERS_SITE','REFERRAL','JOB_BOARD','PROFESSIONAL_NETWORK','AGENCY','CAMPUS','INTERNAL') NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`candidate_id`),
  UNIQUE KEY `uq_candidates_tenant` (`tenant_id`,`candidate_id`),
  UNIQUE KEY `uq_candidates_email` (`tenant_id`,`email`),
  KEY `fk_candidates_country` (`country_code`),
  KEY `fk_candidates_qual` (`highest_qualification_code`),
  CONSTRAINT `fk_candidates_country` FOREIGN KEY (`country_code`) REFERENCES `countries` (`country_code`),
  CONSTRAINT `fk_candidates_qual` FOREIGN KEY (`highest_qualification_code`) REFERENCES `qualification_levels` (`qualification_code`),
  CONSTRAINT `fk_candidates_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`tenant_id`)
);

CREATE TABLE `certifications` (
  `certification_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `skill_id` int unsigned NOT NULL,
  `certification_name` varchar(150) NOT NULL,
  `issuing_body` varchar(100) NOT NULL,
  `issued_date` date NOT NULL,
  `expiry_date` date DEFAULT NULL,
  `credential_ref` varchar(40) NOT NULL COMMENT 'sensitivity=INTERNAL',
  `employee_training_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`certification_id`),
  KEY `ix_certifications_employee` (`tenant_id`,`employee_id`),
  KEY `ix_certifications_expiry` (`tenant_id`,`expiry_date`),
  KEY `fk_certs_skill` (`skill_id`),
  CONSTRAINT `fk_certs_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_certs_skill` FOREIGN KEY (`skill_id`) REFERENCES `skill_catalog` (`skill_id`),
  CONSTRAINT `ck_certs_dates` CHECK (((`expiry_date` is null) or (`expiry_date` > `issued_date`)))
);

CREATE TABLE `company_locations` (
  `location_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `location_code` varchar(20) NOT NULL,
  `location_name` varchar(100) NOT NULL,
  `city` varchar(60) NOT NULL,
  `country_code` char(2) NOT NULL,
  `is_headquarters` tinyint(1) NOT NULL DEFAULT '0',
  `opened_date` date NOT NULL,
  PRIMARY KEY (`location_id`),
  UNIQUE KEY `uq_company_locations_tenant` (`tenant_id`,`location_id`),
  UNIQUE KEY `uq_company_locations_code` (`tenant_id`,`location_code`),
  KEY `fk_locations_country` (`country_code`),
  CONSTRAINT `fk_locations_country` FOREIGN KEY (`country_code`) REFERENCES `countries` (`country_code`),
  CONSTRAINT `fk_locations_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`tenant_id`)
);

CREATE TABLE `compensation_adjustments` (
  `adjustment_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `adjustment_type` enum('ONE_OFF_ALLOWANCE','RETRO_PAY','SHIFT_ALLOWANCE','RELOCATION','CORRECTION') NOT NULL,
  `amount` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `effective_date` date NOT NULL,
  `payroll_period_id` int unsigned NOT NULL,
  `reason` varchar(200) DEFAULT NULL,
  `requested_by_employee_id` int unsigned DEFAULT NULL,
  `approved_by_employee_id` int unsigned DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`adjustment_id`),
  KEY `ix_comp_adj_employee` (`tenant_id`,`employee_id`,`effective_date`),
  KEY `ix_comp_adj_period` (`tenant_id`,`payroll_period_id`),
  KEY `fk_comp_adj_requester` (`tenant_id`,`requested_by_employee_id`),
  KEY `fk_comp_adj_approver` (`tenant_id`,`approved_by_employee_id`),
  CONSTRAINT `fk_comp_adj_approver` FOREIGN KEY (`tenant_id`, `approved_by_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_comp_adj_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_comp_adj_period` FOREIGN KEY (`tenant_id`, `payroll_period_id`) REFERENCES `payroll_periods` (`tenant_id`, `payroll_period_id`),
  CONSTRAINT `fk_comp_adj_requester` FOREIGN KEY (`tenant_id`, `requested_by_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`)
);

CREATE TABLE `competency_catalog` (
  `competency_code` varchar(30) NOT NULL,
  `competency_name` varchar(80) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`competency_code`)
);

CREATE TABLE `cost_centers` (
  `cost_center_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `cost_center_code` varchar(20) NOT NULL,
  `cost_center_name` varchar(100) NOT NULL,
  `annual_budget` decimal(16,2) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`cost_center_id`),
  UNIQUE KEY `uq_cost_centers_tenant` (`tenant_id`,`cost_center_id`),
  UNIQUE KEY `uq_cost_centers_code` (`tenant_id`,`cost_center_code`),
  CONSTRAINT `fk_cost_centers_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`tenant_id`)
);

CREATE TABLE `countries` (
  `country_code` char(2) NOT NULL COMMENT 'ISO-3166 alpha-2',
  `country_code3` char(3) NOT NULL,
  `country_name` varchar(80) NOT NULL,
  `region` varchar(40) NOT NULL,
  `currency_code` char(3) NOT NULL,
  `phone_prefix` varchar(6) NOT NULL,
  PRIMARY KEY (`country_code`),
  UNIQUE KEY `uq_countries_code3` (`country_code3`),
  KEY `fk_countries_currency` (`currency_code`),
  CONSTRAINT `fk_countries_currency` FOREIGN KEY (`currency_code`) REFERENCES `currencies` (`currency_code`)
);

CREATE TABLE `currencies` (
  `currency_code` char(3) NOT NULL,
  `currency_name` varchar(60) NOT NULL,
  `symbol` varchar(8) DEFAULT NULL,
  `minor_units` tinyint unsigned NOT NULL DEFAULT '2',
  PRIMARY KEY (`currency_code`)
);

CREATE TABLE `deductions` (
  `deduction_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `deduction_type` enum('STAFF_LOAN','SALARY_ADVANCE','UNION_DUES','HEALTH_INSURANCE','COURT_ORDER') NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date DEFAULT NULL,
  `monthly_amount` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `total_amount` decimal(14,2) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `deduction_status` enum('ACTIVE','COMPLETED','CANCELLED') NOT NULL,
  PRIMARY KEY (`deduction_id`),
  KEY `ix_deductions_employee` (`tenant_id`,`employee_id`),
  CONSTRAINT `fk_deductions_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `ck_deductions_dates` CHECK (((`end_date` is null) or (`end_date` >= `start_date`)))
);

CREATE TABLE `department_hierarchy` (
  `tenant_id` int unsigned NOT NULL,
  `ancestor_department_id` int unsigned NOT NULL,
  `descendant_department_id` int unsigned NOT NULL,
  `depth` tinyint unsigned NOT NULL COMMENT '0 = self',
  PRIMARY KEY (`tenant_id`,`ancestor_department_id`,`descendant_department_id`),
  KEY `ix_dept_hier_desc` (`tenant_id`,`descendant_department_id`),
  CONSTRAINT `fk_dept_hier_ancestor` FOREIGN KEY (`tenant_id`, `ancestor_department_id`) REFERENCES `departments` (`tenant_id`, `department_id`),
  CONSTRAINT `fk_dept_hier_descendant` FOREIGN KEY (`tenant_id`, `descendant_department_id`) REFERENCES `departments` (`tenant_id`, `department_id`)
);

CREATE TABLE `department_managers` (
  `department_manager_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `department_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `manager_role` enum('HEAD','HR_BUSINESS_PARTNER') NOT NULL,
  `effective_from` date NOT NULL,
  `effective_to` date DEFAULT NULL,
  PRIMARY KEY (`department_manager_id`),
  KEY `ix_dept_mgr_dept` (`tenant_id`,`department_id`,`effective_from`),
  KEY `ix_dept_mgr_emp` (`tenant_id`,`employee_id`),
  CONSTRAINT `fk_dept_mgr_department` FOREIGN KEY (`tenant_id`, `department_id`) REFERENCES `departments` (`tenant_id`, `department_id`),
  CONSTRAINT `fk_dept_mgr_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `ck_dept_mgr_dates` CHECK (((`effective_to` is null) or (`effective_to` >= `effective_from`)))
);

CREATE TABLE `departments` (
  `department_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `department_code` varchar(20) NOT NULL,
  `department_name` varchar(100) NOT NULL,
  `department_type` enum('EXECUTIVE','DIVISION','DEPARTMENT') NOT NULL,
  `parent_department_id` int unsigned DEFAULT NULL COMMENT 'adjacency list; full closure in department_hierarchy',
  `cost_center_id` int unsigned NOT NULL,
  `location_id` int unsigned NOT NULL COMMENT 'primary location',
  `established_date` date NOT NULL,
  `closed_date` date DEFAULT NULL,
  PRIMARY KEY (`department_id`),
  UNIQUE KEY `uq_departments_tenant` (`tenant_id`,`department_id`),
  UNIQUE KEY `uq_departments_code` (`tenant_id`,`department_code`),
  KEY `ix_departments_parent` (`tenant_id`,`parent_department_id`),
  KEY `fk_departments_cost_center` (`tenant_id`,`cost_center_id`),
  KEY `fk_departments_location` (`tenant_id`,`location_id`),
  CONSTRAINT `fk_departments_cost_center` FOREIGN KEY (`tenant_id`, `cost_center_id`) REFERENCES `cost_centers` (`tenant_id`, `cost_center_id`),
  CONSTRAINT `fk_departments_location` FOREIGN KEY (`tenant_id`, `location_id`) REFERENCES `company_locations` (`tenant_id`, `location_id`),
  CONSTRAINT `fk_departments_parent` FOREIGN KEY (`tenant_id`, `parent_department_id`) REFERENCES `departments` (`tenant_id`, `department_id`),
  CONSTRAINT `fk_departments_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`tenant_id`)
);

CREATE TABLE `employee_addresses` (
  `address_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `address_type` enum('HOME','MAILING','TEMPORARY') NOT NULL,
  `address_line1` varchar(150) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `address_line2` varchar(150) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `city` varchar(60) NOT NULL COMMENT 'sensitivity=INTERNAL',
  `postal_code` varchar(15) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `country_code` char(2) NOT NULL COMMENT 'sensitivity=INTERNAL',
  `valid_from` date NOT NULL,
  `valid_to` date DEFAULT NULL,
  PRIMARY KEY (`address_id`),
  KEY `ix_addresses_employee` (`tenant_id`,`employee_id`),
  KEY `fk_addresses_country` (`country_code`),
  CONSTRAINT `fk_addresses_country` FOREIGN KEY (`country_code`) REFERENCES `countries` (`country_code`),
  CONSTRAINT `fk_addresses_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `ck_addresses_dates` CHECK (((`valid_to` is null) or (`valid_to` >= `valid_from`)))
);

CREATE TABLE `employee_bank_accounts` (
  `bank_account_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `bank_name` varchar(80) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=NONE',
  `branch_code` varchar(20) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `account_number` varchar(34) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=LAST4; synthetic',
  `account_holder_name` varchar(120) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `is_primary` tinyint(1) NOT NULL DEFAULT '1',
  `valid_from` date NOT NULL,
  `valid_to` date DEFAULT NULL,
  PRIMARY KEY (`bank_account_id`),
  UNIQUE KEY `uq_bank_accounts_tenant` (`tenant_id`,`bank_account_id`),
  KEY `ix_bank_accounts_employee` (`tenant_id`,`employee_id`),
  CONSTRAINT `fk_bank_accounts_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`)
);

CREATE TABLE `employee_contacts` (
  `contact_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `contact_type` enum('PERSONAL_EMAIL','PERSONAL_MOBILE','HOME_PHONE','WORK_PHONE') NOT NULL,
  `contact_value` varchar(160) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=PARTIAL_PHONE|PARTIAL_EMAIL by contact_type',
  `is_primary` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`contact_id`),
  UNIQUE KEY `uq_employee_contacts` (`tenant_id`,`employee_id`,`contact_type`),
  CONSTRAINT `fk_contacts_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`)
);

CREATE TABLE `employee_contracts` (
  `contract_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `contract_type` enum('PERMANENT','FIXED_TERM','PROBATIONARY','SEASONAL','CONSULTANCY') NOT NULL,
  `employment_type_code` varchar(20) NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date DEFAULT NULL,
  `weekly_hours` decimal(4,1) NOT NULL,
  `notice_period_days` smallint unsigned NOT NULL,
  `signed_date` date NOT NULL,
  `contract_status` enum('ACTIVE','EXPIRED','TERMINATED','SUPERSEDED') NOT NULL,
  PRIMARY KEY (`contract_id`),
  KEY `ix_contracts_employee` (`tenant_id`,`employee_id`),
  KEY `fk_contracts_emp_type` (`employment_type_code`),
  CONSTRAINT `fk_contracts_emp_type` FOREIGN KEY (`employment_type_code`) REFERENCES `employment_types` (`employment_type_code`),
  CONSTRAINT `fk_contracts_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `ck_contracts_dates` CHECK (((`end_date` is null) or (`end_date` >= `start_date`)))
);

CREATE TABLE `employee_dependents` (
  `dependent_id` int unsigned NOT NULL AUTO_INCREMENT,
  `employee_id` int unsigned NOT NULL,
  `dependent_name` varchar(120) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `relationship` enum('SPOUSE','CHILD','PARENT','OTHER') NOT NULL COMMENT 'sensitivity=RESTRICTED',
  `date_of_birth` date DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=YEAR_ONLY',
  `is_insurance_beneficiary` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`dependent_id`),
  KEY `ix_dependents_employee` (`employee_id`),
  CONSTRAINT `fk_dependents_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`employee_id`)
);

CREATE TABLE `employee_documents_metadata` (
  `document_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `document_type` enum('OFFER_LETTER','EMPLOYMENT_CONTRACT','ID_COPY','PASSPORT','DEGREE_CERTIFICATE','MEDICAL_CERTIFICATE','PERFORMANCE_LETTER','RESIGNATION_LETTER') NOT NULL,
  `file_name` varchar(160) NOT NULL,
  `storage_uri` varchar(255) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL; synthetic object-store path, no file exists',
  `content_sha256` char(64) NOT NULL,
  `uploaded_at` datetime NOT NULL,
  `expires_on` date DEFAULT NULL,
  `is_confidential` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`document_id`),
  KEY `ix_documents_employee` (`tenant_id`,`employee_id`),
  CONSTRAINT `fk_documents_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`)
);

CREATE TABLE `employee_emergency_contacts` (
  `emergency_contact_id` int unsigned NOT NULL AUTO_INCREMENT,
  `employee_id` int unsigned NOT NULL,
  `contact_name` varchar(120) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `relationship` enum('SPOUSE','PARENT','SIBLING','CHILD','FRIEND','OTHER') NOT NULL,
  `phone_number` varchar(30) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=PARTIAL_PHONE',
  `priority` tinyint unsigned NOT NULL DEFAULT '1',
  PRIMARY KEY (`emergency_contact_id`),
  KEY `ix_emergency_employee` (`employee_id`),
  CONSTRAINT `fk_emergency_employee` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`employee_id`)
);

CREATE TABLE `employee_kpis` (
  `employee_kpi_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `kpi_code` varchar(30) NOT NULL,
  `kpi_name` varchar(100) NOT NULL,
  `period_start` date NOT NULL COMMENT 'quarter start',
  `period_end` date NOT NULL,
  `target_value` decimal(14,2) NOT NULL,
  `actual_value` decimal(14,2) NOT NULL,
  `unit` varchar(20) NOT NULL,
  PRIMARY KEY (`employee_kpi_id`),
  UNIQUE KEY `uq_employee_kpis` (`tenant_id`,`employee_id`,`kpi_code`,`period_start`),
  CONSTRAINT `fk_kpis_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`)
);

CREATE TABLE `employee_reporting_structure` (
  `reporting_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `manager_employee_id` int unsigned NOT NULL,
  `relationship_type` enum('SOLID_LINE','DOTTED_LINE') NOT NULL,
  `effective_from` date NOT NULL,
  `effective_to` date DEFAULT NULL,
  PRIMARY KEY (`reporting_id`),
  KEY `ix_reporting_employee` (`tenant_id`,`employee_id`,`effective_from`),
  KEY `ix_reporting_manager` (`tenant_id`,`manager_employee_id`,`effective_from`),
  CONSTRAINT `fk_reporting_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_reporting_manager` FOREIGN KEY (`tenant_id`, `manager_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `ck_reporting_dates` CHECK (((`effective_to` is null) or (`effective_to` >= `effective_from`))),
  CONSTRAINT `ck_reporting_self` CHECK ((`employee_id` <> `manager_employee_id`))
);

CREATE TABLE `employee_skills` (
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `skill_id` int unsigned NOT NULL,
  `proficiency_level` tinyint unsigned NOT NULL COMMENT '1-5',
  `assessment_source` enum('SELF','MANAGER','CERTIFICATION','TRAINING') NOT NULL,
  `last_assessed_date` date NOT NULL,
  PRIMARY KEY (`tenant_id`,`employee_id`,`skill_id`),
  KEY `ix_emp_skills_skill` (`tenant_id`,`skill_id`),
  KEY `fk_emp_skills_skill` (`skill_id`),
  CONSTRAINT `fk_emp_skills_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_emp_skills_skill` FOREIGN KEY (`skill_id`) REFERENCES `skill_catalog` (`skill_id`),
  CONSTRAINT `ck_emp_skills_level` CHECK ((`proficiency_level` between 1 and 5))
);

CREATE TABLE `employee_training` (
  `employee_training_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `training_program_id` int unsigned NOT NULL,
  `enrolled_date` date NOT NULL,
  `start_date` date NOT NULL,
  `completion_date` date DEFAULT NULL,
  `training_status` enum('ENROLLED','IN_PROGRESS','COMPLETED','DROPPED','NO_SHOW') NOT NULL,
  `assessment_score` decimal(5,2) DEFAULT NULL COMMENT '0-100',
  `feedback_rating` tinyint unsigned DEFAULT NULL COMMENT '1-5',
  `actual_cost` decimal(12,2) NOT NULL COMMENT 'sensitivity=INTERNAL',
  PRIMARY KEY (`employee_training_id`),
  KEY `ix_emp_training_employee` (`tenant_id`,`employee_id`,`start_date`),
  KEY `ix_emp_training_program` (`tenant_id`,`training_program_id`),
  CONSTRAINT `fk_emp_training_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_emp_training_program` FOREIGN KEY (`tenant_id`, `training_program_id`) REFERENCES `training_programs` (`tenant_id`, `training_program_id`),
  CONSTRAINT `ck_emp_training_dates` CHECK (((`completion_date` is null) or (`completion_date` >= `start_date`)))
);

CREATE TABLE `employees` (
  `employee_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_number` varchar(20) NOT NULL,
  `first_name` varchar(60) NOT NULL COMMENT 'sensitivity=PUBLIC',
  `last_name` varchar(60) NOT NULL COMMENT 'sensitivity=PUBLIC',
  `full_name` varchar(121) GENERATED ALWAYS AS (concat(`first_name`,_utf8mb4' ',`last_name`)) STORED COMMENT 'sensitivity=PUBLIC',
  `gender` enum('MALE','FEMALE','NON_BINARY','UNDISCLOSED') DEFAULT NULL COMMENT 'sensitivity=INTERNAL; NULL = unknown/not recorded, UNDISCLOSED = employee declined',
  `date_of_birth` date DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=YEAR_ONLY',
  `national_id_number` varchar(30) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=LAST4; synthetic, test-range formats',
  `nationality_country_code` char(2) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `marital_status` enum('SINGLE','MARRIED','DIVORCED','WIDOWED','UNDISCLOSED') DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `highest_qualification_code` varchar(20) DEFAULT NULL COMMENT 'sensitivity=INTERNAL',
  `work_email` varchar(160) NOT NULL COMMENT 'sensitivity=INTERNAL; mask=PARTIAL_EMAIL',
  `department_id` int unsigned NOT NULL COMMENT 'sensitivity=PUBLIC; CURRENT department (history in employment_history)',
  `team_id` int unsigned DEFAULT NULL COMMENT 'sensitivity=PUBLIC',
  `position_id` int unsigned NOT NULL COMMENT 'sensitivity=PUBLIC',
  `manager_employee_id` int unsigned DEFAULT NULL COMMENT 'sensitivity=INTERNAL; current solid-line manager',
  `location_id` int unsigned NOT NULL COMMENT 'sensitivity=PUBLIC',
  `cost_center_id` int unsigned NOT NULL COMMENT 'sensitivity=INTERNAL',
  `employment_type_code` varchar(20) NOT NULL COMMENT 'sensitivity=PUBLIC',
  `employment_status` enum('ACTIVE','PROBATION','ON_LEAVE','RESIGNED','TERMINATED','RETIRED') NOT NULL COMMENT 'sensitivity=PUBLIC',
  `hire_date` date NOT NULL COMMENT 'sensitivity=INTERNAL',
  `probation_end_date` date DEFAULT NULL COMMENT 'sensitivity=INTERNAL',
  `termination_date` date DEFAULT NULL COMMENT 'sensitivity=INTERNAL; last working day',
  `termination_reason` enum('VOLUNTARY_RESIGNATION','PERFORMANCE','MISCONDUCT','REDUNDANCY','CONTRACT_END','RETIREMENT') DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `is_rehire_eligible` tinyint(1) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`employee_id`),
  UNIQUE KEY `uq_employees_tenant` (`tenant_id`,`employee_id`),
  UNIQUE KEY `uq_employees_number` (`tenant_id`,`employee_number`),
  UNIQUE KEY `uq_employees_email` (`tenant_id`,`work_email`),
  KEY `ix_employees_dept_status` (`tenant_id`,`department_id`,`employment_status`),
  KEY `ix_employees_status` (`tenant_id`,`employment_status`),
  KEY `ix_employees_hire` (`tenant_id`,`hire_date`),
  KEY `ix_employees_term` (`tenant_id`,`termination_date`),
  KEY `ix_employees_manager` (`tenant_id`,`manager_employee_id`),
  KEY `fk_employees_team` (`tenant_id`,`department_id`,`team_id`),
  KEY `fk_employees_position` (`tenant_id`,`position_id`),
  KEY `fk_employees_location` (`tenant_id`,`location_id`),
  KEY `fk_employees_cost_center` (`tenant_id`,`cost_center_id`),
  KEY `fk_employees_emp_type` (`employment_type_code`),
  KEY `fk_employees_nationality` (`nationality_country_code`),
  KEY `fk_employees_qualification` (`highest_qualification_code`),
  CONSTRAINT `fk_employees_cost_center` FOREIGN KEY (`tenant_id`, `cost_center_id`) REFERENCES `cost_centers` (`tenant_id`, `cost_center_id`),
  CONSTRAINT `fk_employees_department` FOREIGN KEY (`tenant_id`, `department_id`) REFERENCES `departments` (`tenant_id`, `department_id`),
  CONSTRAINT `fk_employees_emp_type` FOREIGN KEY (`employment_type_code`) REFERENCES `employment_types` (`employment_type_code`),
  CONSTRAINT `fk_employees_location` FOREIGN KEY (`tenant_id`, `location_id`) REFERENCES `company_locations` (`tenant_id`, `location_id`),
  CONSTRAINT `fk_employees_manager` FOREIGN KEY (`tenant_id`, `manager_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_employees_nationality` FOREIGN KEY (`nationality_country_code`) REFERENCES `countries` (`country_code`),
  CONSTRAINT `fk_employees_position` FOREIGN KEY (`tenant_id`, `position_id`) REFERENCES `job_positions` (`tenant_id`, `position_id`),
  CONSTRAINT `fk_employees_qualification` FOREIGN KEY (`highest_qualification_code`) REFERENCES `qualification_levels` (`qualification_code`),
  CONSTRAINT `fk_employees_team` FOREIGN KEY (`tenant_id`, `department_id`, `team_id`) REFERENCES `teams` (`tenant_id`, `department_id`, `team_id`),
  CONSTRAINT `fk_employees_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`tenant_id`),
  CONSTRAINT `ck_employees_status_term` CHECK ((((`employment_status` in (_utf8mb4'RESIGNED',_utf8mb4'TERMINATED',_utf8mb4'RETIRED')) and (`termination_date` is not null)) or ((`employment_status` in (_utf8mb4'ACTIVE',_utf8mb4'PROBATION',_utf8mb4'ON_LEAVE')) and (`termination_date` is null)))),
  CONSTRAINT `ck_employees_term` CHECK (((`termination_date` is null) or (`termination_date` >= `hire_date`)))
);

CREATE TABLE `employment_history` (
  `history_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `effective_from` date NOT NULL,
  `effective_to` date DEFAULT NULL COMMENT 'NULL = current period',
  `department_id` int unsigned NOT NULL,
  `team_id` int unsigned DEFAULT NULL,
  `position_id` int unsigned NOT NULL,
  `job_level_code` char(2) NOT NULL,
  `employment_type_code` varchar(20) NOT NULL,
  `employment_status` enum('ACTIVE','PROBATION','ON_LEAVE','RESIGNED','TERMINATED','RETIRED') NOT NULL,
  `change_reason` enum('HIRE','DATA_MIGRATION','PROBATION_CONFIRMED','PROMOTION','TRANSFER','LEAVE_OF_ABSENCE','RETURN_FROM_LEAVE','REORGANIZATION','RESIGNATION','TERMINATION','RETIREMENT','CONTRACT_END') NOT NULL,
  PRIMARY KEY (`history_id`),
  KEY `ix_emp_hist_employee` (`tenant_id`,`employee_id`,`effective_from`),
  KEY `ix_emp_hist_dept` (`tenant_id`,`department_id`,`effective_from`),
  KEY `fk_emp_hist_team` (`tenant_id`,`department_id`,`team_id`),
  KEY `fk_emp_hist_position` (`tenant_id`,`position_id`),
  KEY `fk_emp_hist_level` (`job_level_code`),
  KEY `fk_emp_hist_emp_type` (`employment_type_code`),
  CONSTRAINT `fk_emp_hist_department` FOREIGN KEY (`tenant_id`, `department_id`) REFERENCES `departments` (`tenant_id`, `department_id`),
  CONSTRAINT `fk_emp_hist_emp_type` FOREIGN KEY (`employment_type_code`) REFERENCES `employment_types` (`employment_type_code`),
  CONSTRAINT `fk_emp_hist_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_emp_hist_level` FOREIGN KEY (`job_level_code`) REFERENCES `job_levels` (`job_level_code`),
  CONSTRAINT `fk_emp_hist_position` FOREIGN KEY (`tenant_id`, `position_id`) REFERENCES `job_positions` (`tenant_id`, `position_id`),
  CONSTRAINT `fk_emp_hist_team` FOREIGN KEY (`tenant_id`, `department_id`, `team_id`) REFERENCES `teams` (`tenant_id`, `department_id`, `team_id`),
  CONSTRAINT `ck_emp_hist_dates` CHECK (((`effective_to` is null) or (`effective_to` >= `effective_from`)))
);

CREATE TABLE `employment_types` (
  `employment_type_code` varchar(20) NOT NULL,
  `employment_type_name` varchar(60) NOT NULL,
  `is_permanent` tinyint(1) NOT NULL,
  `standard_weekly_hours` decimal(4,1) NOT NULL,
  PRIMARY KEY (`employment_type_code`)
);

CREATE TABLE `exchange_rates` (
  `currency_code` char(3) NOT NULL,
  `rate_month` date NOT NULL COMMENT 'first day of month',
  `units_per_usd` decimal(14,6) NOT NULL COMMENT 'synthetic monthly average',
  PRIMARY KEY (`currency_code`,`rate_month`),
  CONSTRAINT `fk_exrates_currency` FOREIGN KEY (`currency_code`) REFERENCES `currencies` (`currency_code`)
);

CREATE TABLE `hiring_decisions` (
  `hiring_decision_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `application_id` int unsigned NOT NULL,
  `decision` enum('OFFER_ACCEPTED','OFFER_DECLINED','REJECTED_AFTER_INTERVIEW') NOT NULL,
  `decision_date` date NOT NULL,
  `offered_salary` decimal(14,2) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `proposed_start_date` date DEFAULT NULL,
  `hired_employee_id` int unsigned DEFAULT NULL,
  `decided_by_employee_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`hiring_decision_id`),
  UNIQUE KEY `uq_hiring_decisions_app` (`tenant_id`,`application_id`),
  KEY `fk_hiring_employee` (`tenant_id`,`hired_employee_id`),
  KEY `fk_hiring_decider` (`tenant_id`,`decided_by_employee_id`),
  CONSTRAINT `fk_hiring_application` FOREIGN KEY (`tenant_id`, `application_id`) REFERENCES `applications` (`tenant_id`, `application_id`),
  CONSTRAINT `fk_hiring_decider` FOREIGN KEY (`tenant_id`, `decided_by_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_hiring_employee` FOREIGN KEY (`tenant_id`, `hired_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`)
);

CREATE TABLE `industry_types` (
  `industry_code` varchar(20) NOT NULL,
  `industry_name` varchar(80) NOT NULL,
  `sector` varchar(40) NOT NULL,
  PRIMARY KEY (`industry_code`)
);

CREATE TABLE `interview_records` (
  `interview_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `application_id` int unsigned NOT NULL,
  `interview_round` tinyint unsigned NOT NULL,
  `interview_type` enum('PHONE_SCREEN','TECHNICAL','PANEL','HR','CASE_STUDY') NOT NULL,
  `interviewer_employee_id` int unsigned DEFAULT NULL,
  `scheduled_at` datetime NOT NULL,
  `score` decimal(3,1) DEFAULT NULL COMMENT '1.0 - 5.0',
  `recommendation` enum('STRONG_HIRE','HIRE','NO_HIRE','STRONG_NO_HIRE') DEFAULT NULL,
  PRIMARY KEY (`interview_id`),
  UNIQUE KEY `uq_interviews_round` (`tenant_id`,`application_id`,`interview_round`),
  KEY `fk_interviews_interviewer` (`tenant_id`,`interviewer_employee_id`),
  CONSTRAINT `fk_interviews_application` FOREIGN KEY (`tenant_id`, `application_id`) REFERENCES `applications` (`tenant_id`, `application_id`),
  CONSTRAINT `fk_interviews_interviewer` FOREIGN KEY (`tenant_id`, `interviewer_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`)
);

CREATE TABLE `job_levels` (
  `job_level_code` char(2) NOT NULL,
  `level_rank` tinyint unsigned NOT NULL,
  `level_name` varchar(40) NOT NULL,
  `is_management` tinyint(1) NOT NULL,
  PRIMARY KEY (`job_level_code`),
  UNIQUE KEY `uq_job_levels_rank` (`level_rank`)
);

CREATE TABLE `job_openings` (
  `job_opening_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `opening_code` varchar(30) NOT NULL,
  `department_id` int unsigned NOT NULL,
  `position_id` int unsigned NOT NULL,
  `hiring_manager_employee_id` int unsigned DEFAULT NULL,
  `employment_type_code` varchar(20) NOT NULL,
  `opening_reason` enum('GROWTH','REPLACEMENT','SEASONAL','NEW_ROLE') NOT NULL,
  `headcount_requested` tinyint unsigned NOT NULL DEFAULT '1',
  `opened_date` date NOT NULL,
  `target_fill_date` date NOT NULL,
  `closed_date` date DEFAULT NULL,
  `opening_status` enum('OPEN','ON_HOLD','FILLED','CANCELLED') NOT NULL,
  `salary_budget_max` decimal(14,2) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  PRIMARY KEY (`job_opening_id`),
  UNIQUE KEY `uq_job_openings_tenant` (`tenant_id`,`job_opening_id`),
  UNIQUE KEY `uq_job_openings_code` (`tenant_id`,`opening_code`),
  KEY `ix_job_openings_dept` (`tenant_id`,`department_id`,`opened_date`),
  KEY `fk_openings_position` (`tenant_id`,`position_id`),
  KEY `fk_openings_manager` (`tenant_id`,`hiring_manager_employee_id`),
  KEY `fk_openings_emp_type` (`employment_type_code`),
  CONSTRAINT `fk_openings_department` FOREIGN KEY (`tenant_id`, `department_id`) REFERENCES `departments` (`tenant_id`, `department_id`),
  CONSTRAINT `fk_openings_emp_type` FOREIGN KEY (`employment_type_code`) REFERENCES `employment_types` (`employment_type_code`),
  CONSTRAINT `fk_openings_manager` FOREIGN KEY (`tenant_id`, `hiring_manager_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_openings_position` FOREIGN KEY (`tenant_id`, `position_id`) REFERENCES `job_positions` (`tenant_id`, `position_id`)
);

CREATE TABLE `job_positions` (
  `position_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `position_code` varchar(40) NOT NULL,
  `position_title` varchar(120) NOT NULL,
  `job_category_code` varchar(20) NOT NULL,
  `job_level_code` char(2) NOT NULL,
  `salary_band_min` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND; annual, tenant base currency',
  `salary_band_mid` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `salary_band_max` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`position_id`),
  UNIQUE KEY `uq_job_positions_tenant` (`tenant_id`,`position_id`),
  UNIQUE KEY `uq_job_positions_code` (`tenant_id`,`position_code`),
  KEY `fk_positions_category` (`job_category_code`),
  KEY `fk_positions_level` (`job_level_code`),
  CONSTRAINT `fk_positions_category` FOREIGN KEY (`job_category_code`) REFERENCES `standardized_job_categories` (`job_category_code`),
  CONSTRAINT `fk_positions_level` FOREIGN KEY (`job_level_code`) REFERENCES `job_levels` (`job_level_code`),
  CONSTRAINT `fk_positions_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`tenant_id`),
  CONSTRAINT `ck_positions_band` CHECK (((`salary_band_min` <= `salary_band_mid`) and (`salary_band_mid` <= `salary_band_max`)))
);

CREATE TABLE `leave_approvals` (
  `leave_approval_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `leave_request_id` int unsigned NOT NULL,
  `approval_level` tinyint unsigned NOT NULL,
  `approver_employee_id` int unsigned NOT NULL,
  `decision` enum('APPROVED','REJECTED','PENDING') NOT NULL,
  `decided_at` datetime DEFAULT NULL,
  `comments` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`leave_approval_id`),
  UNIQUE KEY `uq_leave_approvals` (`tenant_id`,`leave_request_id`,`approval_level`),
  KEY `ix_leave_appr_approver` (`tenant_id`,`approver_employee_id`),
  CONSTRAINT `fk_leave_appr_approver` FOREIGN KEY (`tenant_id`, `approver_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_leave_appr_request` FOREIGN KEY (`tenant_id`, `leave_request_id`) REFERENCES `leave_requests` (`tenant_id`, `leave_request_id`)
);

CREATE TABLE `leave_balances` (
  `leave_balance_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `leave_type_code` varchar(20) NOT NULL,
  `balance_year` smallint unsigned NOT NULL,
  `as_of_date` date NOT NULL,
  `entitled_days` decimal(5,1) NOT NULL,
  `carried_forward_days` decimal(5,1) NOT NULL,
  `taken_days` decimal(5,1) NOT NULL,
  `pending_days` decimal(5,1) NOT NULL,
  `remaining_days` decimal(5,1) NOT NULL,
  PRIMARY KEY (`leave_balance_id`),
  UNIQUE KEY `uq_leave_balances` (`tenant_id`,`employee_id`,`leave_type_code`,`balance_year`),
  KEY `fk_leave_bal_type` (`leave_type_code`),
  CONSTRAINT `fk_leave_bal_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_leave_bal_type` FOREIGN KEY (`leave_type_code`) REFERENCES `leave_type_catalog` (`leave_type_code`)
);

CREATE TABLE `leave_entitlements` (
  `entitlement_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `leave_policy_id` int unsigned NOT NULL,
  `leave_type_code` varchar(20) NOT NULL,
  `entitlement_year` smallint unsigned NOT NULL,
  `entitled_days` decimal(5,1) NOT NULL COMMENT 'pro-rated for joiners/leavers',
  `carried_forward_days` decimal(5,1) NOT NULL DEFAULT '0.0',
  `granted_on` date NOT NULL,
  PRIMARY KEY (`entitlement_id`),
  UNIQUE KEY `uq_leave_entitlements` (`tenant_id`,`employee_id`,`leave_type_code`,`entitlement_year`),
  KEY `fk_leave_ent_policy` (`tenant_id`,`leave_policy_id`),
  KEY `fk_leave_ent_type` (`leave_type_code`),
  CONSTRAINT `fk_leave_ent_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_leave_ent_policy` FOREIGN KEY (`tenant_id`, `leave_policy_id`) REFERENCES `leave_policies` (`tenant_id`, `leave_policy_id`),
  CONSTRAINT `fk_leave_ent_type` FOREIGN KEY (`leave_type_code`) REFERENCES `leave_type_catalog` (`leave_type_code`)
);

CREATE TABLE `leave_policies` (
  `leave_policy_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `leave_type_code` varchar(20) NOT NULL,
  `policy_name` varchar(100) NOT NULL,
  `annual_entitlement_days` decimal(5,1) NOT NULL,
  `max_carry_forward_days` decimal(5,1) NOT NULL DEFAULT '0.0',
  `min_service_months` tinyint unsigned NOT NULL DEFAULT '0',
  `requires_document_after_days` tinyint unsigned DEFAULT NULL,
  `accrual_method` enum('ANNUAL_GRANT','MONTHLY_ACCRUAL','EVENT_BASED') NOT NULL,
  `effective_from` date NOT NULL,
  `effective_to` date DEFAULT NULL,
  PRIMARY KEY (`leave_policy_id`),
  UNIQUE KEY `uq_leave_policies_tenant` (`tenant_id`,`leave_policy_id`),
  UNIQUE KEY `uq_leave_policies_type` (`tenant_id`,`leave_type_code`,`effective_from`),
  KEY `fk_leave_policies_type` (`leave_type_code`),
  CONSTRAINT `fk_leave_policies_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`tenant_id`),
  CONSTRAINT `fk_leave_policies_type` FOREIGN KEY (`leave_type_code`) REFERENCES `leave_type_catalog` (`leave_type_code`)
);

CREATE TABLE `leave_requests` (
  `leave_request_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `leave_policy_id` int unsigned NOT NULL,
  `leave_type_code` varchar(20) NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `total_days` decimal(5,1) NOT NULL COMMENT 'working days',
  `is_half_day` tinyint(1) NOT NULL DEFAULT '0',
  `request_status` enum('PENDING','APPROVED','REJECTED','CANCELLED') NOT NULL,
  `requested_at` datetime NOT NULL,
  `decided_at` datetime DEFAULT NULL,
  `reason_text` varchar(255) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL; may contain medical detail',
  PRIMARY KEY (`leave_request_id`),
  UNIQUE KEY `uq_leave_requests_tenant` (`tenant_id`,`leave_request_id`),
  KEY `ix_leave_req_employee` (`tenant_id`,`employee_id`,`start_date`),
  KEY `ix_leave_req_dates` (`tenant_id`,`start_date`),
  KEY `ix_leave_req_type` (`tenant_id`,`leave_type_code`,`start_date`),
  KEY `fk_leave_req_policy` (`tenant_id`,`leave_policy_id`),
  KEY `fk_leave_req_type` (`leave_type_code`),
  CONSTRAINT `fk_leave_req_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_leave_req_policy` FOREIGN KEY (`tenant_id`, `leave_policy_id`) REFERENCES `leave_policies` (`tenant_id`, `leave_policy_id`),
  CONSTRAINT `fk_leave_req_type` FOREIGN KEY (`leave_type_code`) REFERENCES `leave_type_catalog` (`leave_type_code`),
  CONSTRAINT `ck_leave_req_dates` CHECK ((`end_date` >= `start_date`))
);

CREATE TABLE `leave_type_catalog` (
  `leave_type_code` varchar(20) NOT NULL,
  `leave_type_name` varchar(60) NOT NULL,
  `is_paid` tinyint(1) NOT NULL,
  `is_statutory` tinyint(1) NOT NULL,
  PRIMARY KEY (`leave_type_code`)
);

CREATE TABLE `overtime_records` (
  `overtime_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `payroll_period_id` int unsigned NOT NULL,
  `overtime_month` date NOT NULL COMMENT 'first day of month',
  `claimed_hours` decimal(6,2) NOT NULL,
  `approved_hours` decimal(6,2) NOT NULL,
  `rate_multiplier` decimal(3,2) NOT NULL,
  `overtime_amount` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `claim_status` enum('APPROVED','PARTIALLY_APPROVED','REJECTED') NOT NULL,
  `approved_by_employee_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`overtime_id`),
  UNIQUE KEY `uq_overtime_emp_month` (`tenant_id`,`employee_id`,`overtime_month`),
  KEY `ix_overtime_month` (`tenant_id`,`overtime_month`),
  KEY `fk_overtime_period` (`tenant_id`,`payroll_period_id`),
  KEY `fk_overtime_approver` (`tenant_id`,`approved_by_employee_id`),
  CONSTRAINT `fk_overtime_approver` FOREIGN KEY (`tenant_id`, `approved_by_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_overtime_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_overtime_period` FOREIGN KEY (`tenant_id`, `payroll_period_id`) REFERENCES `payroll_periods` (`tenant_id`, `payroll_period_id`),
  CONSTRAINT `ck_overtime_hours` CHECK ((`approved_hours` <= `claimed_hours`))
);

CREATE TABLE `payroll_component_catalog` (
  `component_code` varchar(30) NOT NULL,
  `component_name` varchar(80) NOT NULL,
  `component_kind` enum('EARNING','DEDUCTION','EMPLOYER_CONTRIBUTION') NOT NULL,
  `is_taxable` tinyint(1) NOT NULL,
  PRIMARY KEY (`component_code`)
);

CREATE TABLE `payroll_components` (
  `payroll_component_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `payroll_record_id` bigint unsigned NOT NULL,
  `component_code` varchar(30) NOT NULL,
  `quantity` decimal(8,2) DEFAULT NULL COMMENT 'hours/days where applicable',
  `rate` decimal(12,4) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `amount` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  PRIMARY KEY (`payroll_component_id`),
  KEY `ix_payroll_comp_record` (`payroll_record_id`),
  KEY `ix_payroll_comp_code` (`component_code`),
  CONSTRAINT `fk_payroll_comp_code` FOREIGN KEY (`component_code`) REFERENCES `payroll_component_catalog` (`component_code`),
  CONSTRAINT `fk_payroll_comp_record` FOREIGN KEY (`payroll_record_id`) REFERENCES `payroll_records` (`payroll_record_id`)
);

CREATE TABLE `payroll_periods` (
  `payroll_period_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `period_code` char(7) NOT NULL COMMENT 'YYYY-MM',
  `period_start` date NOT NULL,
  `period_end` date NOT NULL,
  `pay_date` date NOT NULL,
  `working_days` tinyint unsigned NOT NULL,
  `period_status` enum('OPEN','PROCESSING','CLOSED') NOT NULL,
  PRIMARY KEY (`payroll_period_id`),
  UNIQUE KEY `uq_payroll_periods_tenant` (`tenant_id`,`payroll_period_id`),
  UNIQUE KEY `uq_payroll_periods_code` (`tenant_id`,`period_code`),
  CONSTRAINT `fk_payroll_periods_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`tenant_id`),
  CONSTRAINT `ck_payroll_periods_dates` CHECK ((`period_end` >= `period_start`))
);

CREATE TABLE `payroll_records` (
  `payroll_record_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `payroll_period_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `run_type` enum('REGULAR','SUPPLEMENTARY') NOT NULL DEFAULT 'REGULAR',
  `department_id` int unsigned NOT NULL COMMENT 'sensitivity=PUBLIC; department SNAPSHOT at pay date (cost allocation)',
  `cost_center_id` int unsigned NOT NULL COMMENT 'sensitivity=INTERNAL',
  `paid_days` decimal(4,1) NOT NULL COMMENT 'sensitivity=INTERNAL',
  `base_pay` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `allowance_pay` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `overtime_hours` decimal(6,2) NOT NULL DEFAULT '0.00' COMMENT 'sensitivity=INTERNAL',
  `overtime_pay` decimal(14,2) NOT NULL DEFAULT '0.00' COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `bonus_pay` decimal(14,2) NOT NULL DEFAULT '0.00' COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `other_earnings` decimal(14,2) NOT NULL DEFAULT '0.00' COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `gross_pay` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `income_tax` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `social_security_employee` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `social_security_employer` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `other_deductions` decimal(14,2) NOT NULL DEFAULT '0.00' COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `net_pay` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `currency_code` char(3) NOT NULL COMMENT 'sensitivity=PUBLIC',
  `bank_account_id` int unsigned DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `payment_status` enum('PAID','PENDING','FAILED','REVERSED') NOT NULL COMMENT 'sensitivity=INTERNAL',
  `paid_date` date DEFAULT NULL COMMENT 'sensitivity=INTERNAL',
  PRIMARY KEY (`payroll_record_id`),
  UNIQUE KEY `uq_payroll_records_tenant` (`tenant_id`,`payroll_record_id`),
  UNIQUE KEY `uq_payroll_emp_period` (`tenant_id`,`payroll_period_id`,`employee_id`,`run_type`),
  KEY `ix_payroll_employee` (`tenant_id`,`employee_id`),
  KEY `ix_payroll_dept_period` (`tenant_id`,`department_id`,`payroll_period_id`),
  KEY `fk_payroll_cost_center` (`tenant_id`,`cost_center_id`),
  KEY `fk_payroll_bank` (`tenant_id`,`bank_account_id`),
  KEY `fk_payroll_currency` (`currency_code`),
  CONSTRAINT `fk_payroll_bank` FOREIGN KEY (`tenant_id`, `bank_account_id`) REFERENCES `employee_bank_accounts` (`tenant_id`, `bank_account_id`),
  CONSTRAINT `fk_payroll_cost_center` FOREIGN KEY (`tenant_id`, `cost_center_id`) REFERENCES `cost_centers` (`tenant_id`, `cost_center_id`),
  CONSTRAINT `fk_payroll_currency` FOREIGN KEY (`currency_code`) REFERENCES `currencies` (`currency_code`),
  CONSTRAINT `fk_payroll_department` FOREIGN KEY (`tenant_id`, `department_id`) REFERENCES `departments` (`tenant_id`, `department_id`),
  CONSTRAINT `fk_payroll_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_payroll_period` FOREIGN KEY (`tenant_id`, `payroll_period_id`) REFERENCES `payroll_periods` (`tenant_id`, `payroll_period_id`)
);

CREATE TABLE `performance_goals` (
  `goal_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `goal_year` smallint unsigned NOT NULL,
  `goal_title` varchar(150) NOT NULL,
  `goal_category` enum('DELIVERY','QUALITY','CUSTOMER','GROWTH','PEOPLE','COMPLIANCE') NOT NULL,
  `weight_pct` tinyint unsigned NOT NULL,
  `progress_pct` tinyint unsigned NOT NULL,
  `goal_status` enum('IN_PROGRESS','ACHIEVED','PARTIALLY_ACHIEVED','NOT_ACHIEVED','CANCELLED') NOT NULL,
  `due_date` date NOT NULL,
  PRIMARY KEY (`goal_id`),
  KEY `ix_goals_employee` (`tenant_id`,`employee_id`,`goal_year`),
  CONSTRAINT `fk_goals_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `ck_goals_progress` CHECK ((`progress_pct` <= 100))
);

CREATE TABLE `performance_reviews` (
  `performance_review_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `reviewer_employee_id` int unsigned DEFAULT NULL,
  `review_cycle` char(7) NOT NULL COMMENT 'e.g. 2024-H1',
  `review_period_start` date NOT NULL,
  `review_period_end` date NOT NULL,
  `review_date` date NOT NULL,
  `department_id` int unsigned NOT NULL COMMENT 'department snapshot at review time',
  `overall_rating` decimal(3,2) NOT NULL COMMENT 'sensitivity=INTERNAL; 1.00-5.00',
  `rating_band` enum('UNSATISFACTORY','NEEDS_IMPROVEMENT','MEETS_EXPECTATIONS','EXCEEDS_EXPECTATIONS','OUTSTANDING') NOT NULL,
  `review_status` enum('DRAFT','SUBMITTED','CALIBRATED','FINALIZED') NOT NULL,
  `manager_comments` varchar(500) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  PRIMARY KEY (`performance_review_id`),
  UNIQUE KEY `uq_perf_reviews_tenant` (`tenant_id`,`performance_review_id`),
  UNIQUE KEY `uq_perf_reviews_cycle` (`tenant_id`,`employee_id`,`review_cycle`),
  KEY `ix_perf_reviews_dept` (`tenant_id`,`department_id`,`review_cycle`),
  KEY `fk_perf_reviews_reviewer` (`tenant_id`,`reviewer_employee_id`),
  CONSTRAINT `fk_perf_reviews_dept` FOREIGN KEY (`tenant_id`, `department_id`) REFERENCES `departments` (`tenant_id`, `department_id`),
  CONSTRAINT `fk_perf_reviews_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_perf_reviews_reviewer` FOREIGN KEY (`tenant_id`, `reviewer_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `ck_perf_reviews_rating` CHECK ((`overall_rating` between 1.00 and 5.00))
);

CREATE TABLE `performance_scores` (
  `performance_score_id` int unsigned NOT NULL AUTO_INCREMENT,
  `performance_review_id` int unsigned NOT NULL,
  `competency_code` varchar(30) NOT NULL,
  `score` decimal(3,2) NOT NULL,
  `weight_pct` tinyint unsigned NOT NULL,
  PRIMARY KEY (`performance_score_id`),
  UNIQUE KEY `uq_perf_scores` (`performance_review_id`,`competency_code`),
  KEY `fk_perf_scores_competency` (`competency_code`),
  CONSTRAINT `fk_perf_scores_competency` FOREIGN KEY (`competency_code`) REFERENCES `competency_catalog` (`competency_code`),
  CONSTRAINT `fk_perf_scores_review` FOREIGN KEY (`performance_review_id`) REFERENCES `performance_reviews` (`performance_review_id`),
  CONSTRAINT `ck_perf_scores_score` CHECK ((`score` between 1.00 and 5.00))
);

CREATE TABLE `position_skill_requirements` (
  `tenant_id` int unsigned NOT NULL,
  `position_id` int unsigned NOT NULL,
  `skill_id` int unsigned NOT NULL,
  `required_proficiency` tinyint unsigned NOT NULL,
  `is_mandatory` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`tenant_id`,`position_id`,`skill_id`),
  KEY `fk_pos_skill_skill` (`skill_id`),
  CONSTRAINT `fk_pos_skill_position` FOREIGN KEY (`tenant_id`, `position_id`) REFERENCES `job_positions` (`tenant_id`, `position_id`),
  CONSTRAINT `fk_pos_skill_skill` FOREIGN KEY (`skill_id`) REFERENCES `skill_catalog` (`skill_id`),
  CONSTRAINT `ck_pos_skill_level` CHECK ((`required_proficiency` between 1 and 5))
);

CREATE TABLE `project_assignments` (
  `assignment_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `project_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `project_role` enum('PROJECT_MANAGER','LEAD','CONTRIBUTOR','ANALYST','SPECIALIST','REVIEWER') NOT NULL,
  `allocation_pct` tinyint unsigned NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date DEFAULT NULL,
  `billing_rate_hourly` decimal(10,2) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  PRIMARY KEY (`assignment_id`),
  UNIQUE KEY `uq_assignments_tenant` (`tenant_id`,`assignment_id`),
  UNIQUE KEY `uq_assignments_tenant_emp` (`tenant_id`,`assignment_id`,`employee_id`),
  KEY `ix_assignments_project` (`tenant_id`,`project_id`),
  KEY `ix_assignments_employee` (`tenant_id`,`employee_id`,`start_date`),
  CONSTRAINT `fk_assignments_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_assignments_project` FOREIGN KEY (`tenant_id`, `project_id`) REFERENCES `projects` (`tenant_id`, `project_id`),
  CONSTRAINT `ck_assignments_alloc` CHECK ((`allocation_pct` between 5 and 100)),
  CONSTRAINT `ck_assignments_dates` CHECK (((`end_date` is null) or (`end_date` >= `start_date`)))
);

CREATE TABLE `project_resource_allocations` (
  `allocation_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `project_id` int unsigned NOT NULL,
  `department_id` int unsigned NOT NULL,
  `allocation_month` date NOT NULL,
  `planned_fte` decimal(6,2) NOT NULL,
  `planned_hours` decimal(8,2) NOT NULL,
  `actual_hours` decimal(8,2) NOT NULL,
  PRIMARY KEY (`allocation_id`),
  UNIQUE KEY `uq_project_alloc` (`tenant_id`,`project_id`,`department_id`,`allocation_month`),
  KEY `fk_proj_alloc_department` (`tenant_id`,`department_id`),
  CONSTRAINT `fk_proj_alloc_department` FOREIGN KEY (`tenant_id`, `department_id`) REFERENCES `departments` (`tenant_id`, `department_id`),
  CONSTRAINT `fk_proj_alloc_project` FOREIGN KEY (`tenant_id`, `project_id`) REFERENCES `projects` (`tenant_id`, `project_id`)
);

CREATE TABLE `projects` (
  `project_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `project_code` varchar(30) NOT NULL,
  `project_name` varchar(150) NOT NULL,
  `project_type` enum('CLIENT','INTERNAL','R_AND_D','COMPLIANCE','INFRASTRUCTURE') NOT NULL,
  `owning_department_id` int unsigned NOT NULL,
  `project_manager_employee_id` int unsigned DEFAULT NULL,
  `client_name` varchar(120) DEFAULT NULL COMMENT 'sensitivity=INTERNAL; synthetic',
  `start_date` date NOT NULL,
  `planned_end_date` date NOT NULL,
  `actual_end_date` date DEFAULT NULL,
  `project_status` enum('PLANNED','ACTIVE','ON_HOLD','COMPLETED','CANCELLED') NOT NULL,
  `budget_amount` decimal(16,2) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `is_billable` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`project_id`),
  UNIQUE KEY `uq_projects_tenant` (`tenant_id`,`project_id`),
  UNIQUE KEY `uq_projects_code` (`tenant_id`,`project_code`),
  KEY `fk_projects_department` (`tenant_id`,`owning_department_id`),
  KEY `fk_projects_manager` (`tenant_id`,`project_manager_employee_id`),
  CONSTRAINT `fk_projects_department` FOREIGN KEY (`tenant_id`, `owning_department_id`) REFERENCES `departments` (`tenant_id`, `department_id`),
  CONSTRAINT `fk_projects_manager` FOREIGN KEY (`tenant_id`, `project_manager_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `ck_projects_dates` CHECK (((`planned_end_date` >= `start_date`) and ((`actual_end_date` is null) or (`actual_end_date` >= `start_date`))))
);

CREATE TABLE `promotion_history` (
  `promotion_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `effective_date` date NOT NULL,
  `from_position_id` int unsigned NOT NULL,
  `to_position_id` int unsigned NOT NULL,
  `from_level_code` char(2) NOT NULL,
  `to_level_code` char(2) NOT NULL,
  `promotion_type` enum('MERIT','VACANCY_FILL','RECLASSIFICATION') NOT NULL,
  `salary_before` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `salary_after` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `approved_by_employee_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`promotion_id`),
  KEY `ix_promotions_employee` (`tenant_id`,`employee_id`,`effective_date`),
  KEY `fk_promo_from_pos` (`tenant_id`,`from_position_id`),
  KEY `fk_promo_to_pos` (`tenant_id`,`to_position_id`),
  KEY `fk_promo_approver` (`tenant_id`,`approved_by_employee_id`),
  KEY `fk_promo_from_lvl` (`from_level_code`),
  KEY `fk_promo_to_lvl` (`to_level_code`),
  CONSTRAINT `fk_promo_approver` FOREIGN KEY (`tenant_id`, `approved_by_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_promo_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_promo_from_lvl` FOREIGN KEY (`from_level_code`) REFERENCES `job_levels` (`job_level_code`),
  CONSTRAINT `fk_promo_from_pos` FOREIGN KEY (`tenant_id`, `from_position_id`) REFERENCES `job_positions` (`tenant_id`, `position_id`),
  CONSTRAINT `fk_promo_to_lvl` FOREIGN KEY (`to_level_code`) REFERENCES `job_levels` (`job_level_code`),
  CONSTRAINT `fk_promo_to_pos` FOREIGN KEY (`tenant_id`, `to_position_id`) REFERENCES `job_positions` (`tenant_id`, `position_id`)
);

CREATE TABLE `public_holidays` (
  `holiday_id` int unsigned NOT NULL AUTO_INCREMENT,
  `country_code` char(2) NOT NULL,
  `holiday_date` date NOT NULL,
  `holiday_name` varchar(100) NOT NULL,
  `holiday_type` enum('NATIONAL','RELIGIOUS','BANK','OBSERVANCE') NOT NULL,
  PRIMARY KEY (`holiday_id`),
  UNIQUE KEY `uq_public_holidays` (`country_code`,`holiday_date`,`holiday_name`),
  KEY `ix_public_holidays_date` (`holiday_date`),
  CONSTRAINT `fk_holidays_country` FOREIGN KEY (`country_code`) REFERENCES `countries` (`country_code`)
);

CREATE TABLE `qualification_levels` (
  `qualification_code` varchar(20) NOT NULL,
  `qualification_name` varchar(80) NOT NULL,
  `isced_level` tinyint unsigned NOT NULL,
  PRIMARY KEY (`qualification_code`)
);

CREATE TABLE `salary_history` (
  `salary_history_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `effective_from` date NOT NULL,
  `effective_to` date DEFAULT NULL,
  `annual_base_salary` decimal(14,2) NOT NULL COMMENT 'sensitivity=RESTRICTED; mask=BAND',
  `currency_code` char(3) NOT NULL,
  `change_reason` enum('HIRE','BASELINE','ANNUAL_MERIT','PROMOTION','MARKET_ADJUSTMENT','TRANSFER','CORRECTION') NOT NULL,
  `change_pct` decimal(6,2) DEFAULT NULL COMMENT 'sensitivity=RESTRICTED; mask=FULL',
  `approved_by_employee_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`salary_history_id`),
  UNIQUE KEY `uq_salary_history` (`tenant_id`,`employee_id`,`effective_from`),
  KEY `fk_salary_approver` (`tenant_id`,`approved_by_employee_id`),
  KEY `fk_salary_currency` (`currency_code`),
  CONSTRAINT `fk_salary_approver` FOREIGN KEY (`tenant_id`, `approved_by_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_salary_currency` FOREIGN KEY (`currency_code`) REFERENCES `currencies` (`currency_code`),
  CONSTRAINT `fk_salary_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `ck_salary_dates` CHECK (((`effective_to` is null) or (`effective_to` >= `effective_from`))),
  CONSTRAINT `ck_salary_positive` CHECK ((`annual_base_salary` > 0))
);

CREATE TABLE `shift_assignments` (
  `shift_assignment_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `shift_id` int unsigned NOT NULL,
  `effective_from` date NOT NULL,
  `effective_to` date DEFAULT NULL,
  PRIMARY KEY (`shift_assignment_id`),
  KEY `ix_shift_assign_employee` (`tenant_id`,`employee_id`,`effective_from`),
  KEY `fk_shift_assign_shift` (`tenant_id`,`shift_id`),
  CONSTRAINT `fk_shift_assign_employee` FOREIGN KEY (`tenant_id`, `employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_shift_assign_shift` FOREIGN KEY (`tenant_id`, `shift_id`) REFERENCES `work_shifts` (`tenant_id`, `shift_id`),
  CONSTRAINT `ck_shift_assign_dates` CHECK (((`effective_to` is null) or (`effective_to` >= `effective_from`)))
);

CREATE TABLE `skill_catalog` (
  `skill_id` int unsigned NOT NULL,
  `skill_code` varchar(30) NOT NULL,
  `skill_name` varchar(100) NOT NULL,
  `skill_category` enum('TECHNICAL','DOMAIN','LEADERSHIP','COMPLIANCE','INTERPERSONAL') NOT NULL,
  PRIMARY KEY (`skill_id`),
  UNIQUE KEY `uq_skill_catalog_code` (`skill_code`)
);

CREATE TABLE `standardized_job_categories` (
  `job_category_code` varchar(20) NOT NULL,
  `job_category_name` varchar(100) NOT NULL,
  `isco_major_group` tinyint unsigned NOT NULL COMMENT 'ISCO-08 major group (1-9)',
  `job_family` varchar(40) NOT NULL,
  PRIMARY KEY (`job_category_code`)
);

CREATE TABLE `teams` (
  `team_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `department_id` int unsigned NOT NULL,
  `team_code` varchar(30) NOT NULL,
  `team_name` varchar(100) NOT NULL,
  `formed_date` date NOT NULL,
  PRIMARY KEY (`team_id`),
  UNIQUE KEY `uq_teams_tenant` (`tenant_id`,`team_id`),
  UNIQUE KEY `uq_teams_code` (`tenant_id`,`team_code`),
  UNIQUE KEY `uq_teams_dept` (`tenant_id`,`department_id`,`team_id`) COMMENT 'lets employees enforce team-belongs-to-department',
  CONSTRAINT `fk_teams_department` FOREIGN KEY (`tenant_id`, `department_id`) REFERENCES `departments` (`tenant_id`, `department_id`)
);

CREATE TABLE `tenants` (
  `tenant_id` int unsigned NOT NULL,
  `tenant_code` varchar(20) NOT NULL,
  `company_name` varchar(120) NOT NULL,
  `industry_code` varchar(20) NOT NULL,
  `company_size` enum('SMALL','MEDIUM','LARGE','ENTERPRISE') NOT NULL,
  `country_code` char(2) NOT NULL COMMENT 'country of registration / HQ',
  `base_currency_code` char(3) NOT NULL COMMENT 'all monetary amounts of this tenant are stored in this currency',
  `email_domain` varchar(80) NOT NULL,
  `fiscal_year_start_month` tinyint unsigned NOT NULL DEFAULT '1',
  `registered_date` date NOT NULL,
  `status` enum('ACTIVE','TRIAL','SUSPENDED','CHURNED') NOT NULL DEFAULT 'ACTIVE',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`tenant_id`),
  UNIQUE KEY `uq_tenants_code` (`tenant_code`),
  KEY `fk_tenants_industry` (`industry_code`),
  KEY `fk_tenants_country` (`country_code`),
  KEY `fk_tenants_currency` (`base_currency_code`),
  CONSTRAINT `fk_tenants_country` FOREIGN KEY (`country_code`) REFERENCES `countries` (`country_code`),
  CONSTRAINT `fk_tenants_currency` FOREIGN KEY (`base_currency_code`) REFERENCES `currencies` (`currency_code`),
  CONSTRAINT `fk_tenants_industry` FOREIGN KEY (`industry_code`) REFERENCES `industry_types` (`industry_code`),
  CONSTRAINT `ck_tenants_fy` CHECK ((`fiscal_year_start_month` between 1 and 12))
);

CREATE TABLE `timesheets` (
  `timesheet_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `assignment_id` int unsigned NOT NULL,
  `employee_id` int unsigned NOT NULL,
  `week_start_date` date NOT NULL COMMENT 'Monday',
  `hours_logged` decimal(5,2) NOT NULL,
  `billable_hours` decimal(5,2) NOT NULL,
  `timesheet_status` enum('SUBMITTED','APPROVED','REJECTED') NOT NULL,
  `submitted_at` datetime NOT NULL,
  `approved_by_employee_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`timesheet_id`),
  UNIQUE KEY `uq_timesheets_week` (`tenant_id`,`assignment_id`,`week_start_date`),
  KEY `ix_timesheets_employee` (`tenant_id`,`employee_id`,`week_start_date`),
  KEY `ix_timesheets_week` (`tenant_id`,`week_start_date`),
  KEY `fk_timesheets_assignment` (`tenant_id`,`assignment_id`,`employee_id`),
  KEY `fk_timesheets_approver` (`tenant_id`,`approved_by_employee_id`),
  CONSTRAINT `fk_timesheets_approver` FOREIGN KEY (`tenant_id`, `approved_by_employee_id`) REFERENCES `employees` (`tenant_id`, `employee_id`),
  CONSTRAINT `fk_timesheets_assignment` FOREIGN KEY (`tenant_id`, `assignment_id`, `employee_id`) REFERENCES `project_assignments` (`tenant_id`, `assignment_id`, `employee_id`),
  CONSTRAINT `ck_timesheets_hours` CHECK (((`billable_hours` <= `hours_logged`) and (`hours_logged` <= 168)))
);

CREATE TABLE `training_programs` (
  `training_program_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `program_code` varchar(30) NOT NULL,
  `program_title` varchar(150) NOT NULL,
  `primary_skill_id` int unsigned NOT NULL,
  `delivery_mode` enum('CLASSROOM','ONLINE','BLENDED','ON_THE_JOB') NOT NULL,
  `provider_type` enum('INTERNAL','EXTERNAL') NOT NULL,
  `duration_hours` decimal(5,1) NOT NULL,
  `cost_per_participant` decimal(12,2) NOT NULL COMMENT 'sensitivity=INTERNAL',
  `is_mandatory` tinyint(1) NOT NULL DEFAULT '0',
  `awards_certification` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`training_program_id`),
  UNIQUE KEY `uq_training_programs_tenant` (`tenant_id`,`training_program_id`),
  UNIQUE KEY `uq_training_programs_code` (`tenant_id`,`program_code`),
  KEY `fk_training_programs_skill` (`primary_skill_id`),
  CONSTRAINT `fk_training_programs_skill` FOREIGN KEY (`primary_skill_id`) REFERENCES `skill_catalog` (`skill_id`),
  CONSTRAINT `fk_training_programs_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`tenant_id`)
);

CREATE TABLE `work_shifts` (
  `shift_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `shift_code` varchar(20) NOT NULL,
  `shift_name` varchar(60) NOT NULL,
  `start_time` time NOT NULL,
  `end_time` time NOT NULL,
  `break_minutes` smallint unsigned NOT NULL,
  `is_night_shift` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`shift_id`),
  UNIQUE KEY `uq_work_shifts_tenant` (`tenant_id`,`shift_id`),
  UNIQUE KEY `uq_work_shifts_code` (`tenant_id`,`shift_code`),
  CONSTRAINT `fk_shifts_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`tenant_id`)
);

CREATE TABLE `workforce_capacity` (
  `capacity_id` int unsigned NOT NULL AUTO_INCREMENT,
  `tenant_id` int unsigned NOT NULL,
  `department_id` int unsigned NOT NULL,
  `capacity_month` date NOT NULL,
  `budgeted_headcount` smallint unsigned NOT NULL,
  `actual_headcount` smallint unsigned NOT NULL COMMENT 'active at month end',
  `hires` smallint unsigned NOT NULL,
  `exits` smallint unsigned NOT NULL,
  `available_hours` decimal(10,2) NOT NULL,
  `overtime_hours` decimal(10,2) NOT NULL,
  `project_hours` decimal(10,2) NOT NULL,
  `open_requisitions` smallint unsigned NOT NULL,
  PRIMARY KEY (`capacity_id`),
  UNIQUE KEY `uq_workforce_capacity` (`tenant_id`,`department_id`,`capacity_month`),
  CONSTRAINT `fk_capacity_department` FOREIGN KEY (`tenant_id`, `department_id`) REFERENCES `departments` (`tenant_id`, `department_id`)
);

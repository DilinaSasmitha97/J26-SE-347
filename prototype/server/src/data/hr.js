import { mulberry32, pick, intBetween, between, round2, weighted } from './random.js';

// ---------------------------------------------------------------------------
// "PeopleOps" - a second, smaller connection (MySQL, in the story). Exists so
// the demo can show connection switching and per-connection schema/settings.
// ---------------------------------------------------------------------------

const FIRST = ['Ruwan', 'Nadeesha', 'Kavindu', 'Thilini', 'Sahan', 'Menaka', 'Dinesh', 'Iresha',
  'Grace', 'Daniel', 'Hannah', 'Peter', 'Laura', 'Samuel', 'Naomi', 'Victor', 'Farah', 'Jonas'];
const LAST = ['Rajapaksa', 'Ekanayake', 'Senanayake', 'Weerasinghe', 'Herath', 'Dias',
  'Clark', 'Lewis', 'Walker', 'Hall', 'Young', 'Wright', 'Ali', 'Costa', 'Berg'];

const DEPARTMENTS = [
  [1, 'Engineering', 'Colombo', 2400000],
  [2, 'Sales', 'London', 1350000],
  [3, 'Marketing', 'London', 780000],
  [4, 'Customer Support', 'Colombo', 620000],
  [5, 'Finance', 'Singapore', 540000],
  [6, 'People Ops', 'Colombo', 410000],
];

const TITLES = {
  Engineering: ['Software Engineer', 'Senior Software Engineer', 'QA Engineer', 'Engineering Manager', 'Data Engineer'],
  Sales: ['Account Executive', 'Sales Development Rep', 'Sales Manager'],
  Marketing: ['Marketing Specialist', 'Content Strategist', 'Marketing Manager'],
  'Customer Support': ['Support Agent', 'Senior Support Agent', 'Support Lead'],
  Finance: ['Accountant', 'Financial Analyst', 'Finance Manager'],
  'People Ops': ['Recruiter', 'HR Generalist', 'People Ops Manager'],
};

const BANDS = {
  'Software Engineer': [78000, 105000],
  'Senior Software Engineer': [115000, 150000],
  'QA Engineer': [62000, 85000],
  'Engineering Manager': [140000, 178000],
  'Data Engineer': [92000, 125000],
  'Account Executive': [70000, 98000],
  'Sales Development Rep': [48000, 62000],
  'Sales Manager': [110000, 145000],
  'Marketing Specialist': [55000, 74000],
  'Content Strategist': [58000, 78000],
  'Marketing Manager': [95000, 125000],
  'Support Agent': [38000, 52000],
  'Senior Support Agent': [52000, 68000],
  'Support Lead': [72000, 92000],
  Accountant: [56000, 74000],
  'Financial Analyst': [68000, 90000],
  'Finance Manager': [105000, 138000],
  Recruiter: [52000, 70000],
  'HR Generalist': [50000, 68000],
  'People Ops Manager': [92000, 120000],
};

const DAY = 86400000;
const TODAY = new Date('2026-06-30T00:00:00Z').getTime();
const iso = (ms) => new Date(ms).toISOString().slice(0, 10);

export function buildHr() {
  const rnd = mulberry32(778899);

  const departments = DEPARTMENTS.map((d) => ({
    department_id: d[0],
    department_name: d[1],
    location: d[2],
    annual_budget: d[3],
  }));

  const employees = [];
  for (let i = 1; i <= 180; i++) {
    const dept = weighted(rnd, [
      [departments[0], 8], [departments[1], 5], [departments[2], 3],
      [departments[3], 4], [departments[4], 2], [departments[5], 2],
    ]);
    const title = pick(rnd, TITLES[dept.department_name]);
    const band = BANDS[title];
    const hiredMs = TODAY - intBetween(rnd, 30, 2600) * DAY;
    const active = rnd() < 0.9;
    employees.push({
      employee_id: i,
      full_name: pick(rnd, FIRST) + ' ' + pick(rnd, LAST),
      department_id: dept.department_id,
      job_title: title,
      employment_type: weighted(rnd, [['Full-time', 8], ['Contract', 2], ['Part-time', 1]]),
      salary: Math.round(between(rnd, band[0], band[1]) / 500) * 500,
      hire_date: iso(hiredMs),
      exit_date: active ? null : iso(hiredMs + intBetween(rnd, 200, 1400) * DAY),
      is_active: active,
      performance_rating: round2(between(rnd, 2.4, 5)),
      location: dept.location,
    });
  }

  const leave = [];
  let leaveId = 0;
  for (const emp of employees) {
    const requests = intBetween(rnd, 0, 6);
    for (let r = 0; r < requests; r++) {
      leaveId++;
      const startMs = TODAY - intBetween(rnd, 0, 500) * DAY;
      const days = weighted(rnd, [[1, 5], [2, 3], [3, 2], [5, 2], [10, 1]]);
      leave.push({
        leave_id: leaveId,
        employee_id: emp.employee_id,
        leave_type: weighted(rnd, [['Annual', 5], ['Sick', 4], ['Unpaid', 1], ['Parental', 1]]),
        start_date: iso(startMs),
        days_taken: days,
        status: weighted(rnd, [['Approved', 8], ['Pending', 1], ['Rejected', 1]]),
      });
    }
  }

  return { employees, departments, leave_requests: leave };
}

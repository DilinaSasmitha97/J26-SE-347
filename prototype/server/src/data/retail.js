import { mulberry32, pick, intBetween, between, round2, weighted } from './random.js';

// ---------------------------------------------------------------------------
// "NorthWind Retail" - the primary demo warehouse (Postgres, in the story).
// Rows are generated from a fixed seed: same numbers on every machine.
// ---------------------------------------------------------------------------

const FIRST = ['Nimal', 'Kasun', 'Amaya', 'Sanduni', 'Tharindu', 'Ishara', 'Dilani', 'Ruwan', 'Chamath', 'Hasini',
  'Emma', 'Liam', 'Olivia', 'Noah', 'Ava', 'Ethan', 'Sofia', 'Lucas', 'Mia', 'Arjun',
  'Priya', 'Wei', 'Yuki', 'Chen', 'Aisha', 'Omar', 'Elena', 'Marco', 'Ines', 'Tomas'];

const LAST = ['Perera', 'Fernando', 'Silva', 'Jayasuriya', 'Bandara', 'Wickramasinghe', 'Gunawardena',
  'Smith', 'Johnson', 'Williams', 'Brown', 'Garcia', 'Miller', 'Davis', 'Nakamura', 'Kim',
  'Patel', 'Singh', 'Haddad', 'Rossi', 'Novak', 'Andersen'];

const REGIONS = [
  ['North America', ['United States', 'Canada']],
  ['Europe', ['United Kingdom', 'Germany', 'France', 'Spain']],
  ['Asia Pacific', ['Sri Lanka', 'India', 'Singapore', 'Japan', 'Australia']],
  ['Middle East', ['UAE', 'Qatar']],
];

const SEGMENTS = [['Consumer', 5], ['SMB', 3], ['Enterprise', 2]];
const CHANNELS = [['Web', 6], ['Mobile App', 4], ['Retail Store', 2], ['Partner', 1]];
const STATUSES = [['Completed', 82], ['Pending', 7], ['Cancelled', 6], ['Refunded', 5]];

const PRODUCTS = [
  ['Aurora Laptop 14', 'Electronics', 1299, 910],
  ['Aurora Laptop Pro 16', 'Electronics', 2199, 1580],
  ['Nimbus Wireless Mouse', 'Electronics', 39, 14],
  ['Nimbus Mechanical Keyboard', 'Electronics', 129, 58],
  ['Vertex 27in 4K Monitor', 'Electronics', 449, 300],
  ['Vertex Webcam 1080p', 'Electronics', 89, 33],
  ['Pulse Noise-Cancel Headphones', 'Electronics', 299, 142],
  ['Pulse Earbuds Mini', 'Electronics', 149, 61],
  ['Atlas Office Chair', 'Furniture', 549, 330],
  ['Atlas Standing Desk', 'Furniture', 699, 415],
  ['Atlas Desk Lamp', 'Furniture', 79, 28],
  ['Harbour Bookshelf', 'Furniture', 249, 128],
  ['Harbour Filing Cabinet', 'Furniture', 189, 96],
  ['Everyday Notebook A5', 'Stationery', 12, 4],
  ['Everyday Pen Pack', 'Stationery', 9, 3],
  ['Everyday Sticky Notes', 'Stationery', 6, 2],
  ['Archer Backpack', 'Accessories', 119, 52],
  ['Archer Laptop Sleeve', 'Accessories', 45, 17],
  ['Archer Travel Adapter', 'Accessories', 29, 10],
  ['Verde Water Bottle', 'Accessories', 24, 8],
  ['Summit Trail Shoes', 'Apparel', 139, 64],
  ['Summit Rain Jacket', 'Apparel', 179, 82],
  ['Summit Merino Socks', 'Apparel', 22, 7],
  ['Cobalt Smart Watch', 'Electronics', 379, 205],
  ['Cobalt Fitness Band', 'Electronics', 99, 41],
];

const DAY = 86400000;
// Anchor the dataset so relative dates ("last month") always land on real rows.
export const TODAY = new Date('2026-06-30T00:00:00Z').getTime();
const START = TODAY - 730 * DAY;

const iso = (ms) => new Date(ms).toISOString().slice(0, 10);

// Seasonality: Nov/Dec peak, Jan/Feb trough, plus steady growth over time.
function seasonalWeight(ms) {
  const d = new Date(ms);
  const monthFactor = [0.78, 0.8, 0.95, 1.0, 1.03, 1.0, 0.97, 1.0, 1.06, 1.12, 1.35, 1.45][d.getUTCMonth()];
  const growth = 1 + ((ms - START) / (TODAY - START)) * 0.45;
  const weekend = d.getUTCDay() === 0 || d.getUTCDay() === 6 ? 0.85 : 1.05;
  return monthFactor * growth * weekend;
}

export function buildRetail() {
  const rnd = mulberry32(20260630);

  const products = PRODUCTS.map((p, i) => ({
    product_id: i + 1,
    product_name: p[0],
    category: p[1],
    unit_price: p[2],
    unit_cost: p[3],
    in_stock: intBetween(rnd, 0, 640),
    discontinued: rnd() < 0.08,
  }));

  const customers = [];
  for (let i = 1; i <= 420; i++) {
    const [region, countries] = pick(rnd, REGIONS);
    const first = pick(rnd, FIRST);
    const last = pick(rnd, LAST);
    customers.push({
      customer_id: i,
      customer_name: first + ' ' + last,
      email: first.toLowerCase() + '.' + last.toLowerCase() + i + '@example.com',
      phone: '+' + intBetween(rnd, 1, 94) + '-' + intBetween(rnd, 200, 999) + '-' + intBetween(rnd, 1000, 9999),
      region,
      country: pick(rnd, countries),
      segment: weighted(rnd, SEGMENTS),
      signup_date: iso(START - intBetween(rnd, 0, 500) * DAY),
      is_active: rnd() < 0.87,
    });
  }

  const orders = [];
  const orderItems = [];
  let orderId = 0;
  let itemId = 0;

  for (let day = 0; day < 730; day++) {
    const ms = START + day * DAY;
    const count = Math.max(0, Math.round(between(rnd, 1.6, 4.4) * seasonalWeight(ms)));

    for (let k = 0; k < count; k++) {
      orderId++;
      const customer = customers[intBetween(rnd, 0, customers.length - 1)];
      const lines = weighted(rnd, [[1, 5], [2, 4], [3, 3], [4, 1]]);

      let total = 0;
      const used = new Set();
      for (let l = 0; l < lines; l++) {
        let prod = products[intBetween(rnd, 0, products.length - 1)];
        let guard = 0;
        while (used.has(prod.product_id) && guard++ < 6) {
          prod = products[intBetween(rnd, 0, products.length - 1)];
        }
        used.add(prod.product_id);

        const qty = weighted(rnd, [[1, 6], [2, 3], [3, 2], [5, 1]]);
        const discount = weighted(rnd, [[0, 7], [0.05, 2], [0.1, 1.5], [0.2, 0.5]]);
        const unit = round2(prod.unit_price * (1 - discount));
        const lineTotal = round2(unit * qty);
        total += lineTotal;
        itemId++;
        orderItems.push({
          order_item_id: itemId,
          order_id: orderId,
          product_id: prod.product_id,
          quantity: qty,
          unit_price: unit,
          discount,
          line_total: lineTotal,
          line_cost: round2(prod.unit_cost * qty),
        });
      }

      const shipping = round2(weighted(rnd, [[0, 4], [4.99, 3], [9.99, 2], [14.99, 1]]));
      orders.push({
        order_id: orderId,
        customer_id: customer.customer_id,
        order_date: iso(ms),
        status: weighted(rnd, STATUSES),
        channel: weighted(rnd, CHANNELS),
        shipping_fee: shipping,
        total_amount: round2(total + shipping),
      });
    }
  }

  const TOPICS = ['Delivery delay', 'Damaged item', 'Refund request', 'Billing question',
    'Product question', 'Account access', 'Warranty claim'];

  const tickets = [];
  for (let i = 1; i <= 520; i++) {
    const order = orders[intBetween(rnd, 0, orders.length - 1)];
    const opened = new Date(order.order_date).getTime() + intBetween(rnd, 0, 20) * DAY;
    if (opened > TODAY) continue;
    const resolvedIn = weighted(rnd, [[null, 2], [1, 4], [2, 3], [4, 2], [9, 1]]);
    tickets.push({
      ticket_id: i,
      order_id: order.order_id,
      customer_id: order.customer_id,
      subject: pick(rnd, TOPICS),
      priority: weighted(rnd, [['Low', 4], ['Medium', 5], ['High', 2], ['Urgent', 1]]),
      status: resolvedIn === null ? 'Open' : 'Resolved',
      opened_date: iso(opened),
      resolved_date: resolvedIn === null ? null : iso(opened + resolvedIn * DAY),
      satisfaction_score: resolvedIn === null ? null : intBetween(rnd, 2, 5),
    });
  }

  return { customers, products, orders, order_items: orderItems, support_tickets: tickets };
}

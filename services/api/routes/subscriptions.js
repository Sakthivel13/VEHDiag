'use strict';
/** VEHDiag — /api/v1/subscriptions: plan catalog + plan selection (no payment in dev). */

const { HttpError, ok, readJson } = require('../lib/http');

const PLANS = {
  free: { id: 'free', name: 'Free', priceInr: 0, limits: { vehicles: 3, sessions: 20, users: 1 } },
  pro: { id: 'pro', name: 'Pro', priceInr: 499, limits: { vehicles: -1, sessions: -1, users: 1 } },
  workshop: { id: 'workshop', name: 'Workshop', priceInr: 1999, limits: { vehicles: -1, sessions: -1, users: 10 } },
};

function mount(router, { store, log, notify }) {
  router.get('/api/v1/subscriptions/plans', async (req, res) => {
    ok(res, { plans: Object.values(PLANS) });
  });

  router.get('/api/v1/subscriptions/me', async (req, res) => {
    ok(res, { subscription: req.user.subscription || { plan: 'free' }, plans: Object.values(PLANS) });
  });

  router.post('/api/v1/subscriptions/select', async (req, res) => {
    const body = await readJson(req);
    if (!PLANS[body.plan]) throw new HttpError(400, 'Unknown plan', 'invalid_plan');
    const users = store.collection('users');
    const u = users.find((x) => x.id === req.user.id);
    u.subscription = { plan: body.plan, since: new Date().toISOString(), source: 'dev-checkout' };
    store.scheduleFlush();
    notify(u.id, { type: 'subscription', title: `Plan updated — ${PLANS[body.plan].name}`, body: 'Your VEHDiag subscription has been updated.' });
    log.app('info', 'plan_changed', { userId: u.id, plan: body.plan });
    ok(res, { subscription: u.subscription });
  });
}

module.exports = { mount, PLANS };

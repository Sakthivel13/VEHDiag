'use strict';
/** VEHDiag — /api/v1/admin: role-gated administration (users, stats, audit). */

const { HttpError, ok, readJson } = require('../lib/http');
const { hasRole, publicUser } = require('../lib/auth');

function requireAdmin(req) {
  if (!hasRole(req.user, 'ADMIN')) throw new HttpError(403, 'Administrator role required', 'forbidden');
}

function mount(router, { store, log }) {
  router.get('/api/v1/admin/stats', async (req, res) => {
    requireAdmin(req);
    const users = store.collection('users');
    const sessions = store.collection('sessions');
    const reports = store.collection('reports');
    const dtcs = sessions.flatMap((s) => (s.scan && s.scan.dtcs ? s.scan.dtcs : []));
    ok(res, {
      stats: {
        users: users.length,
        vehicles: store.collection('vehicles').length,
        sessions: sessions.length,
        activeSessions: sessions.filter((s) => s.status === 'scanning' || s.status === 'created').length,
        reports: reports.length,
        devices: store.collection('devices').length,
        dtcsFound: dtcs.length,
        scansToday: sessions.filter((s) => s.createdAt > new Date(Date.now() - 864e5).toISOString()).length,
        byRole: Object.fromEntries(users.reduce((m, u) => (m[u.role] = (m[u.role] || 0) + 1, m), {})),
      },
    });
  });

  router.get('/api/v1/admin/users', async (req, res) => {
    requireAdmin(req);
    const q = String(req.query.q || '').toLowerCase();
    let users = store.collection('users');
    if (q) users = users.filter((u) => (u.email + ' ' + u.name).toLowerCase().includes(q));
    ok(res, { users: users.map(publicUser) });
  });

  router.patch('/api/v1/admin/users/:id', async (req, res) => {
    requireAdmin(req);
    const body = await readJson(req);
    const users = store.collection('users');
    const u = users.find((x) => x.id === req.params.id);
    if (!u) throw new HttpError(404, 'User not found', 'not_found');
    if (body.role) {
      const { ROLES } = require('../lib/auth');
      if (!ROLES.includes(body.role)) throw new HttpError(400, 'Invalid role', 'invalid_role');
      if (u.id === req.user.id && body.role !== req.user.role) throw new HttpError(400, 'You cannot change your own role', 'forbidden');
      u.role = body.role;
    }
    if (typeof body.suspended === 'boolean') u.suspended = body.suspended;
    u.updatedAt = new Date().toISOString();
    store.scheduleFlush();
    log.sec('warn', 'admin_user_update', { by: req.user.id, target: u.id, role: u.role });
    ok(res, { user: publicUser(u) });
  });

  router.get('/api/v1/admin/audit', async (req, res) => {
    requireAdmin(req);
    const audit = store.collection('audit').slice(-200).reverse();
    ok(res, { audit });
  });
}

module.exports = { mount };
